from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import supabase, reset_supabase_auth
from schemas import UserAuthSchema

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

def normalize_role(role: str) -> str:
    if not role:
        return "user"
    return role.strip().lower().replace("-", "_").replace(" ", "_")

# --- 1. TOKEN VERIFY KARNA AUR LIVE ROLE DATABASE SE NIKALNA ---
def get_current_user_with_role(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ya expired token")
        
        user_id = user_response.user.id

        # Always ensure clean postgrest client with server key
        reset_supabase_auth()
        profile = supabase.table("profiles").select("role").eq("id", user_id).execute()
        if not profile.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile record nahi mila")

        raw_role = profile.data[0].get("role", "user")
        normalized_role = normalize_role(raw_role)

        return {
            "id": user_id,
            "email": user_response.user.email,
            "role": normalized_role  # Always normalized e.g. 'ops_agent', 'super_admin', 'user'
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


# --- 2. PERMISSION GUARDS ---
def verify_super_admin(user=Depends(get_current_user_with_role)):
    if normalize_role(user["role"]) != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access Denied: Sirf Super-Admin ko yeh action allow hai"
        )
    return user


def verify_ops_or_admin(user=Depends(get_current_user_with_role)):
    if normalize_role(user["role"]) not in ["super_admin", "ops_agent"]:
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
    # Always reset auth header so PostgREST uses the server API key, not an expired user JWT
    reset_supabase_auth()
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

        token = getattr(session, "access_token", None)
        if not token and isinstance(session, dict):
            token = session.get("access_token")

        # Immediately restore postgrest client header to server key
        reset_supabase_auth()

        if profile_res.data:
            supabase.table("profiles").update({
                "failed_attempts": 0, 
                "locked_until": None
            }).eq("email", user.email).execute()

        raw_role = profile_res.data[0].get("role", "user") if profile_res.data else "user"
        user_role = normalize_role(raw_role)

        return {
            "message": "Login successful",
            "token": token,
            "email": user.email,
            "role": user_role
        }

    except HTTPException:
        raise
    except Exception:
        # Restore postgrest client header to server key before updating failed attempts
        reset_supabase_auth()
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
    finally:
        reset_supabase_auth()