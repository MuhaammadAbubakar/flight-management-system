from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from schemas import SupportTicketCreate

router = APIRouter(prefix="/api/support", tags=["Customer Support"])

@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_support_ticket(payload: SupportTicketCreate, db: Session = Depends(get_db)):
    try:
        query = text("""
            INSERT INTO support_tickets (customer_email, flight_number, customer_query, status)
            VALUES (:email, :fn, :query, 'PENDING_APPROVAL')
            RETURNING id, created_at;
        """)
        result = db.execute(query, {
            "email": payload.customer_email.lower(),
            "fn": payload.flight_number.upper(),
            "query": payload.customer_query.strip()
        }).fetchone()

        db.commit()

        return {
            "status": "SUCCESS",
            "ticket_id": str(result[0]),
            "created_at": str(result[1]),
            "message": f"Support ticket #{str(result[0])[:8]} created successfully! Our team will get back to you shortly."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tickets/{email}")
def get_support_tickets_by_email(email: str, db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT id, flight_number, customer_query, ai_draft_response, status, created_at
            FROM support_tickets
            WHERE LOWER(customer_email) = LOWER(:email)
            ORDER BY created_at DESC;
        """)
        rows = db.execute(query, {"email": email}).fetchall()
        tickets = []
        for r in rows:
            tickets.append({
                "id": str(r[0]),
                "flight_number": r[1],
                "customer_query": r[2],
                "ai_draft_response": r[3],
                "status": r[4],
                "created_at": str(r[5])
            })
        return {"email": email.lower(), "count": len(tickets), "tickets": tickets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
