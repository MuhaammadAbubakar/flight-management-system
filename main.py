import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routers import admin, search, bookings
import auth

app = FastAPI(
    title="Mera Safar - Flight Management System",
    description="Dual-writer transactional core & luxury flight booking portal",
    version="1.0.0",
    docs_url=None,     # Swagger UI disable
    redoc_url=None     # ReDoc disable
)

origins = [
    "https://merasafar.site.je",   
    "http://localhost:5173",
    "https://*.railway.app",
    "*"  # Development aur presentation ke waqt "*" har domain ko allow kar deta hai
]
# Enable CORS for browser frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers register karein
app.include_router(admin.router)
app.include_router(search.router)
app.include_router(bookings.router)
app.include_router(auth.router)

# Dedicated Frontend Directory Mount
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
os.makedirs(frontend_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

@app.get("/")
def index():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "running", "name": "Mera Safar Flight System", "docs": "/docs"}

@app.get("/api/health")
def health_check():
    return {"status": "running", "message": "Mera Safar Flight API is healthy"}