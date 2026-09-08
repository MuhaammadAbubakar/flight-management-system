import os
from dotenv import load_dotenv
from supabase import create_client, Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Startup guard — agar koi env var missing ho to clear error de
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL aur SUPABASE_KEY .env mein hone chahiye!")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL .env mein hona chahiye!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def reset_supabase_auth():
    """Resets postgrest client Authorization header to server API key so expired user sessions never block DB calls."""
    try:
        supabase.postgrest.auth(SUPABASE_KEY)
    except Exception:
        pass

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()