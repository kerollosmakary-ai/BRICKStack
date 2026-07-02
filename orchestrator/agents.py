import asyncio, json, subprocess, sys, textwrap, re
from .llm import LLMClient
from typing import AsyncGenerator, Dict, Any

# DeepSeek-compatible JSON extraction
def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try to find JSON in code blocks
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block:
        text = code_block.group(1)
    # Try to find raw JSON object/array
    obj_match = re.search(r'\{.*\}', text, re.DOTALL)
    if obj_match:
        text = obj_match.group(0)
    arr_match = re.search(r'\[.*\]', text, re.DOTALL)
    if arr_match and not obj_match:
        text = arr_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"steps": ["Analyze request", "Draft solution", "Return answer"]}

async def planner_agent(state: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    llm = LLMClient()
    messages = [
        {"role": "system", "content": "You are a planning agent. Break down tasks into clear steps. Return your answer as a JSON object with a 'steps' array of strings."},
        {"role": "user", "content": state["prompt"]}
    ]
    result = await llm.chat_complete(messages)
    plan = _extract_json(result)
    if "steps" not in plan:
        plan = {"steps": plan.get("plan", plan.get("tasks", ["Analyze request", "Draft solution"]))}
    yield {"type": "thought", "content": f"Plan: {json.dumps(plan, indent=2)}", "agent": "planner", "task_id": state["task_id"]}
    state["plan"] = plan
    state["thoughts"] = state.get("thoughts", []) + [f"Planner: {plan}"]

async def coder_agent(state: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    llm = LLMClient()
    plan_text = json.dumps(state.get("plan", {}), indent=2)
    messages = [
        {"role": "system", "content": "You are a coding agent. Write clean, executable code. Only output the code, no explanations."},
        {"role": "user", "content": f"Task: {state['prompt']}\n\nPlan: {plan_text}\n\nWrite the necessary code."}
    ]
    code_buffer = []
    async for token in llm.stream(messages):
        code_buffer.append(token)
        yield {"type": "code", "chunk": token, "task_id": state["task_id"]}
    code = "".join(code_buffer)
    # Clean up markdown fences
    if "```" in code:
        parts = code.split("```")
        if len(parts) >= 3:
            code = parts[1]
            if code.startswith(("python", "js", "javascript", "ts", "typescript", "json", "bash", "sh")):
                code = code.split("\n", 1)[1] if "\n" in code else ""
    state["code"] = code.strip()
    state["thoughts"] = state.get("thoughts", []) + ["Coder: generated code"]

async def terminal_agent(state: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    code = state.get("code", "")
    if not code:
        yield {"type": "terminal", "content": "No code to execute", "task_id": state["task_id"]}
        return
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15
        )
        output = proc.stdout
        if proc.stderr:
            output += "\n[STDERR]\n" + proc.stderr
    except subprocess.TimeoutExpired:
        output = "Execution timed out (15s limit)"
    except Exception as e:
        output = f"Execution error: {e}"
    yield {"type": "terminal", "content": output[:5000], "task_id": state["task_id"]}
    state["execution_result"] = output

async def reviewer_agent(state: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    llm = LLMClient()
    messages = [
        {"role": "system", "content": "You are a code reviewer. Review the code and its output. Return a JSON object with 'review_ok' (boolean) and 'issues' (list of strings)."},
        {"role": "user", "content": f"Code:\n{state.get('code', '')}\n\nOutput:\n{state.get('execution_result', '')}"}
    ]
    result = await llm.chat_complete(messages)
    review = _extract_json(result)
    if "review_ok" not in review:
        review = {"review_ok": True, "issues": review.get("issues", review.get("problems", []))}
    yield {"type": "thought", "content": f"Review: {json.dumps(review, indent=2)}", "agent": "reviewer", "task_id": state["task_id"]}
    state["review"] = review
    state["thoughts"] = state.get("thoughts", []) + [f"Reviewer: {review}"]

async def writer_agent(state: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    llm = LLMClient()
    plan_text = json.dumps(state.get("plan", {}), indent=2)
    review_text = json.dumps(state.get("review", {}), indent=2)
    messages = [
        {"role": "system", "content": "You are a writer agent. Produce the final answer to the user. Be concise and helpful."},
        {"role": "user", "content": f"Task: {state['prompt']}\n\nPlan: {plan_text}\n\nCode: {state.get('code', '')}\n\nExecution: {state.get('execution_result', '')}\n\nReview: {review_text}\n\nWrite the final answer."}
    ]
    answer_parts = []
    async for token in llm.stream(messages):
        answer_parts.append(token)
        yield {"type": "assistant", "chunk": token, "task_id": state["task_id"]}
    state["output"] = "".join(answer_parts)
    state["thoughts"] = state.get("thoughts", []) + ["Writer: generated final answer"]

async def handle_edit(state: Dict[str, Any], updated_code: str) -> AsyncGenerator[Dict[str, Any], None]:
    state["code"] = updated_code
    yield {"type": "thought", "content": "Code updated. Re-running...", "agent": "coder", "task_id": state["task_id"]}
    async for ev in terminal_agent(state):
        yield ev
    async for ev in reviewer_agent(state):
        yield ev
    async for ev in writer_agent(state):
        yield ev
