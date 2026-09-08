Mera Safar - Enterprise Flight Reservation & Management System
An enterprise-grade, full-stack airline reservation and operations platform built with FastAPI, PostgreSQL (Supabase), and modern responsive web technologies. The platform handles concurrent seat inventory allocations, dual-tier fare protection policies, and automated priority queue waitlists.

Architecture Overview
Frontend: Vanilla HTML5, Modern CSS3, JavaScript (Fetch API, Token-based Auth) deployed via CDN/static hosting.

Backend: FastAPI (Python 3.13) containerized and continuously deployed on Railway.

Database & Auth: PostgreSQL hosted on Supabase with relational constraints and indexing.

Automation (In Progress): n8n workflows for asynchronous priority waitlist processing and transactional notifications.

Key Capabilities & Business Logic
Atomic Seat Allocation: Strict transactional database updates preventing race conditions, inventory collisions, or overbooking across multiple cabin classes (ECONOMY, BUSINESS, FIRST).

Dual-Tier Fare Flexibility Rules:

BASIC Fare: Standard cost tier; strictly non-refundable with cancellation penalties.

FLEX Fare: Premium flexible tier; includes guaranteed 100% full refund rights upon voluntary cancellation.

Transaction Idempotency: Implements x-idempotency-key validation headers across booking mutations to prevent duplicate payment/seat creation on network retries or double-clicks.

Priority Waitlist Engine: Tiered queue allocation (ORDER BY priority DESC, created_at ASC) designed for automatic promotion triggers when cancellations occur.

Role-Guarded Administration: Granular access controls separating passengers, Operations Agents (flight rescheduling), and Super-Admins (inventory and route scheduling).

Tech Stack & Dependencies
Framework: FastAPI

Server: Uvicorn (Standard ASGI)

ORM & Database Drivers: SQLAlchemy, Psycopg2-binary

Validation: Pydantic (with email validation)

Rate Limiting & Security: SlowAPI, PyJWT, Python-Dotenv

Date Parsing: Python-Dateutil

Environment Variables
Create a .env file in the root directory (or configure via Railway / deployment dashboard):

Code snippet
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-key
DATABASE_URL=postgresql://user:password@host:port/dbname
Local Development Setup
1. Clone the Repository
Bash
git clone https://github.com/your-username/mera-safar.git
cd mera-safar
2. Configure Python Virtual Environment
Bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
3. Run Backend API Server
Bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Interactive Swagger API documentation will be available at: http://localhost:8000/docs.

4. Run Frontend
Open frontend/index.html directly in your browser or run a local static file server:

Bash
python -m http.server 3000 --directory frontend
Production Deployment Structure
Backend Service (Railway): Direct GitHub repository integration with automated CI/CD builds on each git push to main. Listens on port 8080.

Frontend Delivery: Static assets served with CORS origin policies configured to allow seamless API transactions between distinct domains.

License
This project was developed for demonstration, portfolio, and hackathon operational showcases. Open-sourced under the MIT License.
