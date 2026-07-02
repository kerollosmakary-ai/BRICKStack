#!/usr/bin/env python3
"""
Qwen Code CLI — LiteLLM Edition

Unified terminal AI coding assistant supporting 100+ providers via LiteLLM:
  DeepSeek, Qwen, OpenAI, Anthropic, Groq, Ollama, local models, etc.

Usage:
    python3 qwen_cli.py "write a fibonacci function"          # Auto-detect model
    python3 qwen_cli.py "write a web scraper" --model local   # Use local Ollama
    python3 qwen_cli.py --model deepseek --stream               # Stream output
    python3 qwen_cli.py --interactive                         # REPL mode

Environment:
    LLM_MODEL=deepseek  (default model alias)
    DEEPSEEK_API_KEY=... (for DeepSeek)
    OPENAI_API_KEY=...   (for OpenAI)
    OLLAMA_BASE_URL=...  (for local, default: http://localhost:11434)
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from typing import Optional, List, Dict
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich import box
from rich.table import Table
from rich.align import Align

from orchestrator.litellm_client import create_client, LiteLLMClient, MODEL_ALIASES

logging.basicConfig(level=logging.WARNING, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("qwen_cli")

console = Console()

# ── Agent Prompts ──────────────────────────────────────────────────
AGENTS = {
    "code": "You are an expert software engineer. Write clean, efficient, well-documented code. Include type hints and error handling. Output the code block first, then a brief explanation.",
    "review": "You are a senior code reviewer. Check for bugs, security vulnerabilities, performance issues, and style problems. Provide severity ratings: Critical/Warning/Suggestion.",
    "explain": "You are a patient teacher. Explain this code step by step: what it does, how each part works, and key concepts used. Use simple analogies.",
    "plan": "You are a technical project manager. Break this task into numbered steps with file names, function names, and complexity estimates.",
    "debug": "You are a debugging expert. Identify the root cause, explain why it fails, provide corrected code, and add a test case.",
    "chat": "You are a helpful coding assistant. Be concise and accurate.",
}

# ── CLI Application ───────────────────────────────────────────────
class QwenCLI:
    def __init__(self, model: str = "auto", stream: bool = True, temperature: float = 0.3):
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.history: List[Dict] = []
        self.max_history = 10

    def get_client(self) -> LiteLLMClient:
        return create_client(model_name=self.model, temperature=self.temperature, max_tokens=4096)

    def banner(self):
        info = self.get_client().get_info()
        table = Table(box=box.ROUNDED, show_header=False, border_style="bright_blue", padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="dim")
        table.add_row("Qwen Code CLI", "v2.0 (LiteLLM)")
        table.add_row("Provider", info["provider"].upper())
        table.add_row("Model", info["model"])
        table.add_row("Base URL", info["base_url"])
        table.add_row("API Key", "✅ Set" if info["has_api_key"] else "⚠️ Not set")
        table.add_row("Streaming", "✅" if info["streaming"] else "❌")
        console.print()
        console.print(Align.center(table))
        console.print()

    def show_help(self):
        help_text = """
## Commands

- **/help** — Show this help
- **/clear** — Clear conversation history
- **/model** — Show or switch model
- **/models** — List all available models
- **/execute** — Toggle auto-execution
- **/history** — Show conversation history
- **/quit** — Exit

## Model Aliases

- **local** / qwen-3b / qwen-7b — Local Ollama models (offline)
- **deepseek** / deepseek-coder — DeepSeek API
- **qwen** / qwen-32b — Qwen via Alibaba (API key needed)
- **gpt-4o** / gpt-4o-mini — OpenAI
- **claude** / claude-sonnet — Anthropic Claude
- **gemini** / gemini-pro — Google Gemini
- **groq-llama** / groq-mixtral — Groq (fast inference)

## Examples

