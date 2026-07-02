#!/usr/bin/env python3
"""
Qwen Code CLI — Terminal AI Coding Assistant
Supports: Qwen, DeepSeek, OpenAI, Ollama (local)

Usage:
    python qwen_cli.py                    # Interactive mode
    python qwen_cli.py "write fibonacci"  # One-shot mode
    python qwen_cli.py --provider qwen   # Use Qwen API
    python qwen_cli.py --model qwen2.5-coder-32b-instruct
"""

import os, sys, json, asyncio, argparse, textwrap, subprocess, re
from typing import Optional, AsyncGenerator
from pathlib import Path
from dataclasses import dataclass

# Load .env
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'""))
from typing import Optional, AsyncGenerator
from pathlib import Path
from dataclasses import dataclass

import httpx
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.spinner import Spinner
from rich.text import Text
from rich import box
from rich.align import Align

# ── Configuration ───────────────────────────────────────────────
@dataclass
class Config:
    provider: str = "auto"
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    stream: bool = True
    execute: bool = False
    temperature: float = 0.3
    max_tokens: int = 4096

# ── Provider Registry ───────────────────────────────────────────
PROVIDERS = {
    "qwen": {
        "env_key": "QWEN_API_KEY",
        "env_url": "QWEN_BASE_URL",
        "env_model": "QWEN_MODEL",
        "default_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen2.5-coder-32b-instruct",
        "models": [
            "qwen2.5-coder-7b-instruct",
            "qwen2.5-coder-32b-instruct",
            "qwen2.5-72b-instruct",
            "qwen2.5-7b-instruct",
        ],
    },
    "deepseek": {
        "env_key": "LLM_API_KEY",
        "env_url": "LLM_BASE_URL",
        "env_model": "LLM_MODEL",
        "default_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "env_url": "OPENAI_BASE_URL",
        "env_model": "OPENAI_MODEL",
        "default_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    },
    "ollama": {
        "env_key": "",
        "env_url": "OLLAMA_BASE_URL",
        "env_model": "OLLAMA_MODEL",
        "default_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5-coder:7b",
        "models": ["qwen2.5-coder:7b", "qwen2.5-coder:14b", "llama3.2", "codellama"],
    },
}

# ── LLM Client ──────────────────────────────────────────────────
class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.provider = self._detect_provider()
        self.api_key = config.api_key or os.getenv(PROVIDERS[self.provider]["env_key"], "")
        self.base_url = (config.base_url or os.getenv(PROVIDERS[self.provider]["env_url"], PROVIDERS[self.provider]["default_url"])).rstrip("/")
        self.model = config.model or os.getenv(PROVIDERS[self.provider]["env_model"], PROVIDERS[self.provider]["default_model"])
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def _detect_provider(self) -> str:
        if self.config.provider != "auto":
            return self.config.provider
        # Auto-detect based on available keys
        for name, cfg in PROVIDERS.items():
            if cfg["env_key"] and os.getenv(cfg["env_key"]):
                return name
        # Default to deepseek if nothing found
        return "deepseek"

    async def chat(self, messages: list, stream: bool = True) -> AsyncGenerator[str, None]:
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": stream,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            if stream:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions",
                    headers=self.headers, json=data
                ) as response:
                    response.raise_for_status()
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
            else:
                r = await client.post(f"{self.base_url}/chat/completions", headers=self.headers, json=data)
                r.raise_for_status()
                yield r.json()["choices"][0]["message"]["content"]

    def get_info(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "has_key": bool(self.api_key),
        }

