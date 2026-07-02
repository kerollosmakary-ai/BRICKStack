#!/usr/bin/env python3
"""
BRICKStack Hetzner Optimized Backend

Designed for low-resource VPS (1-2 vCPU, 2-4GB RAM):
- No Docker overhead
- SQLite instead of Postgres (saves ~200MB RAM)
- No Redis (saves ~50MB RAM)
- Single Uvicorn worker with Gunicorn
- Static files served by Caddy (not Python)
- External LLM only (no local model)
- Minimal dependencies

Usage:
    python -m uvicorn backend.main_hetzner:app --host 127.0.0.1 --port 8000 --workers 1

Or with Gunicorn (recommended):
    gunicorn backend.main_hetzner:app -w 1 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
"""

import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("brickstack_hetzner")

# ── FastAPI ───────────────────────────────────────────────────────
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ── LiteLLM Client ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from orchestrator.litellm_client import create_client, LiteLLMClient

# ── Configuration ───────────────────────────────────────────────────
HOST = os.getenv("API_HOST", "127.0.0.1")
PORT = int(os.getenv("API_PORT", "8000"))
MODEL = os.getenv("LLM_MODEL", "deepseek")
WORKERS = int(os.getenv("WORKERS", "1"))

def get_db_path() -> Path:
    """SQLite database path."""
    db_dir = Path(__file__).parent.parent / "data"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "brickstack.db"

# ── Simple SQLite Storage ───────────────────────────────────────────
import sqlite3
import threading