```bash
python qwen_cli.py "write a Python web scraper" --model local
python qwen_cli.py "review this code" --model deepseek --mode review
python qwen_cli.py --interactive --model gpt-4o-mini
python qwen_cli.py "explain quicksort" --model qwen --stream
```
        """
        console.print(Markdown(help_text))

    def render_code(self, code: str, language: str = "python"):
        syntax = Syntax(code, language, theme="monokai", line_numbers=True, word_wrap=True)
        console.print(Panel(syntax, border_style="blue", title=f"[bold]{language}[/bold]", title_align="left"))

    def render_output(self, text: str, title: str = "Output", color: str = "green"):
        console.print(Panel(text.strip(), title=f"[{color}]{title}[/color]", border_style=color, title_align="left"))

    async def ask(self, prompt: str, system: str, stream: bool = None) -> str:
        client = self.get_client()
        stream = stream if stream is not None else self.stream
        
        messages = [{"role": "system", "content": system}]
        for h in self.history[-self.max_history:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": prompt})
        
        if stream:
            with console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots"):
                result = []
                async for token in client.chat(messages, stream=True):
                    result.append(token)
            response = "".join(result)
        else:
            with console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots"):
                response = await client.complete(prompt, system=system)
        
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": response})
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2:]
        
        return response

    async def run_agent(self, prompt: str, mode: str = "code"):
        system = AGENTS.get(mode, AGENTS["chat"])
        response = await self.ask(prompt, system, stream=self.stream)
        
        console.print()
        if "```" in response:
            import re
            code_blocks = re.findall(r"```(\w+)?\s*\n(.*?)\n```", response, re.DOTALL)
            parts = re.split(r"```\w*\s*\n.*?\n```", response, flags=re.DOTALL)
            for i, part in enumerate(parts):
                if part.strip():
                    console.print(Markdown(part.strip()))
                if i < len(code_blocks):
                    lang, code = code_blocks[i]
                    self.render_code(code, lang or "python")
        else:
            console.print(Markdown(response))
        console.print()

    async def run_pipeline(self, task: str):
        console.print(f"\n[bold]Task:[/bold] {task}\n")
        
        # Step 1: Plan
        console.print("[bold yellow]Step 1: Planner[/bold yellow]")
        plan = await self.ask(f"Break this task into steps: {task}", AGENTS["plan"], stream=False)
        console.print(Markdown(plan))
        console.print()
        
        # Step 2: Code
        console.print("[bold yellow]Step 2: Coder[/bold yellow]")
        code = await self.ask(f"Task: {task}\n\nPlan:\n{plan}\n\nWrite the complete code.", AGENTS["code"], stream=False)
        self.render_code(code, "python")
        
        # Step 3: Review
        console.print("[bold yellow]Step 3: Reviewer[/bold yellow]")
        review = await self.ask(f"Review this code:\n\n{code}", AGENTS["review"], stream=False)
        console.print(Markdown(review))
        
        # Summary
        console.print(f"\n[bold green]✅ Pipeline Complete[/bold green]")
        console.print(f"  Model: {self.model}")
        console.print(f"  Plan: {len(plan)} chars")
        console.print(f"  Code: {len(code)} chars")
        console.print(f"  Review: {len(review)} chars\n")

    async def run_interactive(self):
        self.banner()
        console.print("[dim]Type /help for commands. Ctrl+C to exit.[/dim]\n")
        
        while True:
            try:
                user_input = Prompt.ask("[bold green]›[/bold green]").strip()
                if not user_input:
                    continue
                
                if user_input.startswith("/"):
                    await self.handle_command(user_input)
                    continue
                
                await self.run_agent(user_input, "chat")
                
            except (KeyboardInterrupt, EOFError):
                break
        console.print("\n[bold cyan]Goodbye![/bold cyan]\n")

    async def handle_command(self, cmd: str):
        parts = cmd.split()
        cmd_name = parts[0].lower()
        
        if cmd_name == "/help" or cmd_name == "/h":
            self.show_help()
        elif cmd_name == "/clear":
            self.history.clear()
            console.print("[dim]History cleared.[/dim]")
        elif cmd_name == "/quit" or cmd_name == "/q":
            raise SystemExit
        elif cmd_name == "/history":
            for i, h in enumerate(self.history[-10:], 1):
                console.print(f"[dim]{i}.[/dim] {h['role']}: {h['content'][:60]}...")
        elif cmd_name == "/model":
            if len(parts) > 1:
                alias = parts[1].lower()
                if alias in MODEL_ALIASES or alias == "auto":
                    self.model = alias
                    console.print(f"[dim]Model switched to: {alias}[/dim]")
                    self.banner()
                else:
                    console.print(f"[red]Unknown model: {alias}[/red]")
                    console.print("[dim]Use /models to see all available.[/dim]")
            else:
                self.banner()
        elif cmd_name == "/models":
            console.print("[bold]Available Models:[/bold]")
            for alias in sorted(MODEL_ALIASES.keys()):
                resolved = MODEL_ALIASES[alias]
                current = " ← current" if alias == self.model else ""
                console.print(f"  • {alias:20} → {resolved}{current}")
        elif cmd_name == "/save":
            if not self.history:
                console.print("[red]No history to save.[/red]")
            else:
                last = self.history[-1]["content"]
                filename = f"qwen_output_{len(self.history)}.md"
                with open(filename, "w") as f:
                    f.write(last)
                console.print(f"[dim]Saved to: {filename}[/dim]")
        else:
            console.print(f"[red]Unknown command: {cmd_name}[/red]")

# ── Main Entry ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Qwen Code CLI — LiteLLM Edition")
    parser.add_argument("prompt", nargs="?", help="Prompt to send (one-shot mode)")
    parser.add_argument("--model", "-m", default=os.getenv("LLM_MODEL", "auto"), help="Model alias (e.g., deepseek, local, qwen, gpt-4o)")
    parser.add_argument("--mode", choices=list(AGENTS.keys()), default="code", help="Agent mode")
    parser.add_argument("--stream", "-s", action="store_true", default=True, help="Stream output")
    parser.add_argument("--no-stream", dest="stream", action="store_false", help="Non-streaming mode")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive REPL mode")
    parser.add_argument("--temperature", "-t", type=float, default=0.3, help="Sampling temperature")
    parser.add_argument("--pipeline", "-p", action="store_true", help="Run multi-agent pipeline")
    
    args = parser.parse_args()
    
    cli = QwenCLI(model=args.model, stream=args.stream, temperature=args.temperature)
    
    try:
        if args.interactive:
            asyncio.run(cli.run_interactive())
        elif args.pipeline and args.prompt:
            asyncio.run(cli.run_pipeline(args.prompt))
        elif args.prompt:
            cli.banner()
            console.print(f"[bold]You:[/bold] {args.prompt}\n")
            asyncio.run(cli.run_agent(args.prompt, args.mode))
        else:
            parser.print_help()
            print("\nExamples:")
            print('  python qwen_cli.py "write a Fibonacci function"')
            print('  python qwen_cli.py "write a web scraper" --model local')
            print('  python qwen_cli.py --interactive --model deepseek')
            print('  python qwen_cli.py "build a todo API" --pipeline')
    except SystemExit:
        pass
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise

if __name__ == "__main__":
    main()
