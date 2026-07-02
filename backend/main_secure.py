#!/usr/bin/env python3
"""BRICKStack — Production-hardened backend."""
import os, sys, json, asyncio, traceback, time, hashlib, hmac, re, subprocess
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

# ── Load .env ──────────────────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

# ── Security imports ───────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from middleware.security import (
    RateLimiter, InputValidator, AuthMiddleware,
    RateLimitMiddleware, SecurityHeadersMiddleware,
    verify_ws_token, generate_token
)

# ── Core imports ───────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from orchestrator.schemas import GraphEvent
from orchestrator.llm import LLMClient
from orchestrator.graph import run_graph, run_edit
from storage.db import init_db, get_db
from storage.models import MessageModel

DB_INITIALIZED = False
CONNECTIONS = {}  # task_id -> websocket

# ── Logging ───────────────────────────────────────────────────
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("/tmp/brickstack.log"), logging.StreamHandler()]
)
logger = logging.getLogger("brickstack")

# ── Lifespan ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    global DB_INITIALIZED
    if not DB_INITIALIZED:
        try:
            init_db()
            DB_INITIALIZED = True
            logger.info("Database initialized")
        except Exception as e:
            logger.warning(f"DB init failed (using fallback): {e}")
    yield
    logger.info("Shutting down BRICKStack")

# ── FastAPI App ────────────────────────────────────────────────
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

app = FastAPI(
    lifespan=lifespan,
    title="BRICKStack",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENV", "prod") != "prod" else None,
    redoc_url=None,
)

# Security middlewares (order matters)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, limiter=RateLimiter(max_requests=30, window_seconds=60))
app.add_middleware(AuthMiddleware, exempt_paths=["/api/health", "/api/token", "/", "/static", "/docs"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
)

# ── Health ────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_ready": bool(LLMClient().api_key),
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }

# ── Token Generation ─────────────────────────────────────────
@app.get("/api/token")
async def get_token():
    """Generate a new API token. In production, protect this endpoint."""
    token = generate_token()
    logger.info("Token generated")
    return {"token": token, "expires_in": 3600}

# ── File Tree ──────────────────────────────────────────────────
@app.get("/api/files")
async def list_files():
    workspace = "/tmp/brickstack_workspace"
    os.makedirs(workspace, exist_ok=True)
    files = []
    try:
        for root, dirs, filenames in os.walk(workspace):
            # Prevent escaping workspace
            for d in dirs:
                dpath = os.path.join(root, d)
                if os.path.islink(dpath) and not os.path.realpath(dpath).startswith(workspace):
                    dirs.remove(d)
            for f in filenames:
                fpath = os.path.join(root, f)
                if os.path.islink(fpath):
                    realpath = os.path.realpath(fpath)
                    if not realpath.startswith(workspace):
                        continue
                relpath = os.path.relpath(fpath, workspace)
                # Prevent path traversal
                if ".." in relpath or relpath.startswith("/"):
                    continue
                files.append(relpath)
    except Exception as e:
        logger.error(f"File tree error: {e}")
    return {"files": files, "workspace": workspace, "count": len(files)}

# ── WebSocket ─────────────────────────────────────────────────
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    # Optional: require token for production
    if os.getenv("WS_REQUIRE_AUTH", "false").lower() == "true":
        if not await verify_ws_token(websocket):
            await websocket.close(code=4001, reason="Unauthorized")
            return
    
    await websocket.accept()
    client_ip = websocket.client.host
    logger.info(f"WebSocket connected: {client_ip}")
    
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "content": "Invalid JSON"})
                continue
            
            # Validate message structure
            msg_type = data.get("type")
            if msg_type not in ("user_message", "edit_code", "list_files"):
                await websocket.send_json({"type": "error", "content": "Unknown message type"})
                continue
            
            try:
                if msg_type == "list_files":
                    workspace = "/tmp/brickstack_workspace"
                    os.makedirs(workspace, exist_ok=True)
                    files = []
                    for root, dirs, filenames in os.walk(workspace):
                        for f in filenames:
                            relpath = os.path.relpath(os.path.join(root, f), workspace)
                            if ".." not in relpath:
                                files.append(relpath)
                    await websocket.send_json({"type": "file_tree", "files": files, "task_id": data.get("task_id", "system")})
                    continue
                
                if msg_type == "user_message":
                    # Validate input
                    prompt = InputValidator.validate_prompt(data.get("content", ""))
                    task_id = re.sub(r'[^a-zA-Z0-9\-_]', '', data.get("task_id", f"task-{int(time.time())}"))[:64]
                    
                    state = {
                        "task_id": task_id,
                        "prompt": prompt,
                        "session_context": {},
                        "user_id": re.sub(r'[^a-zA-Z0-9\-_]', '', str(data.get("user_id", "anonymous")))[:64],
                    }
                    CONNECTIONS[task_id] = websocket
                    
                    async for event in run_graph(state):
                        await websocket.send_json(event.model_dump())
                    await websocket.send_json({"type": "done", "task_id": task_id})
                    CONNECTIONS.pop(task_id, None)
                    continue
                
                if msg_type == "edit_code":
                    code = InputValidator.validate_code(data.get("code", ""))
                    task_id = re.sub(r'[^a-zA-Z0-9\-_]', '', data.get("task_id", f"task-{int(time.time())}"))[:64]
                    state = {
                        "task_id": task_id,
                        "prompt": data.get("content", ""),
                        "code": code,
                        "session_context": {},
                        "user_id": "anonymous",
                    }
                    async for event in run_edit(state, code):
                        await websocket.send_json(event.model_dump())
                    await websocket.send_json({"type": "done", "task_id": task_id})
                    continue
                    
            except ValueError as ve:
                logger.warning(f"Validation error from {client_ip}: {ve}")
                await websocket.send_json({"type": "error", "content": str(ve), "task_id": data.get("task_id", "unknown")})
            except Exception as e:
                logger.error(f"Pipeline error: {e}\n{traceback.format_exc()}")
                await websocket.send_json({"type": "error", "content": "Internal error. Please try again.", "task_id": data.get("task_id", "unknown")})
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {client_ip}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

# ── Static Frontend ────────────────────────────────────────────
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if (frontend_dir / "build" / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir / "build"), html=True), name="static")
elif (frontend_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_secure:app", host="0.0.0.0", port=int(os.getenv("API_PORT", 8000)), reload=False)
