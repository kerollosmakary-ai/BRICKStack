"""Production security middleware for BRICKStack."""
import os, time, hashlib, json, re
from typing import Optional, Callable
from fastapi import Request, WebSocket, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ── Rate Limiting ────────────────────────────────────────────
class RateLimiter:
    """Simple in-memory rate limiter. Use Redis in production."""
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._store = {}  # ip -> [(timestamp, count)]
    
    def _get_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        return forwarded.split(",")[0].strip() if forwarded else request.client.host
    
    def is_allowed(self, request: Request) -> bool:
        key = self._get_key(request)
        now = time.time()
        # Clean old entries
        self._store[key] = [t for t in self._store.get(key, []) if now - t < self.window]
        if len(self._store[key]) >= self.max_requests:
            return False
        self._store[key].append(now)
        return True

# ── Input Validation ───────────────────────────────────────────
class InputValidator:
    """Sanitize and validate all inputs."""
    MAX_PROMPT_LENGTH = 10000
    MAX_CODE_LENGTH = 50000
    FORBIDDEN_PATTERNS = [
        r"import\s+os\.system",
        r"subprocess\.call\s*\(\s*['\"]rm\s",
        r"__import__\s*\(\s*['\"]os['\"]\s*\).*\.system",
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        r"open\s*\(\s*['\"]/etc/passwd",
        r"open\s*\(\s*['\"]/etc/shadow",
    ]
    
    @classmethod
    def validate_prompt(cls, prompt: str) -> str:
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Prompt must be a non-empty string")
        if len(prompt) > cls.MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt too long (max {cls.MAX_PROMPT_LENGTH} chars)")
        # Remove null bytes and control chars
        prompt = prompt.replace('\x00', '').replace('\x01', '').replace('\x02', '')
        return prompt.strip()
    
    @classmethod
    def validate_code(cls, code: str) -> str:
        if not code or not isinstance(code, str):
            raise ValueError("Code must be a non-empty string")
        if len(code) > cls.MAX_CODE_LENGTH:
            raise ValueError(f"Code too long (max {cls.MAX_CODE_LENGTH} chars)")
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                raise ValueError(f"Forbidden pattern detected in code: {pattern[:50]}...")
        return code

# ── Auth Middleware ────────────────────────────────────────────
class AuthMiddleware(BaseHTTPMiddleware):
    """JWT-based auth for REST endpoints. WebSocket uses token in query param."""
    def __init__(self, app, exempt_paths: Optional[list] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or ["/api/health", "/", "/static", "/docs", "/openapi.json"]
        self.jwt_secret = os.getenv("JWT_SECRET", "change-me")
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip exempt paths
        if any(request.url.path.startswith(p) for p in self.exempt_paths):
            return await call_next(request)
        
        # Check Authorization header
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"}
            )
        
        token = auth[7:]
        if not self._verify_token(token):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid or expired token"}
            )
        
        return await call_next(request)
    
    def _verify_token(self, token: str) -> bool:
        try:
            import hmac
            expected = hmac.new(self.jwt_secret.encode(), b"brickstack", hashlib.sha256).hexdigest()[:32]
            return hmac.compare_digest(token, expected)
        except Exception:
            return False

# ── Rate Limit Middleware ─────────────────────────────────────
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or RateLimiter(max_requests=60, window_seconds=60)
    
    async def dispatch(self, request: Request, call_next: Callable):
        if not self.limiter.is_allowed(request):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Try again later."}
            )
        return await call_next(request)

# ── Security Headers ─────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:;"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

# ── WebSocket Auth Helper ────────────────────────────────────
async def verify_ws_token(websocket: WebSocket) -> bool:
    """Verify token from WebSocket query param."""
    token = websocket.query_params.get("token", "")
    if not token:
        return False
    secret = os.getenv("JWT_SECRET", "change-me")
    import hmac, hashlib
    expected = hmac.new(secret.encode(), b"brickstack", hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(token, expected)

def generate_token() -> str:
    """Generate a secure API token."""
    import hmac, hashlib, secrets
    secret = os.getenv("JWT_SECRET", secrets.token_hex(32))
    return hmac.new(secret.encode(), b"brickstack", hashlib.sha256).hexdigest()[:32]
