"""
BRICKStack Studio — Multi-Agent AI Coding Platform
FastAPI Gateway + WebSocket + LangGraph Orchestrator + Docker Sandbox
"""
import os, uuid, json, asyncio, logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import create_session, validate_session, rate_limit
from orchestrator.graph import AgentGraph
from storage.db import get_db, init_db
from storage.models import MessageModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("brickstack")

# ── State ──
active_sessions: dict[str, dict] = {}  # session_id → {ws, graph, state}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("DB initialized")
    yield
    log.info("Shutdown")

app = FastAPI(title="BRICKStack Studio", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── REST Endpoints ──

@app.get("/health")
async def health():
    return {"status": "ok", "agents": 5, "sessions": len(active_sessions)}

@app.post("/sessions")
async def create_session_endpoint():
    session_id = create_session()
    return {"session_id": session_id}

# ── WebSocket — Main Event Loop ──

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {"ws": ws, "graph": AgentGraph(session_id)}
    log.info(f"WS connected: {session_id}")

    try:
        # Send session welcome
        await ws.send_json({"type": "system", "content": f"Session {session_id[:8]}... ready. 5 agents online."})

        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            if data.get("type") == "user_message":
                content = data.get("content", "").strip()
                if not content:
                    continue

                await ws.send_json({"type": "user_message", "content": content})

                # ── Run through agent graph ──
                session = active_sessions[session_id]
                graph = session["graph"]

                async for event in graph.run(content):
                    await ws.send_json(event)

                # Save to DB
                await MessageModel.create(session_id, "user", content)
                await MessageModel.create(session_id, "assistant", graph.get_last_output())

            elif data.get("type") == "edit_code":
                block_id = data.get("block_id")
                new_source = data.get("new_source", "")
                auto_run = data.get("auto_run", True)
                log.info(f"Edit block {block_id}: re-running...")
                if auto_run:
                    session = active_sessions[session_id]
                    async for event in session["graph"].rerun_code(new_source):
                        await ws.send_json(event)

            elif data.get("type") == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        log.info(f"WS disconnected: {session_id}")
    except Exception as e:
        log.error(f"WS error {session_id}: {e}")
    finally:
        active_sessions.pop(session_id, None)

# ── Run ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
