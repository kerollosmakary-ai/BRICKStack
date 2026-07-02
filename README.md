# 🧱 BRICKStack Studio — Full Stack Project

A multi-agent AI coding platform with:
- Chat UI (locked rich text, edit, re-run)
- Multi-agent orchestrator (Planner → Coder → Terminal → Reviewer → Writer)
- Persistent terminal sandbox
- File tree workspace
- Forever storage

## Structure

```
brickstack-studio/
├── frontend/              # HTML/JS/CSS chat UI
│   ├── index.html         # Main app (single page)
│   ├── style.css          # Locked/editable code, tree, bubbles
│   └── app.js             # WebSocket, rendering, edit flow
│
├── backend/               # FastAPI + WebSocket gateway
│   ├── main.py            # API + WS server
│   ├── auth.py            # Session & rate limiting
│   └── requirements.txt
│
├── orchestrator/          # LangGraph multi-agent brain
│   ├── graph.py           # Agent flow (plan → code → run → review → write)
│   ├── agents.py          # 5 agent definitions
│   └── schemas.py         # State & message types
│
├── sandbox/               # Docker execution environment
│   ├── Dockerfile         # Isolated Python/Node/Shell environment
│   └── runner.py          # PTY terminal manager
│
└── storage/               # Persistence layer
    ├── db.py              # Postgres + Redis clients
    └── models.py          # Chat, session, file models
```

## Data Flow (end-to-end)

```
User types → index.html → WebSocket → FastAPI
  → LangGraph orchestrator
    → PlannerAgent (breaks task into steps)
    → CoderAgent (writes files in sandbox)
    → TerminalAgent (runs commands in PTY, streams output)
    → ReviewerAgent (checks quality)
    → WriterAgent (formats markdown answer)
  → Streams result back over WebSocket
  → Frontend renders: 🔒 locked rich text
  → User clicks ✏️ Edit → edits code block → ✅ Save → re-executes
  → Everything saved to Postgres forever
```
