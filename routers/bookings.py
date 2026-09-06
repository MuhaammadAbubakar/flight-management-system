from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from database import get_db
from schemas import GroupBookingSchema, WaitlistCreateSchema

router = APIRouter(prefix="/bookings", tags=["Bookings & Waitlist"])

@router.post("")
def create_booking(
    payload: GroupBookingSchema, 
    x_idempotency_key: str = Header(None), 
    db: Session = Depends(get_db)
):
    # 1. Idempotency Check
    if x_idempotency_key:
        cached = db.execute(
            text("SELECT response FROM idempotency_keys WHERE key = :k"),
            {"k": x_idempotency_key}
        ).fetchone()
        if cached:
            return cached[0]

    seat_count = len(payload.passengers)
    if seat_count <= 0:
        raise HTTPException(status_code=400, detail="Kam az kam ek passenger hona zaroori hai!")

    try:
        # 2. ATOMIC SEAT ALLOCATION (FULL FAIL POLICY)
        # Agar pure group ke liye seats na hui toh 0 row update hogi aur fail ho jayega
        seat_update = db.execute(text("""
            UPDATE seat_inventory 
            SET booked_seats = booked_seats + :cnt 
            WHERE flight_id = :fid 
              AND seat_class = :cls 
              AND (total_seats - booked_seats) >= :cnt
            RETURNING id;
        """), {
            "fid": payload.flight_id, 
            "cls": payload.seat_class.upper(),
            "cnt": seat_count
        }).fetchone()

        if not seat_update:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Class full ho chuki hai ya {seat_count} seats aik sath available nahi hain! Waitlist join karein."
            )

        # 3. Passenger Bookings Insert
        booking_ids = []
        for p in payload.passengers:
            b_id = db.execute(text("""
                INSERT INTO bookings (flight_id, seat_class, passenger_name, passenger_email, fare_type)
                VALUES (:fid, :cls, :name, :email, :fare)
                RETURNING id;
            """), {
                "fid": payload.flight_id,
                "cls": payload.seat_class.upper(),
                "name": p.passenger_name,
                "email": p.passenger_email,
                "fare": payload.fare_type
            }).scalar()
            booking_ids.append(str(b_id))

        db.commit()

        result = {
            "status": "CONFIRMED",
            "booking_ids": booking_ids,
            "flight_id": payload.flight_id,
            "seat_class": payload.seat_class.upper(),
            "total_booked": seat_count
        }

        # Idempotency response save
        if x_idempotency_key:
            db.execute(text("""
                INSERT INTO idempotency_keys (key, response) 
                VALUES (:k, :resp);
            """), {"k": x_idempotency_key, "resp": json.dumps(result)})
            db.commit()

        return result

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/waitlist")
def join_waitlist(payload: WaitlistCreateSchema, db: Session = Depends(get_db)):
    try:
        res = db.execute(text("""
            INSERT INTO waitlist (flight_id, seat_class, passenger_email, priority)
            VALUES (:fid, :cls, :email, :prio)
            RETURNING id;
        """), {
            "fid": payload.flight_id,
            "cls": payload.seat_class.upper(),
            "email": payload.passenger_email,
            "prio": payload.priority
        }).fetchone()

        db.commit()
        return {"status": "WAITLISTED", "waitlist_id": str(res[0])}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))