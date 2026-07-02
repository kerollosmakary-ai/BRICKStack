"""
Session management + rate limiting
"""
import uuid, time, hashlib, hmac, os
from datetime import datetime, timedelta

SESSIONS: dict[str, dict] = {}
RATE_LIMIT_WINDOW = 10  # seconds
RATE_LIMIT_MAX = 30     # messages per window

def create_session() -> str:
    sid = uuid.uuid4().hex[:16]
    SESSIONS[sid] = {
        "created": datetime.utcnow(),
        "msg_count": 0,
        "window_start": time.time(),
    }
    return sid

def validate_session(session_id: str) -> bool:
    return session_id in SESSIONS

def rate_limit(session_id: str) -> bool:
    sess = SESSIONS.get(session_id)
    if not sess:
        return False
    now = time.time()
    if now - sess["window_start"] > RATE_LIMIT_WINDOW:
        sess["window_start"] = now
        sess["msg_count"] = 0
    sess["msg_count"] += 1
    return sess["msg_count"] <= RATE_LIMIT_MAX

def cleanup_sessions():
    """Remove sessions older than 24h"""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    to_del = [k for k, v in SESSIONS.items() if v["created"] < cutoff]
    for k in to_del:
        del SESSIONS[k]
