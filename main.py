from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt
from typing import Dict, List, Optional
import json

from database import get_db, User, Listing, Message

SECRET_KEY = "landconnect_super_secret_key"
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="LandConnect API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic Schemas ---
class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    role: str  # "buyer", "seller", or "broker"

class UserLogin(BaseModel):
    email: str
    password: str

class ListingCreate(BaseModel):
    title: str
    description: str
    price: str
    area_sqft: str
    location_name: str
    latitude: float
    longitude: float
    image_url: Optional[str] = "https://images.unsplash.com/photo-1500382017468-9049fed747ef"
    owner_id: int

# --- Auth Endpoints ---
@app.post("/auth/register")
def register(user: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if user.role.lower() not in ["buyer", "seller", "broker"]:
        raise HTTPException(status_code=400, detail="Role must be buyer, seller, or broker")
    
    new_user = User(
        name=user.name,
        email=user.email,
        hashed_password=pwd_context.hash(user.password),
        role=user.role.lower()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    token = jwt.encode({"sub": str(new_user.id), "role": new_user.role}, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "user": {"id": new_user.id, "name": new_user.name, "email": new_user.email, "role": new_user.role}}

@app.post("/auth/login")
def login(creds: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == creds.email).first()
    if not user or not pwd_context.verify(creds.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode({"sub": str(user.id), "role": user.role}, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role}}

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    # Privacy protection: Never expose emails or phone numbers in public directory
    return [{"id": u.id, "name": u.name, "role": u.role} for u in users]

# --- Listings Endpoints (Role-Protected) ---
@app.get("/listings")
def get_listings(db: Session = Depends(get_db)):
    return db.query(Listing).order_by(Listing.created_at.desc()).all()

@app.post("/listings")
def create_listing(item: ListingCreate, db: Session = Depends(get_db)):
    owner = db.query(User).filter(User.id == item.owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="User not found")
    if owner.role not in ["seller", "broker"]:
        raise HTTPException(status_code=403, detail="Only Sellers and Brokers can post land listings")
    
    listing = Listing(
        **item.dict(),
        owner_name=owner.name,
        owner_role=owner.role
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing

@app.delete("/listings/{listing_id}")
def delete_listing(listing_id: int, user_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing or listing.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this listing")
    db.delete(listing)
    db.commit()
    return {"status": "deleted"}

# --- Chat History ---
@app.get("/messages/{user1_id}/{user2_id}")
def get_chat_history(user1_id: int, user2_id: int, db: Session = Depends(get_db)):
    msgs = db.query(Message).filter(
        ((Message.sender_id == user1_id) & (Message.receiver_id == user2_id)) |
        ((Message.sender_id == user2_id) & (Message.receiver_id == user1_id))
    ).order_by(Message.timestamp.asc()).all()
    return msgs

# --- WebSocket Manager for Real-Time Chat & Audio/Video Call Signaling ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(json.dumps(message))

manager = ConnectionManager()

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, db: Session = Depends(get_db)):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            event_type = payload.get("type")  # "chat", "call_invite", "call_accept", "call_reject", "call_end"
            target_id = int(payload.get("to"))

            if event_type == "chat":
                msg = Message(sender_id=user_id, receiver_id=target_id, content=payload.get("content"))
                db.add(msg)
                db.commit()
                await manager.send_personal_message({
                    "type": "chat",
                    "from": user_id,
                    "content": payload.get("content")
                }, target_id)
            else:
                # Forward call signaling events (call_invite, call_accept, call_reject, call_end)
                await manager.send_personal_message(payload, target_id)
    except WebSocketDisconnect:
        manager.disconnect(user_id)