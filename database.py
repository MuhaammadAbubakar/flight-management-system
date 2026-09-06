import os
from dotenv import load_dotenv
from supabase import create_client,Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


supabase: Client = create_client(SUPABASE_URL,SUPABASE_KEY)
# Apni copied URI string yahan dalein
DATABASE_URL = "postgresql://postgres:im43Hex1vDkexxtA@db.qxqxookmjfmcrvhrugki.supabase.co:5432/postgres"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()