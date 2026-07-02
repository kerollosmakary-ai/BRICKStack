"""
Sandbox runner — Docker-based PTY execution environment
Isolated Linux containers for safe code execution
"""
import os, json, asyncio, logging
from typing import Optional

log = logging.getLogger("sandbox")

# ── Config ──
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "python:3.12-slim")
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "120"))
SANDBOX_MEMORY = os.getenv("SANDBOX_MEMORY", "512m")
SANDBOX_CPU = float(os.getenv("SANDBOX_CPU", "1.0"))

class SandboxRunner:
    """Manages isolated PTY sessions for code execution"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.container_id: Optional[str] = None
        self.workdir = f"/workspace/{session_id}"

    async def start(self):
        """Boot a sandbox container"""
        log.info(f"Starting sandbox for {self.session_id}")
        # In prod: docker run -d --rm --memory={SANDBOX_MEMORY} --cpus={SANDBOX_CPU} {SANDBOX_IMAGE} sleep infinity
        self.container_id = f"sandbox-{self.session_id[:8]}"
        return self.container_id

    async def run_command(self, command: str) -> dict:
        """Execute a command in the sandbox, return stdout/stderr/exit_code"""
        log.info(f"Sandbox exec: {command[:60]}...")
        # In prod: docker exec {container_id} sh -c "{command}"
        # Simulated for now:
        if "python" in command or "count" in command:
            stdout = "Found 8 files\n  main.py (320 bytes)\n  app.py (1200 bytes)"
            stderr = ""
            exit_code = 0
        elif "error" in command.lower():
            stdout = ""
            stderr = "Traceback (most recent call last):\n  File \"<stdin>\", line 1, in <module>\nNameError: name 'x' is not defined"
            exit_code = 1
        else:
            stdout = "Command completed."
            stderr = ""
            exit_code = 0

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }

    async def write_file(self, path: str, content: str):
        """Write a file inside the sandbox"""
        log.info(f"Sandbox write: {path}")
        # docker exec {container_id} sh -c "cat > {path} << 'EOF'\n{content}\nEOF"
        return True

    async def read_file(self, path: str) -> str:
        """Read a file from inside the sandbox"""
        log.info(f"Sandbox read: {path}")
        return "# File contents would be read from sandbox"

    async def stop(self):
        """Kill the sandbox container"""
        if self.container_id:
            log.info(f"Stopping sandbox {self.container_id}")
            # docker stop {container_id}
            self.container_id = None

    async def list_files(self, path: str = ".") -> list:
        """List files in sandbox workspace"""
        return [
            {"name": "main.py", "size": 320, "type": "file"},
            {"name": "app.py", "size": 1200, "type": "file"},
            {"name": "requirements.txt", "size": 450, "type": "file"},
            {"name": "README.md", "size": 1440, "type": "file"},
        ]
