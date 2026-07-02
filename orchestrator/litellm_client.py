#!/usr/bin/env python3
"""
LiteLLM Unified Client for BRICKStack

Provides a single interface for 100+ LLM providers.
Use any model by name — no provider-specific code needed.

Supported Providers:
  - Local: Ollama, llama.cpp, vLLM
  - Cloud: OpenAI, Anthropic, DeepSeek, Qwen, Groq, Gemini, Cohere, Azure
  - Fallback: Automatic failover if primary fails
  - Streaming: All providers support streaming

Usage:
    from orchestrator.litellm_client import LiteLLMClient
    
    client = LiteLLMClient(model="deepseek-chat")
    async for token in client.stream("Write a Python function"):
        print(token, end="")

Or via proxy:
    litellm --config litellm_config.yaml --port 4000
    # Then use http://localhost:4000 as your OpenAI-compatible endpoint
"""

import os
import sys
import asyncio
import json
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("litellm_client")

# ── Configuration ──────────────────────────────────────────────────
@dataclass
class LiteLLMConfig:
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 120.0
    stream: bool = True
    
    # Proxy mode
    use_proxy: bool = False
    proxy_url: str = "http://localhost:4000"
    proxy_key: Optional[str] = None
    
    # Fallback
    fallback_model: Optional[str] = None
    retries: int = 3

# ── Provider Map (auto-detect model names) ──────────────────────
MODEL_ALIASES = {
    # Local
    "qwen-3b": "ollama/qwen2.5-coder:3b",
    "qwen-7b": "ollama/qwen2.5-coder:7b",
    "llama-3.2": "ollama/llama3.2",
    "phi-3": "ollama/phi3:mini",
    "local": "ollama/qwen2.5-coder:3b",
    
    # Cloud — DeepSeek
    "deepseek": "deepseek/deepseek-chat",
    "deepseek-chat": "deepseek/deepseek-chat",
    "deepseek-coder": "deepseek/deepseek-coder",
    "deepseek-reasoner": "deepseek/deepseek-reasoner",
    
    # Cloud — Qwen (Alibaba)
    "qwen": "openai/qwen2.5-coder-32b-instruct",
    "qwen-32b": "openai/qwen2.5-coder-32b-instruct",
    "qwen-coder": "openai/qwen2.5-coder-32b-instruct",
    
    # Cloud — OpenAI
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-4-turbo": "openai/gpt-4-turbo",
    "gpt-3.5-turbo": "openai/gpt-3.5-turbo",
    
    # Cloud — Anthropic
    "claude": "anthropic/claude-3-5-sonnet-20240620",
    "claude-sonnet": "anthropic/claude-3-5-sonnet-20240620",
    "claude-haiku": "anthropic/claude-3-haiku-20240307",
    
    # Cloud — Groq (fast, cheap)
    "groq-llama": "groq/llama-3.1-70b-versatile",
    "groq-mixtral": "groq/mixtral-8x7b-32768",
    "groq-gemma": "groq/gemma-2-9b-it",
    
    # Cloud — Gemini
    "gemini": "gemini/gemini-1.5-pro",
    "gemini-pro": "gemini/gemini-1.5-pro",
    "gemini-flash": "gemini/gemini-1.5-flash",
}

# ── Environment Keys by Provider ──────────────────────────────────
ENV_KEYS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "qwen": "QWEN_API_KEY",
    "azure": "AZURE_API_KEY",
    "cohere": "COHERE_API_KEY",
}

def resolve_model_alias(name: str) -> str:
    """Convert friendly name to LiteLLM model string."""
    return MODEL_ALIASES.get(name.lower(), name)

def detect_provider(model: str) -> str:
    """Detect provider prefix from model name."""
    if model.startswith("ollama/"):
        return "ollama"
    if model.startswith("openai/"):
        return "openai"  # or qwen via base_url
    parts = model.split("/")
    if len(parts) > 1:
        return parts[0]
    # Try to infer from env
    for provider, key in ENV_KEYS.items():
        if os.getenv(key):
            return provider
    return "openai"  # default

def get_api_key(provider: str) -> Optional[str]:
    """Get API key for provider from environment."""
    key_name = ENV_KEYS.get(provider)
    if key_name:
        return os.getenv(key_name)
    # Try generic keys
    return os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")

def get_api_base(provider: str) -> Optional[str]:
    """Get API base URL for provider."""
    bases = {
        "deepseek": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "openai": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "qwen": os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "ollama": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    }
    return bases.get(provider)

