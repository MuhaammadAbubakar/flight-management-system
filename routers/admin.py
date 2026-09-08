from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from database import get_db
from schemas import FlightCreateSchema, FlightScheduleUpdateSchema
from auth import verify_super_admin, verify_ops_or_admin

router = APIRouter(prefix="/admin", tags=["Admin Operations"])

# 1. FLIGHT CREATE WITH AUDIT
@router.post("/flights")
def create_flight(
    data: FlightCreateSchema, 
    db: Session = Depends(get_db),
    admin_user: dict = Depends(verify_super_admin)
):
    if sum(data.seats.values()) != data.total_capacity:
        raise HTTPException(status_code=400, detail = "Total seats are not equal to total capacity!")

    for s_class, count in data.seats.items():
        if count <= 0:
            raise HTTPException(status_code=400, detail=f"Class {s_class} mein seat count zero ya negative nahi ho sakta!")

    try:
        # Duplicate check
        check_query = text("SELECT id FROM flights WHERE UPPER(flight_number) = UPPER(:fn) AND departure_time = :dep;")
        if db.execute(check_query, {"fn": data.flight_number, "dep": data.departure_time}).fetchone():
            raise HTTPException(status_code=400, detail="Yeh flight is date/time par pehle se mojood hai!")

        # Flight insertion
        flight_sql = text("""
            INSERT INTO flights (flight_number, origin, destination, departure_time, total_capacity)
            VALUES (:fn, :orig, :dest, :dep, :cap)
            RETURNING id;
        """)
        flight_id = db.execute(flight_sql, {
            "fn":   data.flight_number.upper(),   # Always uppercase
            "orig": data.origin.upper(),            # Always uppercase
            "dest": data.destination.upper(),       # Always uppercase
            "dep":  data.departure_time,
            "cap":  data.total_capacity
        }).scalar()

        # Normalize prices keys to uppercase (case-insensitive match)
        prices_normalized = {k.upper(): v for k, v in data.prices.items()}

        for s_class, count in data.seats.items():
            db.execute(text("""
                INSERT INTO seat_inventory (flight_id, seat_class, total_seats, price)
                VALUES (:fid, :cls, :total, :price);
            """), {
                "fid": flight_id, "cls": s_class.upper(),
                "total": count, "price": prices_normalized.get(s_class.upper(), 100.0)
            })

        # AUDIT LOG INSERTION
        db.execute(text("""
            INSERT INTO audit_logs (actor_email, action, target_flight_id, details)
            VALUES (:actor, 'CREATE_FLIGHT', :fid, :det);
        """), {
            "actor": admin_user["email"],
            "fid": flight_id,
            "det": json.dumps({"flight_number": data.flight_number, "seats": data.seats})
        })

        db.commit()
        return {"status": "SUCCESS", "flight_id": str(flight_id), "created_by": admin_user["email"]}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# 2. FLIGHT CANCELLATION WITH AUDIT
@router.post("/flights/{flight_number}/cancel")
def cancel_flight(
    flight_number: str, 
    db: Session = Depends(get_db),
    admin_user: dict = Depends(verify_super_admin)
):
    try:
        res = db.execute(text("""
            UPDATE flights 
            SET status = 'CANCELLED' 
            WHERE UPPER(flight_number) = UPPER(:fid)
            RETURNING id;
        """), {"fid": flight_number}).fetchone()

        if not res:
            raise HTTPException(status_code=404, detail="Flight record nahi mila!")

        flight_uuid = res[0]

        # Cascade: is flight ki saari CONFIRMED bookings bhi cancel karo
        db.execute(text("""
            UPDATE bookings SET status = 'CANCELLED'
            WHERE flight_id = :fid AND status = 'CONFIRMED';
        """), {"fid": flight_uuid})

        # AUDIT LOG ENTRY
        db.execute(text("""
            INSERT INTO audit_logs (actor_email, action, target_flight_id, details)
            VALUES (:actor, 'CANCEL_FLIGHT', :fid, :det);
        """), {
            "actor": admin_user["email"],
            "fid": flight_uuid,  # Pass UUID, not flight_number string
            "det": json.dumps({"reason": "Operational cancellation"})
        })

        db.commit()
        return {"status": "SUCCESS", "message": "Flight cancelled. Downstream refund flows unlocked."}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# 3. FLIGHT SCHEDULE UPDATE
@router.patch("/flights/{flight_number}/schedule")
def update_flight_schedule(
    flight_number: str, 
    data: FlightScheduleUpdateSchema, 
    db: Session = Depends(get_db),
    agent_user: dict = Depends(verify_ops_or_admin)
):
    try:
        res = db.execute(text("""
            UPDATE flights 
            SET departure_time = :dep 
            WHERE UPPER(flight_number) = UPPER(:fn) AND status = 'SCHEDULED'
            RETURNING id;
        """), {"dep": data.departure_time, "fn": flight_number}).fetchone()

        if not res:
            raise HTTPException(status_code=404, detail="Flight record nahi mila ya cancelled hai!")

        flight_uuid = res[0]  # UUID returned by RETURNING id

        # AUDIT LOG
        db.execute(text("""
            INSERT INTO audit_logs (actor_email, action, target_flight_id, details)
            VALUES (:actor, 'UPDATE_SCHEDULE', :fid, :det);
        """), {
            "actor": agent_user["email"],
            "fid": flight_uuid,  # Pass UUID, not flight_number string
            "det": json.dumps({"new_departure": data.departure_time.isoformat()})
        })

        db.commit()
        return {"status": "SUCCESS", "message": "Schedule updated successfully"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flights")
def get_all_admin_flights(
    db: Session = Depends(get_db),
    agent_user: dict = Depends(verify_ops_or_admin)
):
    """Admin/Ops panel ke liye saari flights (scheduled & cancelled) with inventory data"""
    flights_query = text("""
        SELECT f.id, f.flight_number, f.origin, f.destination, f.departure_time,
               f.total_capacity, f.status,
               s.seat_class, s.total_seats, COALESCE(s.booked_seats, 0) as booked_seats, s.price
        FROM flights f
        LEFT JOIN seat_inventory s ON f.id = s.flight_id
        ORDER BY f.created_at DESC;
    """)
    rows = db.execute(flights_query).fetchall()

    flight_map = {}
    for r in rows:
        fid = str(r[0])
        if fid not in flight_map:
            flight_map[fid] = {
                "flight_id": fid,
                "flight_number": r[1],
                "origin": r[2],
                "destination": r[3],
                "departure_time": str(r[4]),
                "total_capacity": r[5],
                "status": r[6],
                "classes": []
            }
        if r[7]:  # seat_class exists
            flight_map[fid]["classes"].append({
                "seat_class": r[7],
                "total_seats": r[8],
                "booked_seats": r[9],
                "available_seats": r[8] - r[9],
                "price": float(r[10])
            })

    return {"admin_email": agent_user["email"], "role": agent_user["role"], "flights": list(flight_map.values())}