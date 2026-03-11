"""
PlagSini Customer Service — AI Bot Microservice
Handles chat bot interactions; tickets are managed by ChargingPlatform.

Endpoints:
  Bot:
    POST /api/bot/welcome   — Welcome message with categories
    POST /api/bot/category   — FAQ questions for a category
    POST /api/bot/chat       — Chat with the AI bot
    POST /api/bot/escalate   — Create ticket via ChargingPlatform API
"""

import logging
import os
import secrets
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import init_db, get_db, BotConversation, BotMessage
from ai_bot import init_gemini, get_welcome_message, get_category_questions, process_message
from knowledge_base import FAQ_CATEGORIES, detect_category, detect_priority

# ─── Setup ───
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ChargingPlatform base URL (inside Docker network)
CP_BASE_URL = os.getenv("CHARGING_PLATFORM_URL", "http://charging-platform:8000")

# CORS — restrict to known origins; falls back to the charging platform domain
_ALLOWED_ORIGINS_ENV = os.getenv("CORS_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: List[str] = (
    [o.strip() for o in _ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
    if _ALLOWED_ORIGINS_ENV
    else [
        "https://charger.czeros.tech",
        "http://localhost:3000",
        "http://localhost:8000",
    ]
)

app = FastAPI(
    title="PlagSini Customer Service Bot",
    description="AI Bot for PlagSini EV Charging — tickets managed centrally via ChargingPlatform",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ─── Simple rate limiter for bot endpoints ───
_BOT_RATE_BUCKETS: Dict[str, List[float]] = {}
_BOT_RATE_LOCK = threading.Lock()
_BOT_RATE_LAST_CLEANUP: float = 0.0

BOT_MAX_REQUESTS = int(os.getenv("BOT_RATE_LIMIT_REQUESTS", "30"))   # max calls per window
BOT_RATE_WINDOW  = int(os.getenv("BOT_RATE_LIMIT_WINDOW_SECONDS", "60"))  # window in seconds


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _bot_rate_limit(request: Request) -> None:
    """Enforce per-IP rate limit on bot endpoints. Raises HTTP 429 if exceeded."""
    global _BOT_RATE_LAST_CLEANUP
    now = time.time()
    ip = _get_client_ip(request)
    cutoff = now - float(BOT_RATE_WINDOW)

    with _BOT_RATE_LOCK:
        # Periodic cleanup of stale buckets (every 5 min)
        if now - _BOT_RATE_LAST_CLEANUP > 300:
            stale = [k for k, v in _BOT_RATE_BUCKETS.items() if not v or max(v) < cutoff]
            for k in stale:
                del _BOT_RATE_BUCKETS[k]
            _BOT_RATE_LAST_CLEANUP = now

        bucket = _BOT_RATE_BUCKETS.get(ip, [])
        bucket = [ts for ts in bucket if ts >= cutoff]
        if len(bucket) >= BOT_MAX_REQUESTS:
            raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
        bucket.append(now)
        _BOT_RATE_BUCKETS[ip] = bucket

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    logger.info("🚀 Initializing Customer Service Bot...")
    init_db()
    logger.info("✅ Bot database tables created")
    has_gemini = init_gemini()
    if has_gemini:
        logger.info("✅ Gemini AI ready")
    else:
        logger.info("⚠️  Running in rule-based mode (no Gemini API key)")
    logger.info("🎉 Customer Service Bot ready on port 8001")


# ─── Pydantic Models ───

class BotChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    category: Optional[str] = None


class BotCategoryRequest(BaseModel):
    category_id: str


class EscalateRequest(BaseModel):
    """Create a ticket through ChargingPlatform."""
    email: str
    name: Optional[str] = ""
    category: Optional[str] = "general"
    subject: str
    description: str
    user_id: Optional[int] = None


# ═══════════════════════════════════════════
#  BOT ENDPOINTS
# ═══════════════════════════════════════════

@app.post("/api/bot/welcome")
async def bot_welcome(request: Request):
    """Get the bot's welcome message with category buttons."""
    _bot_rate_limit(request)
    return {"success": True, "data": get_welcome_message()}


@app.post("/api/bot/category")
async def bot_category(req: BotCategoryRequest, request: Request):
    """Get FAQ questions for a specific category."""
    _bot_rate_limit(request)
    data = get_category_questions(req.category_id)
    return {"success": True, "data": data}


@app.post("/api/bot/chat")
async def bot_chat(req: BotChatRequest, request: Request, db: Session = Depends(get_db)):
    """Send a message to the AI bot and get a response."""
    _bot_rate_limit(request)

    # Limit message length to prevent abuse
    if len(req.message) > 2000:
        raise HTTPException(status_code=400, detail="Message too long (max 2000 characters).")

    try:
        session_id = req.session_id or secrets.token_hex(16)

        conversation = db.query(BotConversation).filter(
            BotConversation.session_id == session_id
        ).first()

        if not conversation:
            conversation = BotConversation(session_id=session_id, message_count=0)
            db.add(conversation)
            db.flush()

        # Save user message
        user_msg = BotMessage(
            conversation_id=conversation.id,
            role="user",
            content=req.message,
        )
        db.add(user_msg)
        conversation.message_count += 1

        # Get conversation history for context
        history = (
            db.query(BotMessage)
            .filter(BotMessage.conversation_id == conversation.id)
            .order_by(BotMessage.created_at)
            .all()
        )
        history_dicts = [{"role": m.role, "content": m.content} for m in history]

        # Process with AI bot
        response = await process_message(
            user_message=req.message,
            conversation_history=history_dicts,
            selected_category=req.category,
        )

        # Save bot response
        bot_msg = BotMessage(
            conversation_id=conversation.id,
            role="bot",
            content=response["message"],
        )
        db.add(bot_msg)
        conversation.message_count += 1
        conversation.category = response.get("category")

        db.commit()

        return {
            "success": True,
            "data": {
                "session_id": session_id,
                **response,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"bot_chat error: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@app.post("/api/bot/escalate")
async def escalate_to_ticket(req: EscalateRequest):
    """Escalate a chat to a support ticket — calls ChargingPlatform API."""
    full_text = f"{req.subject} {req.description}"
    category = req.category if req.category != "general" else detect_category(full_text)
    priority = detect_priority(full_text)

    payload = {
        "user_email": req.email,
        "user_name": req.name or "",
        "user_id": req.user_id,
        "category": category,
        "subject": req.subject,
        "description": req.description,
        "priority": priority,
        "source": "chatbot",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{CP_BASE_URL}/api/tickets", json=payload)
            data = resp.json()

        if resp.status_code == 200 and data.get("success"):
            return {
                "success": True,
                "message": data.get("message", "Ticket created"),
                "data": {
                    "ticket_number": data.get("ticket_number"),
                    "ticket_id": data.get("ticket_id"),
                    "category": category,
                    "priority": priority,
                },
            }
        else:
            logger.error(f"ChargingPlatform ticket creation failed: {data}")
            raise HTTPException(status_code=502, detail="Failed to create ticket in central system")
    except httpx.RequestError as e:
        logger.error(f"Cannot reach ChargingPlatform: {e}")
        raise HTTPException(status_code=502, detail="Support system temporarily unavailable")


# ─── Web Chat UI ───

@app.get("/", response_class=HTMLResponse)
async def chat_page():
    """Serve the web chat interface."""
    return FileResponse("static/chat.html")


# ─── Health Check ───

@app.get("/health")
async def health():
    return {"status": "ok", "service": "customer-service-bot", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
