"""
Live Audio Streaming Platform Backend
FastAPI application for managing streaming rooms and authentication
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import uuid
import secrets
import qrcode
import io
import base64
from datetime import datetime, timedelta
import asyncio
from contextlib import asynccontextmanager

# Data models
class Room(BaseModel):
    room_id: str
    stream_key: str
    title: str
    created_at: datetime
    is_active: bool = False
    viewer_count: int = 0

class CreateRoomRequest(BaseModel):
    title: str
    description: Optional[str] = None

class RoomResponse(BaseModel):
    room_id: str
    stream_key: str
    title: str
    rtmp_url: str
    viewer_url: str
    qr_code: str  # Base64 encoded QR code image
    created_at: datetime
    is_active: bool
    viewer_count: int

# In-memory storage (use Redis/PostgreSQL in production)
rooms_db: Dict[str, Room] = {}
active_streams: Dict[str, datetime] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Audio streaming platform starting...")
    yield
    # Shutdown
    print("📴 Audio streaming platform shutting down...")

# Initialize FastAPI app
app = FastAPI(
    title="Live Audio Streaming Platform",
    description="Backend API for managing audio streaming rooms",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for web browsers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_qr_code(url: str) -> str:
    """Generate QR code for room URL and return as base64 string"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Live Audio Streaming Platform API",
        "status": "running",
        "active_rooms": len([r for r in rooms_db.values() if r.is_active])
    }

@app.post("/api/rooms", response_model=RoomResponse)
async def create_room(request: CreateRoomRequest):
    """
    Create a new streaming room
    Returns room details including RTMP URL and QR code
    """
    # Generate unique identifiers
    room_id = str(uuid.uuid4())
    stream_key = secrets.token_urlsafe(32)
    
    # Create room object
    room = Room(
        room_id=room_id,
        stream_key=stream_key,
        title=request.title,
        created_at=datetime.utcnow()
    )
    
    # Store in database
    rooms_db[room_id] = room
    
    # Generate URLs using domain name
    # server_host = "localhost"  # Configure from environment in production
    # rtmp_port = 1935
    # viewer_port = 8088
    # rtmp_url = f"rtmp://{server_host}:{rtmp_port}/live/{stream_key}"
    # viewer_url = f"http://{server_host}:{viewer_port}/room/{room_id}"
    
    # Updated URLs for forwarded domain
    server_host = "tilsync.nu.edu.kz"
    rtmp_port = 443
    rtmp_url = f"rtmp://{server_host}:{rtmp_port}/live/{stream_key}"
    viewer_url = f"https://tilsync.nu.edu.kz/broadcast/client/room/{room_id}"
    
    # Generate QR code
    qr_code = generate_qr_code(viewer_url)
    
    return RoomResponse(
        room_id=room.room_id,
        stream_key=room.stream_key,
        title=room.title,
        rtmp_url=rtmp_url,
        viewer_url=viewer_url,
        qr_code=qr_code,
        created_at=room.created_at,
        is_active=room.is_active,
        viewer_count=room.viewer_count
    )

@app.get("/api/rooms/{room_id}", response_model=RoomResponse)
async def get_room(room_id: str):
    """Get room details by room ID"""
    if room_id not in rooms_db:
        raise HTTPException(status_code=404, detail="Room not found")
    
    room = rooms_db[room_id]
    

    # Generate URLs
    # server_host = "localhost"  # Configure from environment in production
    # rtmp_port = 1935
    # viewer_port = 8088
    # rtmp_url = f"rtmp://{server_host}:{rtmp_port}/live/{room.stream_key}"
    # viewer_url = f"http://{server_host}:{viewer_port}/room/{room_id}"
    
    # Updated URLs for forwarded domain
    server_host = "tilsync.nu.edu.kz"
    rtmp_port = 443
    rtmp_url = f"rtmp://{server_host}:{rtmp_port}/live/{room.stream_key}"
    viewer_url = f"https://tilsync.nu.edu.kz/broadcast/client/room/{room_id}"
    qr_code = generate_qr_code(viewer_url)
    
    return RoomResponse(
        room_id=room.room_id,
        stream_key=room.stream_key,
        title=room.title,
        rtmp_url=rtmp_url,
        viewer_url=viewer_url,
        qr_code=qr_code,
        created_at=room.created_at,
        is_active=room.is_active,
        viewer_count=room.viewer_count
    )

@app.get("/api/rooms")
async def list_rooms():
    """List all rooms with their status"""
    return [
        {
            "room_id": room.room_id,
            "title": room.title,
            "created_at": room.created_at,
            "is_active": room.is_active,
            "viewer_count": room.viewer_count
        }
        for room in rooms_db.values()
    ]

@app.delete("/api/rooms/{room_id}")
async def delete_room(room_id: str):
    """Delete a room"""
    if room_id not in rooms_db:
        raise HTTPException(status_code=404, detail="Room not found")
    
    del rooms_db[room_id]
    return {"message": "Room deleted successfully"}

# NGINX RTMP webhook endpoints
@app.post("/webhooks/stream_start")
async def stream_start_webhook(request: Request):
    """Called by NGINX when a stream starts publishing"""
    form_data = await request.form()
    stream_key = form_data.get("name")
    
    # Find room by stream key
    room = None
    for r in rooms_db.values():
        if r.stream_key == stream_key:
            room = r
            break
    
    if room:
        room.is_active = True
        active_streams[stream_key] = datetime.utcnow()
        print(f"🎵 Stream started for room: {room.title}")
    
    return JSONResponse({"status": "ok"})

@app.post("/webhooks/stream_end")
async def stream_end_webhook(request: Request):
    """Called by NGINX when a stream stops publishing"""
    form_data = await request.form()
    stream_key = form_data.get("name")
    
    # Find room by stream key
    room = None
    for r in rooms_db.values():
        if r.stream_key == stream_key:
            room = r
            break
    
    if room:
        room.is_active = False
        if stream_key in active_streams:
            del active_streams[stream_key]
        print(f"⏹️ Stream ended for room: {room.title}")
    
    return JSONResponse({"status": "ok"})

@app.get("/api/stream/{stream_key}/status")
async def get_stream_status(stream_key: str):
    """Check if a stream is currently active"""
    is_active = stream_key in active_streams
    return {
        "stream_key": stream_key,
        "is_active": is_active,
        "started_at": active_streams.get(stream_key) if is_active else None
    }

# Room-specific API for viewer page
@app.get("/api/room/{room_id}/stream-url")
async def get_room_stream_url(room_id: str):
    """Get HLS stream URL for a specific room"""
    if room_id not in rooms_db:
        raise HTTPException(status_code=404, detail="Room not found")
        
    room = rooms_db[room_id]
    # hls_url = f"/hls/{room.stream_key}.m3u8"  # Local access
    hls_url = f"/broadcast/client/hls/{room.stream_key}.m3u8"  # Forwarded domain access
    
    return {
        "room_id": room_id,
        "hls_url": hls_url,
        "is_active": room.is_active,
        "title": room.title
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)