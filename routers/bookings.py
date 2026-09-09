from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from database import get_db
from schemas import GroupBookingSchema, WaitlistCreateSchema, CancelBookingSchema

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
            cached_data = cached[0]
            # Same key, same request → return cached (idempotent)
            # Same key, different request → 409 Conflict
            if (cached_data.get("flight_number") != payload.flight_number.upper() or
                cached_data.get("fare_type") != payload.fare_type):
                raise HTTPException(
                    status_code=409,
                    detail="Yeh idempotency key pehle alag request ke liye use ho chuki hai. Naya unique key use karein."
                )
            return cached_data

    seat_count = payload.seat_count
    if seat_count < 1:
        raise HTTPException(status_code=400, detail="Kam az kam ek seat honi chahiye!")

    try:
        # Flight number se UUID resolve karo
        flight = db.execute(
            text("SELECT id FROM flights WHERE UPPER(flight_number) = UPPER(:fn) AND status = 'SCHEDULED';"),
            {"fn": payload.flight_number}
        ).fetchone()
        if not flight:
            raise HTTPException(status_code=404, detail=f"Flight '{payload.flight_number}' nahi mili ya scheduled nahi hai!")
        flight_uuid = flight[0]

        # 2. Available seats check — specific error message ke liye
        avail_row = db.execute(text("""
            SELECT (total_seats - COALESCE(booked_seats, 0)) as available
            FROM seat_inventory
            WHERE flight_id = :fid AND seat_class = :cls;
        """), {"fid": flight_uuid, "cls": payload.seat_class.upper()}).fetchone()

        if not avail_row:
            raise HTTPException(
                status_code=404,
                detail=f"Is flight mein '{payload.seat_class}' class exist nahi karti!"
            )

        available = avail_row[0]
        if available == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{payload.seat_class} class bilkul full ho chuki hai! Waitlist join karein."
            )
        if available < seat_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sirf {available} seat(s) available hain, aapne {seat_count} maangi hain. "
                       f"Seat count {available} ya usse kam karein, ya waitlist join karein."
            )

        # 3. ATOMIC SEAT ALLOCATION
        seat_update = db.execute(text("""
            UPDATE seat_inventory 
            SET booked_seats = COALESCE(booked_seats, 0) + :cnt 
            WHERE flight_id = :fid 
              AND seat_class = :cls 
              AND (total_seats - COALESCE(booked_seats, 0)) >= :cnt
            RETURNING id;
        """), {
            "fid": flight_uuid, 
            "cls": payload.seat_class.upper(),
            "cnt": seat_count
        }).fetchone()

        if not seat_update:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seats allocate nahi ho sakin. Dobara try karein."
            )

        # 3. Price fetch karo seat_inventory se
        price_row = db.execute(text("""
            SELECT price FROM seat_inventory
            WHERE flight_id = :fid AND seat_class = :cls;
        """), {"fid": flight_uuid, "cls": payload.seat_class.upper()}).fetchone()
        base_price = float(price_row[0]) if price_row else 0.0

        # Fare type multiplier:
        # BASIC → base price (no flexibility)
        # FLEX  → 30% mehnga, lekin changes/refunds allowed
        FARE_MULTIPLIERS = {"BASIC": 1.0, "FLEX": 1.30}
        multiplier = FARE_MULTIPLIERS.get(payload.fare_type, 1.0)
        price_per_seat = round(base_price * multiplier, 2)
        total_fare = round(price_per_seat * seat_count, 2)

        # 4. Passenger Bookings Insert
        # seat_count seats book honge — jitni details hain unke naam/email, baqi TBD
        booking_ids = []
        for i in range(seat_count):
            if i < len(payload.passengers):
                p = payload.passengers[i]
                pname = p.passenger_name
                pemail = p.passenger_email.lower()   # Always lowercase
            else:
                pname  = "TBD"
                pemail = f"tbd+seat{i+1}@pending.local"

            b_id = db.execute(text("""
                INSERT INTO bookings (flight_id, seat_class, passenger_name, passenger_email, fare_type)
                VALUES (:fid, :cls, :name, :email, :fare)
                RETURNING id;
            """), {
                "fid": flight_uuid,
                "cls": payload.seat_class.upper(),
                "name": pname,
                "email": pemail,
                "fare": payload.fare_type
            }).scalar()
            booking_ids.append(str(b_id))

        result = {
            "status": "CONFIRMED",
            "booking_ids": booking_ids,
            "flight_number": payload.flight_number.upper(),
            "seat_class": payload.seat_class.upper(),
            "fare_type": payload.fare_type,
            "fare_note": "No changes/refunds" if payload.fare_type == "BASIC" else "Changes & refunds allowed (+30%)",
            "base_price_per_seat": base_price,
            "price_per_seat": price_per_seat,
            "total_fare": total_fare,
            "total_booked": seat_count
        }

        # Save idempotency key IN SAME TRANSACTION (atomicity)
        if x_idempotency_key:
            db.execute(text("""
                INSERT INTO idempotency_keys (key, response) 
                VALUES (:k, :resp);
            """), {"k": x_idempotency_key, "resp": json.dumps(result)})

        db.commit()  # Single commit — booking + idempotency key atomic
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
        # Flight number se UUID resolve karo
        flight = db.execute(
            text("SELECT id, flight_number FROM flights WHERE UPPER(flight_number) = UPPER(:fn);"),
            {"fn": payload.flight_number}
        ).fetchone()
        if not flight:
            raise HTTPException(status_code=404, detail=f"Flight '{payload.flight_number}' nahi mili!")

        # Duplicate waitlist check (same flight, class, fare_type, email aur WAITING status)
        existing = db.execute(text("""
            SELECT id FROM waitlist
            WHERE flight_id = :fid
              AND UPPER(seat_class) = UPPER(:cls)
              AND UPPER(COALESCE(fare_type, 'BASIC')) = UPPER(:fare)
              AND LOWER(passenger_email) = LOWER(:email)
              AND (status IS NULL OR status = 'WAITING');
        """), {
            "fid": flight[0],
            "cls": payload.seat_class,
            "fare": payload.fare_type,
            "email": payload.passenger_email
        }).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"'{payload.passenger_email}' pehle se {payload.flight_number} - {payload.seat_class} ({payload.fare_type}) ki waitlist mein hai!"
            )

        res = db.execute(text("""
            INSERT INTO waitlist (flight_id, seat_class, fare_type, passenger_email, priority, status)
            VALUES (:fid, :cls, :fare, :email, :prio, 'WAITING')
            RETURNING id;
        """), {
            "fid": flight[0],
            "cls": payload.seat_class.upper(),
            "fare": payload.fare_type.upper(),
            "email": payload.passenger_email.lower(),   # Always lowercase
            "prio": payload.priority
        }).fetchone()

        db.commit()
        return {
            "status": "WAITLISTED",
            "waitlist_id": str(res[0]),
            "flight_number": payload.flight_number.upper(),
            "seat_class": payload.seat_class.upper(),
            "fare_type": payload.fare_type.upper(),
            "priority": payload.priority
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel")
def cancel_booking(payload: CancelBookingSchema, db: Session = Depends(get_db)):
    """Passenger apni confirmed bookings cancel kar sakta hai"""
    try:
        # 1. Flight UUID resolve karo
        flight = db.execute(
            text("SELECT id FROM flights WHERE UPPER(flight_number) = UPPER(:fn);"),
            {"fn": payload.flight_number}
        ).fetchone()
        if not flight:
            raise HTTPException(status_code=404, detail=f"Flight '{payload.flight_number}' nahi mili!")
        flight_uuid = flight[0]

        # 2. Passenger ki CONFIRMED bookings dhundo (us class mein)
        fare_filter = "AND fare_type = :ft" if payload.fare_type else ""
        params = {
            "fid":   flight_uuid,
            "email": payload.passenger_email,
            "cls":   payload.seat_class.upper(),
            "cnt":   payload.seats_to_cancel
        }
        if payload.fare_type:
            params["ft"] = payload.fare_type

        bookings = db.execute(text(f"""
            SELECT id, fare_type
            FROM bookings
            WHERE flight_id    = :fid
              AND LOWER(passenger_email) = LOWER(:email)
              AND seat_class   = :cls
              AND status       = 'CONFIRMED'
              {fare_filter}
            ORDER BY created_at ASC
            LIMIT :cnt;
        """), params).fetchall()

        if not bookings:
            fare_msg = f" ({payload.fare_type})" if payload.fare_type else ""
            raise HTTPException(
                status_code=404,
                detail=f"'{payload.passenger_email}' ki koi confirmed{fare_msg} booking nahi mili "
                       f"{payload.flight_number} - {payload.seat_class} mein!"
            )

        if len(bookings) < payload.seats_to_cancel:
            raise HTTPException(
                status_code=400,
                detail=f"Aap ne {payload.seats_to_cancel} seats cancel karni chahein lekin "
                       f"sirf {len(bookings)} confirmed booking(s) mili hain!"
            )

        # 3. Bookings CANCELLED mark karo (har ek ko individually)
        cancelled_ids = [str(b[0]) for b in bookings]
        fare_types    = [b[1] for b in bookings]

        for bid in cancelled_ids:
            db.execute(
                text("UPDATE bookings SET status = 'CANCELLED' WHERE id = :bid"),
                {"bid": bid}
            )

        # 4. Waitlist Auto-Allocation Engine:
        # Jab koi seat cancel hoti hai, waitlist se matching candidates choose karo
        promoted_passengers = []
        for cancelled_fare in fare_types:
            # 1st Priority: Exact match on flight, cabin class, fare_type, status='WAITING'
            candidate = db.execute(text("""
                SELECT id, passenger_email, priority, COALESCE(fare_type, 'BASIC') as fare_type
                FROM waitlist
                WHERE flight_id = :fid
                  AND UPPER(seat_class) = UPPER(:cls)
                  AND UPPER(COALESCE(fare_type, 'BASIC')) = UPPER(:fare)
                  AND (status IS NULL OR status = 'WAITING')
                ORDER BY priority DESC, created_at ASC
                LIMIT 1;
            """), {
                "fid": flight_uuid,
                "cls": payload.seat_class.upper(),
                "fare": cancelled_fare
            }).fetchone()

            # 2nd Priority: Agar exact fare_type candidate nahi mila, to same flight & class ka any waiting candidate
            if not candidate:
                candidate = db.execute(text("""
                    SELECT id, passenger_email, priority, COALESCE(fare_type, 'BASIC') as fare_type
                    FROM waitlist
                    WHERE flight_id = :fid
                      AND UPPER(seat_class) = UPPER(:cls)
                      AND (status IS NULL OR status = 'WAITING')
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1;
                """), {
                    "fid": flight_uuid,
                    "cls": payload.seat_class.upper()
                }).fetchone()

            if candidate:
                w_id, cand_email, cand_prio, cand_fare = candidate[0], candidate[1], candidate[2], candidate[3]

                # Update waitlist status to PROMOTED
                db.execute(text("""
                    UPDATE waitlist
                    SET status = 'PROMOTED'
                    WHERE id = :wid;
                """), {"wid": w_id})

                # Create CONFIRMED booking for promoted passenger
                p_name = cand_email.split('@')[0].replace('.', ' ').title()
                allocated_fare = cand_fare or cancelled_fare

                new_booking_id = db.execute(text("""
                    INSERT INTO bookings (flight_id, seat_class, passenger_name, passenger_email, fare_type, status)
                    VALUES (:fid, :cls, :name, :email, :fare, 'CONFIRMED')
                    RETURNING id;
                """), {
                    "fid": flight_uuid,
                    "cls": payload.seat_class.upper(),
                    "name": p_name,
                    "email": cand_email.lower(),
                    "fare": allocated_fare
                }).scalar()

                promoted_passengers.append({
                    "waitlist_id": str(w_id),
                    "passenger_email": cand_email,
                    "passenger_name": p_name,
                    "seat_class": payload.seat_class.upper(),
                    "fare_type": allocated_fare,
                    "priority": cand_prio,
                    "new_booking_id": str(new_booking_id),
                    "note": f"Auto-promoted from waitlist queue (Priority {cand_prio})"
                })

        # Net seats released = cancelled seats minus those directly allocated to waitlist
        net_seats_released = payload.seats_to_cancel - len(promoted_passengers)
        if net_seats_released > 0:
            db.execute(text("""
                UPDATE seat_inventory
                SET booked_seats = GREATEST(COALESCE(booked_seats, 0) - :cnt, 0)
                WHERE flight_id = :fid AND seat_class = :cls;
            """), {
                "cnt": net_seats_released,
                "fid": flight_uuid,
                "cls": payload.seat_class.upper()
            })

        db.commit()

        # 5. Base price fetch karo refund calculate karne ke liye
        price_row = db.execute(text("""
            SELECT price FROM seat_inventory
            WHERE flight_id = :fid AND seat_class = :cls;
        """), {"fid": flight_uuid, "cls": payload.seat_class.upper()}).fetchone()
        base_price = float(price_row[0]) if price_row else 0.0

        flex_price  = round(base_price * 1.30, 2)   # Jitna FLEX mein pay kiya tha
        basic_price = base_price                     # Jitna BASIC mein pay kiya tha

        # 6. Refund policy aur amount (fare_type ke hisaab se)
        flex_cancelled  = sum(1 for ft in fare_types if ft == "FLEX")
        basic_cancelled = sum(1 for ft in fare_types if ft == "BASIC")

        refund_breakdown = []
        total_refund = 0.0

        if flex_cancelled:
            flex_refund = round(flex_price * flex_cancelled, 2)
            total_refund += flex_refund
            refund_breakdown.append({
                "fare_type": "FLEX",
                "seats": flex_cancelled,
                "price_paid_per_seat": flex_price,
                "refund_per_seat": flex_price,
                "subtotal_refund": flex_refund,
                "note": "Full refund — FLEX ticket"
            })
        if basic_cancelled:
            refund_breakdown.append({
                "fare_type": "BASIC",
                "seats": basic_cancelled,
                "price_paid_per_seat": basic_price,
                "refund_per_seat": 0.0,
                "subtotal_refund": 0.0,
                "note": "No refund — non-refundable BASIC ticket"
            })

        # 7. Remaining confirmed seats check (class aur fare_type ke hisaab se)
        remaining = db.execute(text("""
            SELECT seat_class, fare_type, COUNT(*) as cnt
            FROM bookings
            WHERE flight_id = :fid
              AND LOWER(passenger_email) = LOWER(:email)
              AND status = 'CONFIRMED'
            GROUP BY seat_class, fare_type;
        """), {"fid": flight_uuid, "email": payload.passenger_email}).fetchall()

        # Structure: { "BUSINESS": {"BASIC": 1, "FLEX": 2}, "ECONOMY": {...} }
        remaining_breakdown = {}
        total_remaining = 0
        for row in remaining:
            s_class, f_type, cnt = row[0], row[1], row[2]
            if s_class not in remaining_breakdown:
                remaining_breakdown[s_class] = {}
            remaining_breakdown[s_class][f_type] = cnt
            total_remaining += cnt

        return {
            "status": "CANCELLED",
            "cancelled_booking_ids": cancelled_ids,
            "flight_number": payload.flight_number.upper(),
            "seat_class": payload.seat_class.upper(),
            "seats_cancelled": payload.seats_to_cancel,
            "waitlist_promotions": promoted_passengers,
            "promoted_count": len(promoted_passengers),
            "refund": {
                "total_refund_amount": round(total_refund, 2),
                "breakdown": refund_breakdown
            },
            "remaining_confirmed_seats": {
                "total": total_remaining,
                "by_class": remaining_breakdown
            }
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/passenger/{email}")
def get_passenger_bookings(email: str, db: Session = Depends(get_db)):
    """Passenger ki saari bookings (confirmed & cancelled) aur active waitlist requests fetch karein"""
    query = text("""
        SELECT b.id, b.seat_class, b.passenger_name, b.passenger_email, 
               b.fare_type, b.status, b.created_at,
               f.flight_number, f.origin, f.destination, f.departure_time,
               COALESCE(s.price, 0) as base_price
        FROM bookings b
        JOIN flights f ON b.flight_id = f.id
        LEFT JOIN seat_inventory s ON s.flight_id = f.id AND s.seat_class = b.seat_class
        WHERE LOWER(b.passenger_email) = LOWER(:email)
        ORDER BY b.created_at DESC;
    """)
    rows = db.execute(query, {"email": email}).fetchall()

    bookings = []
    for r in rows:
        base_price = float(r[11])
        multiplier = 1.30 if r[4] == "FLEX" else 1.0
        final_price = round(base_price * multiplier, 2)
        bookings.append({
            "booking_id": str(r[0]),
            "seat_class": r[1],
            "passenger_name": r[2],
            "passenger_email": r[3],
            "fare_type": r[4],
            "status": r[5],
            "created_at": str(r[6]),
            "flight_number": r[7],
            "origin": r[8],
            "destination": r[9],
            "departure_time": str(r[10]),
            "price_paid": final_price
        })

    # Waitlist requests for this passenger
    waitlist_query = text("""
        SELECT w.id, w.seat_class, COALESCE(w.fare_type, 'BASIC') as fare_type,
               w.priority, COALESCE(w.status, 'WAITING') as status, w.created_at,
               f.flight_number, f.origin, f.destination, f.departure_time
        FROM waitlist w
        JOIN flights f ON w.flight_id = f.id
        WHERE LOWER(w.passenger_email) = LOWER(:email)
        ORDER BY w.created_at DESC;
    """)
    w_rows = db.execute(waitlist_query, {"email": email}).fetchall()
    waitlists = []
    for wr in w_rows:
        waitlists.append({
            "waitlist_id": str(wr[0]),
            "seat_class": wr[1],
            "fare_type": wr[2],
            "priority": wr[3],
            "status": wr[4],
            "created_at": str(wr[5]),
            "flight_number": wr[6],
            "origin": wr[7],
            "destination": wr[8],
            "departure_time": str(wr[9])
        })

    return {
        "email": email.lower(), 
        "count": len(bookings), 
        "bookings": bookings,
        "waitlist": waitlists
    }
