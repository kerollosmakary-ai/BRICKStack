import os, sys, json, asyncio, traceback
from pathlib import Path

# Load .env manually (no python-dotenv dependency)
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip(chr(39)+chr(34)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

# ── imports ────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from orchestrator.schemas import GraphEvent
from orchestrator.llm import LLMClient
from orchestrator.graph import run_graph, run_edit
from storage.db import init_db, get_db

DB_INITIALIZED = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global DB_INITIALIZED
    if not DB_INITIALIZED:
        init_db()
        DB_INITIALIZED = True
    yield

app = FastAPI(lifespan=lifespan, title="BRICKStack Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── health ───────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "llm_ready": bool(LLMClient().api_key)}

# ── file tree ────────────────────────────────────────────────
@app.get("/api/files")
async def list_files():
    workspace = "/tmp/brickstack_workspace"
    os.makedirs(workspace, exist_ok=True)
    files = []
    for root, dirs, filenames in os.walk(workspace):
        for f in filenames:
            files.append(os.path.relpath(os.path.join(root, f), workspace))
    return {"files": files, "workspace": workspace}

# ── websocket ────────────────────────────────────────────────
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "content": "Invalid JSON"})
                continue

            if data.get("type") == "list_files":
                workspace = "/tmp/brickstack_workspace"
                os.makedirs(workspace, exist_ok=True)
                files = []
                for root, dirs, filenames in os.walk(workspace):
                    for f in filenames:
                        files.append(os.path.relpath(os.path.join(root, f), workspace))
                await websocket.send_json({"type": "file_tree", "files": files, "task_id": data.get("task_id", "system")})
                continue

            if data.get("type") == "user_message":
                state = {
                    "task_id": data.get("task_id", "task-" + str(asyncio.get_event_loop().time())),
                    "prompt": data.get("content", ""),
                    "session_context": data.get("session_context", {}),
                    "user_id": data.get("user_id", "anonymous"),
                }
                async for event in run_graph(state):
                    await websocket.send_json(event.model_dump())
                await websocket.send_json({"type": "done", "task_id": state["task_id"]})
                continue

            if data.get("type") == "edit_code":
                state = {
                    "task_id": data.get("task_id", "task-" + str(asyncio.get_event_loop().time())),
                    "prompt": data.get("content", ""),
                    "code": data.get("code", ""),
                    "session_context": {},
                    "user_id": data.get("user_id", "anonymous"),
                }
                updated_code = data.get("code", "")
                async for event in run_edit(state, updated_code):
                    await websocket.send_json(event.model_dump())
                await websocket.send_json({"type": "done", "task_id": state["task_id"]})
                continue

            await websocket.send_json({"type": "error", "content": "Unknown message type"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})

# ── static frontend ──────────────────────────────────────────
if os.path.exists("frontend/build"):
    app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")
elif os.path.exists("frontend/index.html"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
