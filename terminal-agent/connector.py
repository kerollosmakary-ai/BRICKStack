#!/usr/bin/env python3
"""
Connector script — run alongside the Node.js server.
Watches for build requests and bridges to the BRICKStack orchestration layer.
"""
import json, os, sys, time, http.server
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
WORKSPACE = DATA_DIR / "workspace"
EXPORTS = DATA_DIR / "exports"

class BridgeHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/bridge-status":
            self.send_json({
                "status": "connected",
                "backend": os.environ.get("BACKEND_URL", "http://backend:8000"),
                "workspace": str(WORKSPACE),
                "mode": "hybrid"
            })
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == "__main__":
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("BRIDGE_PORT", 4500))
    server = http.server.HTTPServer(("0.0.0.0", port), BridgeHandler)
    print(f"🔗 Bridge listening on {port}")
    server.serve_forever()