class SQLiteStore:
    """Thread-safe SQLite store for tasks and messages."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                prompt TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                error TEXT,
                model TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        logger.info(f"SQLite initialized: {self.db_path}")
    
    def create_task(self, task_id: str, prompt: str, model: str) -> dict:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO tasks (id, prompt, status, model) VALUES (?, ?, ?, ?)",
            (task_id, prompt, "pending", model)
        )
        conn.commit()
        return {"id": task_id, "prompt": prompt, "status": "pending", "model": model}
    
    def get_task(self, task_id: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    
    def update_task(self, task_id: str, status: str, result: str = None, error: str = None):
        conn = self._get_conn()
        conn.execute(
            "UPDATE tasks SET status = ?, result = ?, error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, result, error, task_id)
        )
        conn.commit()
    
    def list_tasks(self, limit: int = 50) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    
    def add_message(self, task_id: str, role: str, content: str):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (task_id, role, content) VALUES (?, ?, ?)",
            (task_id, role, content)
        )
        conn.commit()
    
    def get_messages(self, task_id: str) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM messages WHERE task_id = ? ORDER BY created_at", (task_id,)
        ).fetchall()
        return [dict(row) for row in rows]

# ── Global Store ──────────────────────────────────────────────────────
db = SQLiteStore(get_db_path())

# ── LLM Client ───────────────────────────────────────────────────────
llm_client: Optional[LiteLLMClient] = None

def get_llm() -> LiteLLMClient:
    global llm_client
    if llm_client is None:
        llm_client = create_client(model_name=MODEL, temperature=0.3, max_tokens=4096)
    return llm_client

# ── FastAPI App ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BRICKStack Hetzner starting...")
    # Warm up LLM client
    try:
        client = get_llm()
        info = client.get_info()
        logger.info(f"LLM: {info['model']} ({info['provider']})")
    except Exception as e:
        logger.warning(f"LLM not ready: {e}")
    yield
    logger.info("BRICKStack Hetzner shutting down...")

app = FastAPI(
    title="BRICKStack Hetzner",
    description="Optimized for low-resource VPS (2-4GB RAM)",
    version="2.1.0",
    lifespan=lifespan,
)

# CORS (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health ──────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.1.0",
        "model": MODEL,
        "sqlite": str(get_db_path()),
    }

@app.get("/api/status")
async def status():
    try:
        client = get_llm()
        info = client.get_info()
    except Exception as e:
        info = {"error": str(e)}
    return {
        "status": "running",
        "model": MODEL,
        "llm": info,
        "workers": WORKERS,
        "timestamp": datetime.utcnow().isoformat(),
    }

# ── Tasks ───────────────────────────────────────────────────────────
@app.post("/api/tasks")
async def create_task(payload: dict):
    import uuid
    task_id = str(uuid.uuid4())[:8]
    prompt = payload.get("prompt", "")
    model = payload.get("model", MODEL)
    
    if not prompt:
        raise HTTPException(400, "Missing 'prompt'")
    
    task = db.create_task(task_id, prompt, model)
    return {"task_id": task_id, "status": "pending"}

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task

@app.get("/api/tasks")
async def list_tasks(limit: int = 50):
    return {"tasks": db.list_tasks(limit)}

# ── Streaming Chat ──────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    history = []
    
    try:
        while True:
            data = await websocket.receive_json()
            prompt = data.get("prompt", "")
            model = data.get("model", MODEL)
            system = data.get("system", "You are a helpful coding assistant.")
            
            if not prompt:
                await websocket.send_json({"error": "Empty prompt"})
                continue
            
            await websocket.send_json({"type": "start", "model": model})
            
            try:
                client = create_client(model_name=model, temperature=0.3, max_tokens=4096)
                messages = [{"role": "system", "content": system}]
                for h in history[-10:]:
                    messages.append({"role": h["role"], "content": h["content"]})
                messages.append({"role": "user", "content": prompt})
                
                full_response = []
                async for token in client.chat(messages, stream=True):
                    full_response.append(token)
                    await websocket.send_json({"type": "token", "content": token})
                
                response = "".join(full_response)
                history.append({"role": "user", "content": prompt})
                history.append({"role": "assistant", "content": response})
                
                await websocket.send_json({"type": "done", "content": response})
                
            except Exception as e:
                logger.error(f"Stream error: {e}")
                await websocket.send_json({"type": "error", "message": str(e)})
    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

# ── Agent Pipeline (HTTP) ───────────────────────────────────────────
@app.post("/api/pipeline")
async def run_pipeline(payload: dict):
    import uuid
    task_id = str(uuid.uuid4())[:8]
    prompt = payload.get("prompt", "")
    model = payload.get("model", MODEL)
    
    if not prompt:
        raise HTTPException(400, "Missing 'prompt'")
    
    task = db.create_task(task_id, prompt, model)
    
    # Run pipeline asynchronously
    async def _pipeline():
        try:
            db.update_task(task_id, "running")
            client = create_client(model_name=model, temperature=0.3, max_tokens=4096)
            
            # Step 1: Plan
            plan = await client.complete(f"Break this task into steps: {prompt}", system=AGENTS["plan"])
            db.add_message(task_id, "planner", plan)
            
            # Step 2: Code
            code = await client.complete(
                f"Task: {prompt}\n\nPlan:\n{plan}\n\nWrite the complete code.",
                system=AGENTS["code"]
            )
            db.add_message(task_id, "coder", code)
            
            # Step 3: Review
            review = await client.complete(f"Review this code:\n\n{code}", system=AGENTS["review"])
            db.add_message(task_id, "reviewer", review)
            
            result = json.dumps({"plan": plan, "code": code, "review": review})
            db.update_task(task_id, "completed", result=result)
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            db.update_task(task_id, "failed", error=str(e))
    
    asyncio.create_task(_pipeline())
    return {"task_id": task_id, "status": "running"}

AGENTS = {
    "plan": "You are a technical project manager. Break this task into numbered steps with file names and complexity estimates.",
    "code": "You are an expert software engineer. Write clean, efficient, well-documented code with type hints and error handling.",
    "review": "You are a senior code reviewer. Check for bugs, security issues, performance, and style. Provide severity ratings.",
}

# ── Static Files (development only, Caddy serves in production) ──────
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, workers=WORKERS)
