from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/flights", tags=["Search Operations"])


@router.get("/all")
def get_all_flights(db: Session = Depends(get_db)):
    """Frontend ke liye saari scheduled flights list karein"""
    query = text("""
        SELECT f.id, f.flight_number, f.origin, f.destination, f.departure_time,
               s.seat_class, (s.total_seats - COALESCE(s.booked_seats, 0)) as available_seats, s.price
        FROM flights f
        JOIN seat_inventory s ON f.id = s.flight_id
        WHERE f.status = 'SCHEDULED'
        ORDER BY f.departure_time ASC;
    """)
    rows = db.execute(query).fetchall()
    results = []
    for r in rows:
        results.append({
            "flight_id": str(r[0]),
            "flight_number": r[1],
            "origin": r[2],
            "destination": r[3],
            "departure_time": str(r[4]),
            "seat_class": r[5],
            "available_seats": r[6],
            "price": float(r[7])
        })
    return {"flights": results}


@router.get("/cities")
def get_flight_cities(db: Session = Depends(get_db)):
    """Unique origins aur destinations fetch karein for search dropdowns"""
    origins = [r[0] for r in db.execute(text("SELECT DISTINCT origin FROM flights WHERE status='SCHEDULED'")).fetchall()]
    destinations = [r[0] for r in db.execute(text("SELECT DISTINCT destination FROM flights WHERE status='SCHEDULED'")).fetchall()]
    all_cities = sorted(list(set(origins + destinations)))
    return {"origins": sorted(origins), "destinations": sorted(destinations), "cities": all_cities}


@router.get("/search")
def search_flights(origin: str, destination: str, db: Session = Depends(get_db)):
    query = text("""
        SELECT f.id, f.flight_number, f.origin, f.destination, f.departure_time,
               s.seat_class, (s.total_seats - COALESCE(s.booked_seats, 0)) as available_seats, s.price
        FROM flights f
        JOIN seat_inventory s ON f.id = s.flight_id
        WHERE UPPER(f.origin) = UPPER(:orig) AND UPPER(f.destination) = UPPER(:dest) AND f.status = 'SCHEDULED'
          AND (s.total_seats - COALESCE(s.booked_seats, 0)) > 0;
    """)
    rows = db.execute(query, {"orig": origin, "dest": destination}).fetchall()

    results = []
    for r in rows:
        results.append({
            "flight_id": str(r[0]),
            "flight_number": r[1],
            "origin": r[2],
            "destination": r[3],
            "departure_time": str(r[4]),
            "seat_class": r[5],
            "available_seats": r[6],
            "price": float(r[7])
        })
    return {"available_flights": results}


@router.get("/{flight_number}/prices")
def get_flight_prices(flight_number: str, db: Session = Depends(get_db)):
    """Book karne se pehle flight ki har class ki price check karo"""
    rows = db.execute(text("""
        SELECT s.seat_class, s.price,
               (s.total_seats - COALESCE(s.booked_seats, 0)) as available_seats
        FROM flights f
        JOIN seat_inventory s ON f.id = s.flight_id
        WHERE UPPER(f.flight_number) = UPPER(:fn) AND f.status = 'SCHEDULED'
        ORDER BY s.price ASC;
    """), {"fn": flight_number}).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Flight '{flight_number}' nahi mili ya scheduled nahi hai!")

    return {
        "flight_number": flight_number.upper(),
        "pricing": [
            {
                "seat_class": r[0],
                "price_per_seat": float(r[1]),
                "available_seats": r[2]
            }
            for r in rows
        ]
    }