# ── LiteLLM Client ───────────────────────────────────────────────
class LiteLLMClient:
    """Unified async client for any LLM via LiteLLM format."""
    
    def __init__(self, config: LiteLLMConfig):
        self.config = config
        self.model = resolve_model_alias(config.model)
        self.provider = detect_provider(self.model)
        
        # Resolve credentials
        if config.use_proxy:
            self.base_url = config.proxy_url.rstrip("/")
            self.api_key = config.proxy_key or "sk-any"
        else:
            self.base_url = (config.api_base or get_api_base(self.provider) or "https://api.openai.com/v1").rstrip("/")
            self.api_key = config.api_key or get_api_key(self.provider) or ""
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        logger.info(f"LiteLLM client: model={self.model}, provider={self.provider}, base={self.base_url}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _post(self, url: str, payload: dict) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            return r
    
    async def chat(self, messages: List[Dict[str, str]], stream: bool = None) -> AsyncGenerator[str, None]:
        """Send chat completion request, yield tokens if streaming."""
        stream = stream if stream is not None else self.config.stream
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": stream,
        }
        
        url = f"{self.base_url}/chat/completions"
        
        try:
            if stream:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    async with client.stream("POST", url, headers=self.headers, json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.strip() or line.startswith(":"):
                                continue
                            if line.startswith("data: "):
                                chunk = line[6:]
                                if chunk == "[DONE]":
                                    break
                                try:
                                    data = json.loads(chunk)
                                    delta = data.get("choices", [{}])[0].get("delta", {})
                                    token = delta.get("content", "")
                                    if token:
                                        yield token
                                except (json.JSONDecodeError, IndexError, KeyError):
                                    continue
            else:
                r = await self._post(url, payload)
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                yield content
        
        except Exception as e:
            logger.error(f"LiteLLM request failed: {type(e).__name__}: {e}")
            if self.config.fallback_model and self.model != self.config.fallback_model:
                logger.info(f"Falling back to {self.config.fallback_model}")
                self.model = resolve_model_alias(self.config.fallback_model)
                self.provider = detect_provider(self.model)
                self.base_url = (self.config.api_base or get_api_base(self.provider) or self.base_url).rstrip("/")
                self.api_key = self.config.api_key or get_api_key(self.provider) or self.api_key
                self.headers["Authorization"] = f"Bearer {self.api_key}"
                async for token in self.chat(messages, stream=stream):
                    yield token
            else:
                raise
    
    async def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """Non-streaming completion, returns full string."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        result = []
        async for token in self.chat(messages, stream=False):
            result.append(token)
        return "".join(result)
    
    def get_info(self) -> dict:
        return {
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "streaming": self.config.stream,
        }

# ── Factory: Create from env/model name ──────────────────────────
def create_client(
    model_name: str = "auto",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    fallback: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> LiteLLMClient:
    """Create LiteLLMClient from model name or environment.
    
    Args:
        model_name: 'auto', 'deepseek', 'qwen', 'ollama', 'gpt-4o', etc.
        api_key: Override API key (optional)
        api_base: Override base URL (optional)
        fallback: Fallback model name if primary fails
    
    Returns:
        Configured LiteLLMClient
    
    Examples:
        client = create_client("deepseek")        # Cloud API
        client = create_client("local")           # Local Ollama
        client = create_client("qwen-32b")        # Alibaba Qwen
        client = create_client("groq-llama")      # Fast Groq inference
        client = create_client("gpt-4o-mini")     # OpenAI
    """
    if model_name == "auto":
        # Detect from environment
        for alias, resolved in MODEL_ALIASES.items():
            provider = detect_provider(resolved)
            if provider == "ollama":
                # Check if Ollama is running
                try:
                    import httpx
                    httpx.get("http://localhost:11434", timeout=2).raise_for_status()
                    model_name = alias
                    logger.info(f"Auto-detected local Ollama: {model_name}")
                    break
                except:
                    continue
            elif get_api_key(provider):
                model_name = alias
                logger.info(f"Auto-detected cloud provider: {model_name} ({provider})")
                break
        else:
            model_name = "deepseek-chat"  # final fallback
            logger.info(f"Defaulting to: {model_name}")
    
    config = LiteLLMConfig(
        model=model_name,
        api_key=api_key,
        api_base=api_base,
        fallback_model=fallback,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return LiteLLMClient(config)

# ── Direct Usage (if litellm library installed) ────────────────────
def create_litellm_sdk():
    """Create native litellm SDK client if available."""
    try:
        import litellm
        litellm.set_verbose = False
        litellm.drop_params = True  # Drop unsupported params per provider
        return litellm
    except ImportError:
        logger.warning("litellm package not installed. Using HTTP client instead.")
        return None

async def litellm_acompletion(model: str, messages: list, **kwargs):
    """Async completion using litellm SDK if available, else HTTP fallback."""
    litellm = create_litellm_sdk()
    if litellm:
        return await litellm.acompletion(model=resolve_model_alias(model), messages=messages, **kwargs)
    else:
        client = create_client(model)
        return client.chat(messages, stream=kwargs.get("stream", False))

# ── Main ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("LiteLLM BRICKStack Client Demo")
        print("=" * 50)
        
        # Show available models
        print("\nAvailable models:")
        for alias in sorted(MODEL_ALIASES.keys()):
            print(f"  • {alias:20} → {MODEL_ALIASES[alias]}")
        
        # Test auto-detect
        print("\nAuto-detecting...")
        client = create_client("auto")
        info = client.get_info()
        print(f"  Detected: {info['model']}")
        print(f"  Provider: {info['provider']}")
        print(f"  Base URL: {info['base_url']}")
        print(f"  Has Key:  {info['has_api_key']}")
    
    asyncio.run(demo())
