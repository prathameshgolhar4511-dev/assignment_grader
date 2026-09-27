"""
utils.py
Shared helpers used across all agents:
  - LLM call wrapper. Supports two modes, auto-selected by which
    environment variable is set:
      1. GROQ_API_KEY set  -> Groq's free API tier (no credit card
                               needed). Recommended for real LLM responses.
      2. neither set       -> deterministic offline "mock" mode, so
                               the whole pipeline is demoable without
                               any network access / API key at all.
  - Small text helpers.
"""

import os
import json
import textwrap

# Load .env from the project root automatically
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed; rely on env vars being set manually

GROQ_MODEL = "openai/gpt-oss-120b"   # supports tool calling, free tier (developer plan)

if os.environ.get("GROQ_API_KEY"):
    PROVIDER = "groq"
    from groq import Groq
    _client = Groq(api_key=os.environ["GROQ_API_KEY"])
else:
    PROVIDER = "mock"
    _client = None

USE_LIVE_LLM = PROVIDER != "mock"


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 600) -> str:
    """Single entry point every agent uses for a plain (no-tools) LLM call."""
    if PROVIDER == "groq":
        resp = _client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content or ""

    # ---- Offline mock mode ----
    return _mock_llm_response(system_prompt, user_prompt)


def _mock_llm_response(system_prompt: str, user_prompt: str) -> str:
    header = "[MOCK LLM RESPONSE - set GROQ_API_KEY (free) for real generation]\n"
    if "feedback" in system_prompt.lower():
        return header + textwrap.dedent("""
            Overall: The submission demonstrates a reasonable attempt at the problem.
            Strengths: Logical structure is present and core requirements are partially met.
            Weaknesses: Some edge cases / test cases were not handled correctly.
            Suggestion: Review the failing cases listed above and re-trace your logic
            for those specific inputs before resubmitting.
        """).strip()
    if "improvement" in system_prompt.lower():
        return header + textwrap.dedent("""
            Recommended focus areas:
            - Revisit the core concept tested by the failing cases.
            - Practice 2-3 similar problems from the same topic.
            - Add basic input validation / edge-case handling to your code.
        """).strip()
    return header + "No specific guidance generated (mock mode)."


def pretty(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def _anthropic_tools(tools: list) -> list:
    """Strip our internal '_mock_args' hint key."""
    return [{k: v for k, v in t.items() if k != "_mock_args"} for t in tools]


def _openai_style_tools(tools: list) -> list:
    """Convert our Anthropic-shaped tool schemas into OpenAI/Groq's
    {"type": "function", "function": {...}} shape."""
    converted = []
    for t in tools:
        converted.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        })
    return converted


def run_tool_agent(system_prompt: str, user_prompt: str, tools: list, tool_impl: dict,
                    max_iterations: int = 8):
    """
    Generic agentic tool-use loop shared by every agent in this project.

    tools:      list of tool-schema dicts in our internal (Anthropic-shaped)
                format: {"name": ..., "description": ..., "input_schema": {...}}
    tool_impl:  {"tool_name": python_callable(**kwargs) -> JSON-serializable result}

    Live mode (GROQ_API_KEY set): calls the real LLM
    with tool/function-calling enabled. The model autonomously decides
    which tool(s) to call, in what order, and how many times. Each tool
    call is executed locally via tool_impl and the result is fed back to
    the model; the loop continues until the model stops requesting tools
    and returns final text.

    Offline mock mode (no key set): there is no real model making
    decisions, so we cannot claim genuine autonomous tool selection.
    Instead we run a clearly-labeled deterministic simulation that calls
    every tool in `tools` once, in the order given, so the *shape* of the
    agent loop is still fully exercised and demoable without credentials.
    Every trace entry is tagged with "mode" so it's obvious which happened.

    Returns: (final_text: str, trace: list[dict])
    """
    trace = []

    if PROVIDER == "groq":
        openai_tools = _openai_style_tools(tools)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        for _ in range(max_iterations):
            resp = _client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=1000,
                messages=messages,
                tools=openai_tools,
            )
            msg = resp.choices[0].message

            if not msg.tool_calls:
                return msg.content or "", trace

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                kwargs = {}
                try:
                    kwargs = json.loads(tc.function.arguments or "{}")
                    result = tool_impl[tc.function.name](**kwargs)
                except Exception as e:
                    result = {"error": str(e)}
                trace.append({"mode": "live", "tool": tc.function.name, "input": kwargs, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })

        return "[max tool-call iterations reached without a final answer]", trace

    # ---- Offline mock mode: deterministic simulated tool-call trace ----
    for tool in tools:
        name = tool["name"]
        try:
            result = tool_impl[name](**tool.get("_mock_args", {}))
        except Exception as e:
            result = {"error": str(e)}
        trace.append({"mode": "mock", "tool": name, "input": tool.get("_mock_args", {}), "result": result})

    final_text = _mock_llm_response(system_prompt, user_prompt)
    return final_text, trace
