import os, httpx, json, asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional

class LLMClient:
    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        self._fallback = not self.api_key

    async def chat_complete(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int = 4096, response_format: Optional[Dict] = None) -> str:
        if self._fallback:
            return "[MOCK LLM] Fallback response."
        data = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if response_format:
            data["response_format"] = response_format
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base_url}/chat/completions", headers=self.headers, json=data)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def stream(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        if self._fallback:
            yield "[MOCK STREAM] "
            for ch in "This is a simulated streaming response from the LLM. It appears token by token to give a live typing effect in the UI.":
                yield ch
                await asyncio.sleep(0.01)
            return
        data = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", headers=self.headers, json=data) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            break
                        try:
                            delta = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            pass
