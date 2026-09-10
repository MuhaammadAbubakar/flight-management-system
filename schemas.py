from pydantic import BaseModel, EmailStr, field_validator
from typing import Dict, List, Optional
from typing import Literal
from datetime import datetime
from dateutil import parser as dtparser

# --- Auth Schemas ---
class UserAuthSchema(BaseModel):
    email: EmailStr
    password: str

# --- Admin Flight Schemas ---
class FlightCreateSchema(BaseModel):
    flight_number: str
    origin: str
    destination: str
    departure_time: datetime  # e.g. "2026-06-15T10:00:00Z" or "2026-12-10 15:16:15+00"
    total_capacity: int
    seats: Dict[str, int]    # e.g. {"ECONOMY": 50, "BUSINESS": 30, "FIRST": 20}
    prices: Dict[str, float] # e.g. {"ECONOMY": 120.0, "BUSINESS": 350.0, "FIRST": 700.0}

    @field_validator("departure_time", mode="before")
    @classmethod
    def parse_departure_time(cls, v):
        if isinstance(v, str):
            try:
                return dtparser.parse(v)
            except Exception:
                raise ValueError(f"Invalid datetime format: '{v}'. Example: '2026-06-15T10:00:00Z'")
        return v

class FlightScheduleUpdateSchema(BaseModel):
    departure_time: datetime

    @field_validator("departure_time", mode="before")
    @classmethod
    def parse_departure_time(cls, v):
        if isinstance(v, str):
            try:
                return dtparser.parse(v)
            except Exception:
                raise ValueError(f"Invalid datetime format: '{v}'. Example: '2026-06-15T10:00:00Z'")
        return v

# --- Booking Schemas ---
class PassengerItem(BaseModel):
    passenger_name: str
    passenger_email: EmailStr

class GroupBookingSchema(BaseModel):
    flight_number: str                              # e.g. "PK500" or "pk500"
    seat_class: Literal["ECONOMY", "BUSINESS", "FIRST"]
    fare_type: Literal["BASIC", "FLEX"] = "BASIC"
    seat_count: int = 1                             # Kitni seats chahiye (min 1)
    passengers: List[PassengerItem]                 # Kam az kam 1 passenger detail zaroori

    # --- Case normalization BEFORE Pydantic validates Literal fields ---
    @field_validator("seat_class", "fare_type", mode="before")
    @classmethod
    def uppercase_str_fields(cls, v):
        return v.upper() if isinstance(v, str) else v

    @field_validator("seat_count")
    @classmethod
    def validate_seat_count(cls, v):
        if v < 1:
            raise ValueError("seat_count kam az kam 1 hona chahiye!")
        return v

    @field_validator("passengers")
    @classmethod
    def validate_passengers_match(cls, v, info):
        seat_count = info.data.get("seat_count", 1)
        if len(v) < 1:
            raise ValueError("Kam az kam 1 passenger ki detail zaroori hai!")
        if len(v) > seat_count:
            raise ValueError(
                f"Passengers ki tadaad ({len(v)}) seat_count ({seat_count}) se zyada nahi ho sakti!"
            )
        return v

class WaitlistCreateSchema(BaseModel):
    flight_number: str                              # e.g. "PK500"
    seat_class: Literal["ECONOMY", "BUSINESS", "FIRST"]
    fare_type: Literal["BASIC", "FLEX"] = "BASIC"   # BASIC or FLEX fare preference
    passenger_email: EmailStr
    priority: int = 1  # 1 for standard, 2 for loyalty/VIP

    @field_validator("flight_number", mode="before")
    @classmethod
    def uppercase_flight_number(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("seat_class", "fare_type", mode="before")
    @classmethod
    def uppercase_enum_fields(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


# --- Cancellation Schema ---
class CancelBookingSchema(BaseModel):
    flight_number: str                                       # e.g. "PK500"
    passenger_email: EmailStr                                # Jis passenger ki booking cancel karni hai
    seat_class: Literal["ECONOMY", "BUSINESS", "FIRST"]      # Konsi class
    seats_to_cancel: int = 1                                 # Kitni seats cancel karni hain
    fare_type: Optional[Literal["BASIC", "FLEX"]] = None     # Optional: BASIC ya FLEX cancel karo

    @field_validator("seat_class", "fare_type", mode="before")
    @classmethod
    def uppercase_enum_fields(cls, v):
        return v.upper() if isinstance(v, str) else v

    @field_validator("seats_to_cancel")
    @classmethod
    def validate_cancel_count(cls, v):
        if v < 1:
            raise ValueError("seats_to_cancel kam az kam 1 honi chahiye!")
        return v


# --- Support Ticket Schema ---
class SupportTicketCreate(BaseModel):
    customer_email: EmailStr
    flight_number: str
    customer_query: str

    @field_validator("flight_number", mode="before")
    @classmethod
    def uppercase_flight_num(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("customer_email", mode="before")
    @classmethod
    def lowercase_email(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("customer_query")
    @classmethod
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError("customer_query cannot be empty!")
        return v.strip()