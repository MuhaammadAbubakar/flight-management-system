from pydantic import BaseModel, EmailStr
from typing import Dict, List, Optional

# --- Auth Schemas ---
class UserAuthSchema(BaseModel):
    email: EmailStr
    password: str

# --- Admin Flight Schemas ---
class FlightCreateSchema(BaseModel):
    flight_number: str
    origin: str
    destination: str
    departure_time: str  # e.g. "2026-06-15T10:00:00Z"
    total_capacity: int
    seats: Dict[str, int]   # e.g. {"ECONOMY": 50, "BUSINESS": 30, "FIRST": 20}
    prices: Dict[str, float] # e.g. {"ECONOMY": 120.0, "BUSINESS": 350.0, "FIRST": 700.0}

class FlightScheduleUpdateSchema(BaseModel):
    departure_time: str

# --- Booking Schemas ---
class PassengerItem(BaseModel):
    passenger_name: str
    passenger_email: EmailStr

class GroupBookingSchema(BaseModel):
    flight_id: str
    seat_class: str
    fare_type: str = "BASIC"  # Options: "BASIC" ya "FLEX"
    passengers: List[PassengerItem]

class WaitlistCreateSchema(BaseModel):
    flight_id: str
    seat_class: str
    passenger_email: EmailStr
    priority: int = 1  # 1 for standard, 2 for loyalty/VIP