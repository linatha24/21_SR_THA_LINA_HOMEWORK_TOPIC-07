"""
agent.py
--------
Pure Python agent loop running locally against Qwen via the official Ollama client:

    User Request -> [LLM: Qwen3:8b] -> tool_calls? -> [Safety Harness: harness.run_tool]
                         ^                                        |
                         |________________________________________|
                                     (loop until no more tool calls)
                                             -> Final answer

Key design point: The agent loop NEVER executes tool functions directly.
Every proposed tool call is intercepted and routed through harness.run_tool(),
which enforces application-level permission checks, Pydantic schema validation,
error handling, and loop iteration limits.
"""

import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
import ollama

from schemas import TOOL_INPUT_MODELS
from harness import run_tool, MAX_TOOL_CALLS

load_dotenv()

SYSTEM_PROMPT = (
    "You are a helpful shopping assistant agent. You can call tools to search products, "
    "check stock, and (admins only) delete products. "
    "If a tool returns an error, explain it clearly to the user instead of retrying blindly. "
    "When you have enough information, give a clear, natural-language final answer without "
    "calling any more tools."
)


def build_tool_definitions() -> List[dict]:
    """
    Turns our Pydantic input models (schemas.py) into function/tool definitions
    compatible with the Ollama tool calling format.
    """
    tools = []
    for name, model_cls in TOOL_INPUT_MODELS.items():
        doc = (model_cls.__doc__ or f"Tool: {name}").strip()
        doc = " ".join(doc.split())
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": doc,
                    "parameters": model_cls.model_json_schema(),
                },
            }
        )
    return tools


class Agent:
    """Pure Python Safe Agent loop talking directly to Ollama."""

    def __init__(self, model_name: str = None, base_url: str = None):
        self.model_name = model_name or os.getenv("MODEL_NAME", "qwen3:8b")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.client = ollama.Client(host=self.base_url)
        self.tools = build_tool_definitions()

    def run(self, user_request: str, role: str) -> str:
        """
        Runs one user request through the pure Python agent loop and returns the final answer.
        """
        print(f"\n[USER REQUEST] ({role}): {user_request}", flush=True)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ]
        call_count = 0

        while call_count < MAX_TOOL_CALLS:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
            )
            msg = response.message
            messages.append(msg)

            # If the model produced a final answer without requesting tool calls
            if not msg.tool_calls:
                return msg.content or ""

            # The model proposed one or more tool calls: validate and execute via harness
            for call in msg.tool_calls:
                call_count += 1
                name = call.function.name
                args = call.function.arguments or {}
                print(f"  -> tool_call #{call_count}: {name}({args})", flush=True)

                result = run_tool(name, args, role, call_count)
                print(f"     result: {result}", flush=True)

                messages.append(
                    {
                        "role": "tool",
                        "content": json.dumps(result),
                    }
                )

                if call_count >= MAX_TOOL_CALLS:
                    return f"Stopping: reached maximum tool calls ({MAX_TOOL_CALLS}) for this request."

        return f"Stopping: reached maximum tool calls ({MAX_TOOL_CALLS}) for this request."


def build_agent(model_name: str = None, base_url: str = None) -> Agent:
    """Factory function to build a Pure Python Safe Agent instance."""
    return Agent(model_name=model_name, base_url=base_url)


def run_agent(user_request: str, role: str, agent: Agent) -> str:
    """Runs one user request through the agent and returns the final answer."""
    return agent.run(user_request, role)