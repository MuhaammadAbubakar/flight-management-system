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
        raise HTTPException(status_code=400, detail="Seat allocation sum total capacity ke barabar hona chahiye!")

    for s_class, count in data.seats.items():
        if count <= 0:
            raise HTTPException(status_code=400, detail=f"Class {s_class} mein seat count zero ya negative nahi ho sakta!")

    try:
        # Duplicate check
        check_query = text("SELECT id FROM flights WHERE flight_number = :fn AND departure_time = :dep;")
        if db.execute(check_query, {"fn": data.flight_number, "dep": data.departure_time}).fetchone():
            raise HTTPException(status_code=400, detail="Yeh flight is date/time par pehle se mojood hai!")

        # Flight insertion
        flight_sql = text("""
            INSERT INTO flights (flight_number, origin, destination, departure_time, total_capacity)
            VALUES (:fn, :orig, :dest, :dep, :cap)
            RETURNING id;
        """)
        flight_id = db.execute(flight_sql, {
            "fn": data.flight_number, "orig": data.origin,
            "dest": data.destination, "dep": data.departure_time, "cap": data.total_capacity
        }).scalar()

        for s_class, count in data.seats.items():
            db.execute(text("""
                INSERT INTO seat_inventory (flight_id, seat_class, total_seats, price)
                VALUES (:fid, :cls, :total, :price);
            """), {
                "fid": flight_id, "cls": s_class.upper(),
                "total": count, "price": data.prices.get(s_class, 100.0)
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
@router.post("/flights/{flight_id}/cancel")
def cancel_flight(
    flight_id: str, 
    db: Session = Depends(get_db),
    admin_user: dict = Depends(verify_super_admin)
):
    try:
        res = db.execute(text("""
            UPDATE flights 
            SET status = 'CANCELLED' 
            WHERE id = :fid
            RETURNING id;
        """), {"fid": flight_id}).fetchone()

        if not res:
            raise HTTPException(status_code=404, detail="Flight record nahi mila!")

        # AUDIT LOG ENTRY
        db.execute(text("""
            INSERT INTO audit_logs (actor_email, action, target_flight_id, details)
            VALUES (:actor, 'CANCEL_FLIGHT', :fid, :det);
        """), {
            "actor": admin_user["email"],
            "fid": flight_id,
            "det": json.dumps({"reason": "Operational cancellation"})
        })

        db.commit()
        return {"status": "SUCCESS", "message": "Flight cancelled. Downstream refund flows unlocked."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# 3. FLIGHT SCHEDULE UPDATE
@router.patch("/flights/{flight_id}/schedule")
def update_flight_schedule(
    flight_id: str, 
    data: FlightScheduleUpdateSchema, 
    db: Session = Depends(get_db),
    agent_user: dict = Depends(verify_ops_or_admin)
):
    try:
        res = db.execute(text("""
            UPDATE flights 
            SET departure_time = :dep 
            WHERE id = :fid AND status = 'SCHEDULED'
            RETURNING id;
        """), {"dep": data.departure_time, "fid": flight_id}).fetchone()

        if not res:
            raise HTTPException(status_code=404, detail="Flight record nahi mila ya cancelled hai!")

        # AUDIT LOG
        db.execute(text("""
            INSERT INTO audit_logs (actor_email, action, target_flight_id, details)
            VALUES (:actor, 'UPDATE_SCHEDULE', :fid, :det);
        """), {
            "actor": agent_user["email"],
            "fid": flight_id,
            "det": json.dumps({"new_departure": data.departure_time})
        })

        db.commit()
        return {"status": "SUCCESS", "message": "Schedule updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))