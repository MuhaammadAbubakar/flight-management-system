import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routers import admin, search, bookings, support
import auth
import schemas

app = FastAPI(
    title="Mera Safar - Flight Management System",
    description="Dual-writer transactional core & luxury flight booking portal",
    version="1.0.0",
    docs_url=None,     # Swagger UI disable
    redoc_url=None     # ReDoc disable
)

origins = [
    "https://merasafar.site.je",   
    "http://localhost:5173",
    "https://*.railway.app",
    "*"  # Development aur presentation ke waqt "*" har domain ko allow kar deta hai
]
# Enable CORS for browser frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers register karein
app.include_router(admin.router)
app.include_router(search.router)
app.include_router(bookings.router)
app.include_router(auth.router)
app.include_router(support.router)

# Direct alias for Admin Policy Ingestion (Vector Knowledge Base)
@app.post("/api/admin/policies/ingest")
async def ingest_policy_direct(payload: schemas.PolicyIngestionRequest):
    return await admin.ingest_policy_document(payload)

# Passenger AI Chatbot Assistant Endpoint
@app.post("/api/chat")
async def chat_with_bot(payload: schemas.ChatQueryRequest):
    """Chatbot query endpoint forwarding to n8n AI webhook or intelligent policy responder"""
    webhook_url = os.getenv("N8N_CHAT_WEBHOOK_URL", "http://localhost:5678/webhook/airline-chat")
    user_msg = payload.message.strip()

    # Attempt to send to n8n chatbot webhook if configured
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json={"message": user_msg, "session_id": payload.session_id})
            if resp.status_code == 200:
                data = resp.json()
                bot_reply = data.get("reply") or data.get("output") or data.get("message")
                if bot_reply:
                    return {"reply": bot_reply, "source": "n8n_vector_pipeline"}
    except Exception as e:
        print(f"[Chatbot] Notice: n8n chat webhook at {webhook_url} not reachable: {e}")

    # Fallback knowledge responder for standard airline queries
    lower_msg = user_msg.lower()
    if "refund" in lower_msg or "cancel" in lower_msg:
        reply = "Mera Safar Policy: FLEX fare bookings receive a 100% full refund upon voluntary cancellation before departure. BASIC fare bookings are non-refundable. In case of an operational flight cancellation by airline management, all affected passengers receive automated full refunds."
    elif "baggage" in lower_msg or "luggage" in lower_msg or "weight" in lower_msg:
        reply = "Mera Safar Baggage Allowance: Economy Class allows up to 20 kg check-in + 7 kg cabin carry-on. Business Class allows up to 30 kg check-in + 10 kg carry-on. First Class allows up to 40 kg check-in + 2 pieces carry-on."
    elif "support" in lower_msg or "ticket" in lower_msg or "inquiry" in lower_msg:
        reply = "You can submit a direct Customer Support Ticket from the 'Support' tab in the top navigation bar. Simply provide your email, flight number, and inquiry to receive a tracked resolution."
    elif "flex" in lower_msg or "basic" in lower_msg or "fare" in lower_msg:
        reply = "We offer two fare tiers: BASIC (best price, non-refundable on voluntary cancellation) and FLEX (+30% price, 100% full refund guarantee on cancellation)."
    else:
        reply = "Hello! I am your Mera Safar AI Assistant. You can ask me about our Cancellation & Refund policies, Baggage rules, Fare tiers (Basic vs Flex), or how to submit a support ticket. How may I assist your travel today?"

    return {"reply": reply, "source": "mera_safar_kb"}


# Dedicated Frontend Directory Mount
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
os.makedirs(frontend_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

@app.get("/")
def index():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "running", "name": "Mera Safar Flight System", "docs": "/docs"}

@app.get("/api/health")
def health_check():
    return {"status": "running", "message": "Mera Safar Flight API is healthy"}