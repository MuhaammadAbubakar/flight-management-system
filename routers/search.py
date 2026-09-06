from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/flights", tags=["Search Operations"])

@router.get("/search")
def search_flights(origin: str, destination: str, db: Session = Depends(get_db)):
    query = text("""
        SELECT f.id, f.flight_number, f.origin, f.destination, f.departure_time,
               s.seat_class, (s.total_seats - s.booked_seats) as available_seats, s.price
        FROM flights f
        JOIN seat_inventory s ON f.id = s.flight_id
        WHERE f.origin = :orig AND f.destination = :dest AND f.status = 'SCHEDULED'
          AND (s.total_seats - s.booked_seats) > 0;
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