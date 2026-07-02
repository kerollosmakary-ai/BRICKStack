#!/usr/bin/env python3
"""Run a task through BRICKStack backend and stream results."""
import asyncio, websockets, json, sys, os

async def run_task(prompt: str):
    uri = "ws://localhost:8000/ws"
    task_id = f"cli-{asyncio.get_event_loop().time()}"
    
    print(f"🔄 Connecting to BRICKStack backend...")
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "type": "user_message",
            "content": prompt,
            "task_id": task_id,
            "user_id": "cli-user",
            "session_context": {}
        }))
        
        print(f"📨 Task sent: {prompt[:80]}...")
        print("-" * 50)
        
        async for raw in ws:
            msg = json.loads(raw)
            mtype = msg.get("type")
            
            if mtype == "thought":
                print(f"🤔 [{msg.get('agent', 'AI')}]: {msg.get('content', '')[:200]}")
            elif mtype == "code":
                chunk = msg.get("chunk", "")
                if chunk:
                    print(chunk, end="", flush=True)
            elif mtype == "terminal":
                print(f"\n🖥️  [OUTPUT]:\n{msg.get('content', '')[:500]}")
            elif mtype == "assistant":
                chunk = msg.get("chunk", "")
                if chunk:
                    print(chunk, end="", flush=True)
            elif mtype == "done":
                print("\n" + "-" * 50)
                print("✅ Done!")
                break
            elif mtype == "error":
                print(f"\n❌ Error: {msg.get('content', '')}")
                break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_task.py 'your prompt here'")
        sys.exit(1)
    prompt = " ".join(sys.argv[1:])
    asyncio.run(run_task(prompt))
