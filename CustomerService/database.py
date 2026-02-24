"""
Database models for Customer Service Bot.
Connects to the SAME MySQL database as ChargingPlatform.
Only stores bot conversation data — tickets live in ChargingPlatform.
"""

import os
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


# ==================== BOT CONVERSATIONS ====================

class BotConversation(Base):
    """Track bot conversations for analytics."""
    __tablename__ = "bot_conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)

    user_id = Column(Integer, nullable=True)
    resolved_by_bot = Column(Boolean, default=False)
    escalated_to_ticket = Column(Boolean, default=False)
    ticket_id = Column(Integer, nullable=True)
    category = Column(String(50), nullable=True)
    message_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)


class BotMessage(Base):
    """Individual messages in bot conversations."""
    __tablename__ = "bot_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("bot_conversations.id"), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # user, bot
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== DATABASE ENGINE ====================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://charging_user:charging_password@localhost:3306/customer_service"
)

if DATABASE_URL.startswith("mysql"):
    engine = create_engine(
        DATABASE_URL, pool_pre_ping=True, pool_recycle=3600, echo=False
    )
else:
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create bot tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
