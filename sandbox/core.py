import docker, tempfile, os

class Sandbox:
    def __init__(self):
        self.client = docker.from_env()

    def run(self, code: str, language: str = "python"):
        with tempfile.TemporaryDirectory() as tmp:
            ext = "py" if language == "python" else "js"
            file_path = os.path.join(tmp, f"script.{ext}")
            with open(file_path, "w") as f:
                f.write(code)

            image = "python:3.11-slim" if language == "python" else "node:18-slim"
            cmd = f"python /workspace/script.{ext}" if language == "python" else f"node /workspace/script.{ext}"

            result = self.client.containers.run(
                image,
                command=cmd,
                volumes={tmp: {"bind": "/workspace", "mode": "ro"}},
                mem_limit="128m",
                cpu_quota=50000,
                network_disabled=True,
                remove=True,
                stdout=True,
                stderr=True,
                timeout=10,
            )
            return result.decode("utf-8")
