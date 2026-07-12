#!/usr/bin/env python3
"""
Search Bridge — connects the Node.js terminal agent to the Python BRICKStack backend.
This is the 'brushbut' engine: fast C++ search + DB query layer.
"""
import subprocess, json, sys, os

def search(query: str, backend_url: str = "http://backend:8000"):
    """Proxy search queries to the existing BRICKStack backend."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{backend_url}/search",
            data=json.dumps({"query": query}).encode(),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e), "query": query}

def fast_search(query: str):
    """Local C++ fast path (falls back to Python if C++ binary not found)."""
    cpp_bin = "/usr/local/bin/fast_search"
    if os.path.exists(cpp_bin):
        try:
            result = subprocess.run(
                [cpp_bin, query],
                capture_output=True, text=True, timeout=10
            )
            return json.loads(result.stdout)
        except:
            pass
    return {"fallback": True, "result": f"Simulated fast result for: {query}"}

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "test"
    print(json.dumps(fast_search(q)))
