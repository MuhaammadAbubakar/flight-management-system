from fastapi import FastAPI
from routers import admin, search, bookings
import auth
app = FastAPI(
    title="Flight Management System API",
    description="Dual-writer transactional core for Flight Booking Hackathon",
    version="1.0.0"
)

# Routers register karein
app.include_router(admin.router)
app.include_router(search.router)
app.include_router(bookings.router)
app.include_router(auth.router)

@app.get("/")
def health_check():
    return {"status": "running", "message": "Flight API is healthy"}