# ── Code Extractor & Executor ───────────────────────────────────
class CodeExecutor:
    @staticmethod
    def extract_code(text: str, language: str = "python") -> str:
        # Try to extract code from markdown blocks
        pattern = rf"```{language}\s*\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Try any code block
        match = re.search(r"```\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Try indented code (4 spaces)
        lines = text.split("\n")
        code_lines = []
        in_code = False
        for line in lines:
            if line.startswith("    ") or line.startswith("\t"):
                code_lines.append(line.lstrip())
                in_code = True
            elif in_code and line.strip() == "":
                code_lines.append(line)
            else:
                if in_code:
                    break
        if code_lines:
            return "\n".join(code_lines).strip()
        return text.strip()

    @staticmethod
    def execute(code: str, language: str = "python") -> dict:
        if language != "python":
            return {"success": False, "output": "", "error": "Only Python execution supported"}
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=30
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout[:5000],
                "error": result.stderr[:5000] if result.returncode != 0 else "",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Execution timed out (30s)"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

# ── CLI Application ─────────────────────────────────────────────
class QwenCLI:
    def __init__(self, config: Config):
        self.config = config
        self.console = Console()
        self.client = LLMClient(config)
        self.history = []
        self.system_prompt = """You are an expert coding assistant. You write clean, efficient, well-documented code.
When asked to write code, provide complete, runnable solutions with explanations.
Use markdown formatting with code blocks."""

    def banner(self):
        table = Table(
            box=box.ROUNDED,
            show_header=False,
            border_style="bright_blue",
            padding=(0, 2),
        )
        table.add_column(style="bold cyan")
        table.add_column(style="dim")
        
        info = self.client.get_info()
        table.add_row("Qwen Code CLI", "v1.0")
        table.add_row("Provider", info["provider"].upper())
        table.add_row("Model", info["model"])
        table.add_row("Base URL", info["base_url"])
        table.add_row("API Key", "✓ Set" if info["has_key"] else "✗ Not set")
        
        self.console.print()
        self.console.print(Align.center(table))
        self.console.print()
        self.console.print("[dim]Type your request or 'help' for commands. Ctrl+C to exit.[/dim]")
        self.console.print()

    def show_help(self):
        help_text = """
## Commands

- **/help** — Show this help
- **/clear** — Clear conversation history
- **/model** — Change model
- **/provider** — Switch LLM provider
- **/execute** — Toggle auto-execution
- **/history** — Show conversation history
- **/save** — Save last response to file
- **/quit** — Exit

## Examples

- "Write a Python function to sort a list"
- "Build a Flask API with CRUD endpoints"
- "Explain how quicksort works"
- "Debug this code: [paste code]"
        """
        self.console.print(Markdown(help_text))

    def render_code(self, code: str, language: str = "python"):
        syntax = Syntax(code, language, theme="monokai", line_numbers=True, word_wrap=True)
        self.console.print(Panel(syntax, border_style="blue", title=f"[bold]{language}[/bold]", title_align="left"))

    def render_output(self, result: dict):
        if result["success"]:
            if result["output"]:
                self.console.print(Panel(
                    result["output"].strip(),
                    title="[green]Output[/green]",
                    border_style="green",
                    title_align="left",
                ))
            else:
                self.console.print("[dim green]✓ Executed successfully (no output)[/dim green]")
        else:
            self.console.print(Panel(
                result["error"].strip() or "Unknown error",
                title="[red]Error[/red]",
                border_style="red",
                title_align="left",
            ))

    async def stream_response(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        for h in self.history[-6:]:
            messages.append({"role": "user", "content": h["prompt"]})
            messages.append({"role": "assistant", "content": h["response"]})
        messages.append({"role": "user", "content": prompt})

        full_response = []
        
        with self.console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots"):
            async for token in self.client.chat(messages, stream=True):
                full_response.append(token)

        response_text = "".join(full_response)
        
        # Render response
        self.console.print()
        
        # Check for code blocks
        code_blocks = re.findall(r"```(\w+)?\s*\n(.*?)\n```", response_text, re.DOTALL)
        
        if code_blocks:
            # Split by code blocks and render each part
            parts = re.split(r"```\w*\s*\n.*?\n```", response_text, flags=re.DOTALL)
            for i, part in enumerate(parts):
                if part.strip():
                    self.console.print(Markdown(part.strip()))
                if i < len(code_blocks):
                    lang, code = code_blocks[i]
                    lang = lang or "python"
                    self.render_code(code, lang)
                    
                    # Auto-execute if enabled
                    if self.config.execute and lang == "python":
                        self.console.print("[dim]▶ Executing...[/dim]")
                        result = CodeExecutor.execute(code)
                        self.render_output(result)
        else:
            self.console.print(Markdown(response_text))
        
        self.console.print()
        
        # Save to history
        self.history.append({"prompt": prompt, "response": response_text})
        return response_text

    async def run_one_shot(self, prompt: str):
        self.banner()
        self.console.print(f"[bold]You:[/bold] {prompt}")
        self.console.print()
        await self.stream_response(prompt)

    async def run_interactive(self):
        self.banner()
        
        while True:
            try:
                user_input = Prompt.ask("[bold green]›[/bold green]").strip()
                
                if not user_input:
                    continue
                
                if user_input.startswith("/"):
                    await self.handle_command(user_input)
                    continue
                
                await self.stream_response(user_input)
                
            except KeyboardInterrupt:
                self.console.print("\n[dim]Interrupted. Type /quit to exit.[/dim]")
            except EOFError:
                break
        
        self.console.print("\n[bold cyan]Goodbye![/bold cyan]")

    async def handle_command(self, cmd: str):
        parts = cmd.split()
        cmd_name = parts[0].lower()
        
        if cmd_name == "/help" or cmd_name == "/h":
            self.show_help()
        
        elif cmd_name == "/clear":
            self.history.clear()
            self.console.print("[dim]History cleared.[/dim]")
        
        elif cmd_name == "/quit" or cmd_name == "/q":
            raise SystemExit
        
        elif cmd_name == "/execute":
            self.config.execute = not self.config.execute
            status = "ON" if self.config.execute else "OFF"
            self.console.print(f"[dim]Auto-execute: {status}[/dim]")
        
        elif cmd_name == "/history":
            if not self.history:
                self.console.print("[dim]No history.[/dim]")
            else:
                for i, h in enumerate(self.history[-10:], 1):
                    self.console.print(f"[dim]{i}.[/dim] {h['prompt'][:60]}...")
        
        elif cmd_name == "/model":
            if len(parts) > 1:
                self.config.model = parts[1]
                self.client.model = parts[1]
                self.console.print(f"[dim]Model set to: {parts[1]}[/dim]")
            else:
                provider = self.client.provider
                models = PROVIDERS[provider]["models"]
                self.console.print(f"[dim]Available models for {provider}:[/dim]")
                for m in models:
                    current = " ← current" if m == self.client.model else ""
                    self.console.print(f"  • {m}{current}")
        
        elif cmd_name == "/provider":
            if len(parts) > 1:
                name = parts[1].lower()
                if name in PROVIDERS:
                    self.config.provider = name
                    self.client = LLMClient(self.config)
                    self.console.print(f"[dim]Switched to: {name.upper()}[/dim]")
                else:
                    self.console.print(f"[red]Unknown provider: {name}[/red]")
            else:
                self.console.print("[dim]Available providers:[/dim]")
                for name in PROVIDERS:
                    current = " ← current" if name == self.client.provider else ""
                    self.console.print(f"  • {name}{current}")
        
        elif cmd_name == "/save":
            if not self.history:
                self.console.print("[red]No history to save.[/red]")
            else:
                last = self.history[-1]["response"]
                filename = f"qwen_output_{len(self.history)}.md"
                with open(filename, "w") as f:
                    f.write(last)
                self.console.print(f"[dim]Saved to: {filename}[/dim]")
        
        else:
            self.console.print(f"[red]Unknown command: {cmd_name}[/red]")
            self.console.print("[dim]Type /help for available commands.[/dim]")

# ── Main Entry ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Qwen Code CLI — Terminal AI Coding Assistant")
    parser.add_argument("prompt", nargs="?", help="Prompt to send (one-shot mode)")
    parser.add_argument("--provider", "-p", choices=list(PROVIDERS.keys()) + ["auto"], default="auto", help="LLM provider")
    parser.add_argument("--model", "-m", help="Model name")
    parser.add_argument("--api-key", "-k", help="API key")
    parser.add_argument("--base-url", "-u", help="Base URL")
    parser.add_argument("--execute", "-e", action="store_true", help="Auto-execute code")
    parser.add_argument("--temperature", "-t", type=float, default=0.3, help="Temperature")
    
    args = parser.parse_args()
    
    config = Config(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        execute=args.execute,
        temperature=args.temperature,
    )
    
    cli = QwenCLI(config)
    
    try:
        if args.prompt:
            asyncio.run(cli.run_one_shot(args.prompt))
        else:
            asyncio.run(cli.run_interactive())
    except SystemExit:
        pass
    except Exception as e:
        console = Console()
        console.print(f"[red]Error: {e}[/red]")
        raise

if __name__ == "__main__":
    main()
