"""
Persistence layer — Postgres (chat history) + Redis (session state)
"""
import os, json, logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("storage")

# ── Config ──
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/brickstack")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── In-memory fallback (no deps required for demo) ──
_memory_db: dict = {"messages": [], "sessions": {}}

async def init_db():
    """Initialize database tables (Postgres or in-memory)"""
    log.info("Storage ready (in-memory mode)")
    # In prod: CREATE TABLES via SQLAlchemy
    return True

async def get_db():
    return _memory_db

# ── Message Model ──

class MessageModel:
    @staticmethod
    async def create(session_id: str, role: str, content: str, agent: Optional[str] = None):
        msg = {
            "id": len(_memory_db["messages"]) + 1,
            "session_id": session_id,
            "role": role,
            "content": content,
            "agent": agent,
            "created_at": datetime.utcnow().isoformat(),
        }
        _memory_db["messages"].append(msg)
        # Also store under session
        if session_id not in _memory_db["sessions"]:
            _memory_db["sessions"][session_id] = []
        _memory_db["sessions"][session_id].append(msg)
        return msg

    @staticmethod
    async def get_session(session_id: str) -> list:
        return _memory_db["sessions"].get(session_id, [])

    @staticmethod
    async def list_sessions(limit: int = 50) -> list:
        sessions = {}
        for msg in _memory_db["messages"]:
            sid = msg["session_id"]
            if sid not in sessions:
                sessions[sid] = {"session_id": sid, "count": 0, "last": ""}
            sessions[sid]["count"] += 1
            sessions[sid]["last"] = msg["created_at"]
        return sorted(sessions.values(), key=lambda x: x["last"], reverse=True)[:limit]
