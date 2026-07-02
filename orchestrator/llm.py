#!/usr/bin/env python3
"""
BRICKStack LLM Orchestrator

Unified interface using LiteLLM-compatible client.
Works with any provider: DeepSeek, Qwen, OpenAI, Anthropic, Groq, Ollama, local.

Usage:
    from orchestrator.llm import get_client, stream_task
    
    client = get_client("deepseek")  # or "local", "qwen", "gpt-4o", etc.
    async for token in client.stream(messages):
        print(token, end="")
"""

import os
import logging
from typing import Optional, AsyncGenerator, List, Dict

from orchestrator.litellm_client import create_client, LiteLLMClient

logger = logging.getLogger("orchestrator.llm")

# ── Global Client Cache ─────────────────────────────────────────────
_client_cache: Dict[str, LiteLLMClient] = {}

def get_client(
    model: str = "auto",
    api_key: Optional[str] = None,
    fallback: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> LiteLLMClient:
    """Get or create LiteLLM client.
    
    Args:
        model: Model alias or full name. 'auto' detects from env.
        api_key: Override API key (optional).
        fallback: Fallback model if primary fails.
        temperature: Sampling temperature.
        max_tokens: Max tokens in response.
    
    Returns:
        Cached or new LiteLLMClient.
    
    Examples:
        client = get_client("deepseek")      # DeepSeek API
        client = get_client("local")         # Ollama/local
        client = get_client("qwen-32b")      # Qwen via Alibaba
        client = get_client("gpt-4o-mini")   # OpenAI
        client = get_client("groq-llama")    # Fast Groq inference
    """
    cache_key = f"{model}:{api_key}:{fallback}:{temperature}:{max_tokens}"
    
    if cache_key in _client_cache:
        return _client_cache[cache_key]
    
    client = create_client(
        model_name=model,
        api_key=api_key,
        fallback=fallback,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    _client_cache[cache_key] = client
    logger.info(f"LLM client created: {client.get_info()}")
    return client

async def stream_task(
    prompt: str,
    model: str = "auto",
    system: Optional[str] = None,
    history: Optional[List[Dict]] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream a task completion from any model.
    
    Args:
        prompt: User prompt.
        model: Model alias (e.g., 'deepseek', 'local', 'qwen').
        system: System prompt override.
        history: Previous messages.
        temperature: Sampling temperature.
        max_tokens: Max tokens.
    
    Yields:
        Tokens as they are generated.
    
    Example:
        async for token in stream_task("Write a Flask app", model="local"):
            print(token, end="")
    """
    client = get_client(model, temperature=temperature, max_tokens=max_tokens)
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})
    
    async for token in client.chat(messages, stream=True):
        yield token

async def complete_task(
    prompt: str,
    model: str = "auto",
    system: Optional[str] = None,
    history: Optional[List[Dict]] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """Non-streaming completion. Returns full string."""
    client = get_client(model, temperature=temperature, max_tokens=max_tokens)
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})
    
    return await client.complete(prompt, system=system)

def get_available_models() -> Dict[str, str]:
    """Return all available model aliases and their resolved names."""
    from orchestrator.litellm_client import MODEL_ALIASES
    return MODEL_ALIASES.copy()

def get_active_model() -> str:
    """Get the currently active model name."""
    client = get_client("auto")
    return client.model

# ── Backward Compatibility ──────────────────────────────────────────
async def chat(
    messages: list,
    model: str = "auto",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    stream: bool = False,
) -> AsyncGenerator[str, None]:
    """Backward-compatible chat interface."""
    client = get_client(model, api_key=api_key, temperature=0.3, max_tokens=4096)
    async for token in client.chat(messages, stream=stream):
        yield token
