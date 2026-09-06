from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import supabase
from schemas import UserAuthSchema

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

# --- 1. TOKEN VERIFY KARNA AUR LIVE ROLE DATABASE SE NIKALNA ---
def get_current_user_with_role(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ya expired token")
        
        user_id = user_response.user.id

        # Profile table se role read karein
        profile = supabase.table("profiles").select("role").eq("id", user_id).execute()
        if not profile.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile record nahi mila")

        return {
            "id": user_id,
            "email": user_response.user.email,
            "role": profile.data[0].get("role", "user")  # Default 'user'
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


# --- 2. PERMISSION GUARDS ---
def verify_super_admin(user=Depends(get_current_user_with_role)):
    if user["role"] != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access Denied: Sirf Super-Admin ko yeh action allow hai"
        )
    return user


def verify_ops_or_admin(user=Depends(get_current_user_with_role)):
    if user["role"] not in ["super_admin", "ops_agent"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access Denied: Super-Admin ya Ops-Agent permissions darkar hain"
        )
    return user


# --- 3. CLEAN SIGNUP (DEFAULT 'user' BANEGA) ---
@router.post("/signup")
def sign_up(user: UserAuthSchema):
    try:
        signup_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password
        })

        if not signup_response.user:
            raise HTTPException(status_code=400, detail="Signup fail ho gaya. Details check karein.")

        return {
            "message": "Account successfully create ho gaya hai.",
            "email": signup_response.user.email
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- 4. SIGNIN ---
@router.post("/signin")
def sign_in(user: UserAuthSchema):
    profile_res = supabase.table("profiles").select("*").eq("email", user.email).execute()
    if profile_res.data:
        profile = profile_res.data[0]
        lock_until = profile.get("locked_until")
        if lock_until:
            try:
                lock_time = datetime.fromisoformat(lock_until.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) < lock_time:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account temporarily lock hai. 15 minute baad try karein."
                    )
            except HTTPException:
                raise
            except Exception:
                pass

    try:
        signin_response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })

        session = getattr(signin_response, "session", None)
        if not session and isinstance(signin_response, dict):
            session = signin_response.get("session")

        if not session:
            raise Exception("Invalid email or password")

        if profile_res.data:
            supabase.table("profiles").update({
                "failed_attempts": 0, 
                "locked_until": None
            }).eq("email", user.email).execute()

        token = getattr(session, "access_token", None)
        if not token and isinstance(session, dict):
            token = session.get("access_token")

        return {
            "message": "Login successful",
            "token": token
        }

    except HTTPException:
        raise
    except Exception:
        if profile_res.data:
            profile = profile_res.data[0]
            current_attempts = (profile.get("failed_attempts") or 0) + 1
            update_data = {"failed_attempts": current_attempts}

            if current_attempts >= 5:
                future_time = datetime.now(timezone.utc) + timedelta(minutes=15)
                update_data["locked_until"] = future_time.isoformat()

            supabase.table("profiles").update(update_data).eq("email", user.email).execute()

            if current_attempts >= 5:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="5 dafa ghalat password dala gaya. Account 15 minute ke liye lock kar diya gaya hai."
                )

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")