# LandConnect – Backend API & Real-Time Signaling Server

Backend service for the **LandConnect** land marketplace mobile prototype. Built with **Python (FastAPI)**, **SQLAlchemy ORM**, **JWT authentication**, and **WebSockets** to power role-based land listings, private deal-room messaging, and real-time audio/video call signaling without exposing personal phone numbers.

---

## 1. Tech Stack & Architecture

- **Framework:** FastAPI (Python 3.13) + Uvicorn ASGI server
- **Database & ORM:** SQLite / PostgreSQL-compatible SQLAlchemy ORM (`User`, `Listing`, `Message` models)
- **Authentication & RBAC:** JWT (`python-jose`) + Bcrypt password hashing (`passlib`), enforcing role-based access (`buyer`, `seller`, `broker`)
- **Real-Time Signaling & Chat:** Native FastAPI WebSockets (`/ws/{user_id}`) managed via an active connection registry (`ConnectionManager`) for instant message delivery and call state events (`call_invite`, `call_accept`, `call_reject`, `call_end`)

### REST & WebSocket Endpoints
| Method | Endpoint | Access / Description |
| :--- | :--- | :--- |
| `POST` | `/auth/register` | Register a new `buyer`, `seller`, or `broker` account |
| `POST` | `/auth/login` | Authenticate user and return JWT + user profile |
| `GET` | `/users` | Privacy-filtered directory (excludes emails & phone numbers) |
| `GET` | `/listings` | Retrieve all geotagged land listings |
| `POST` | `/listings` | Create a land listing (restricted to `seller` & `broker` roles) |
| `DELETE` | `/listings/{id}` | Delete own listing (`HTTP 403` ownership check) |
| `GET` | `/messages/{u1}/{u2}` | Fetch 1-on-1 private chat history |
| `WS` | `/ws/{user_id}` | Bidirectional WebSocket for real-time chat & audio/video call signaling |

---

## 2. Setup & Execution Instructions

```bash
git clone [https://github.com/MegharajPN/landconnect-backend.git](https://github.com/MegharajPN/landconnect-backend.git)
cd landconnect-backend

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
# source venv/bin/activate

pip install fastapi uvicorn sqlalchemy "passlib[bcrypt]" "python-jose[cryptography]" python-multipart websockets
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive Swagger API Docs:** `http://localhost:8000/docs`

---

## 3. Technical Decisions & Privacy Controls

- **Privacy-by-Design Serialization:** Public user and listing endpoints strip personal emails and phone numbers at the API layer, routing all communication through internal user IDs.
- **Server-Side RBAC Enforcement:** Listing creation validates user roles on the backend (`HTTP 403` if a `buyer` attempts to create a listing), and deletion verifies `owner_id` ownership.
- **Lightweight WebSocket Call Signaling:** Separates call-state signaling (`call_invite`, `call_accept`, `call_reject`, `call_end`) from media transport, passing ephemeral room IDs instead of personal phone numbers.

---

## 4. AI Tools Usage Summary

- **Tools Used:** Gemini & GitHub Copilot
- **Contribution:** Accelerated boilerplate generation for SQLAlchemy models, Pydantic schemas, and WebSocket connection handling, and helped resolve Windows PowerShell dependency escaping. All database schemas, RBAC logic, and signaling flows were reviewed and tested end-to-end.