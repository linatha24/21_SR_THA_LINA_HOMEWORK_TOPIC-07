"""
harness.py
----------
The application-side control layer. This is what makes the agent SAFE:
the model can *propose* any tool call it wants, but this file is the
gatekeeper that actually decides whether that call is allowed to run.

Responsibilities:
  1. Permission control  -> is this role allowed to call this tool?
  2. Input validation     -> do the arguments satisfy the schema?
  3. Execution            -> call the real tool implementation.
  4. Error handling       -> never let a raw exception escape.
  5. Iteration limit      -> stop the agent loop after N tool calls.

Nothing here is enforced by prompting the model to "be careful" -
every check below runs in plain Python, regardless of what the model
says or does.
"""

import os
from typing import Any, Dict
from dotenv import load_dotenv
from pydantic import ValidationError

from schemas import TOOL_INPUT_MODELS
from tools import TOOL_IMPLEMENTATIONS

load_dotenv()
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", "6"))  # hard ceiling on tool calls per request

# ---------------------------------------------------------------------------
# C. Basic permission control (application code, not just prompt text)
# ---------------------------------------------------------------------------
PERMISSIONS = {
    "customer": {"search_products", "check_stock"},
    "admin": {"search_products", "check_stock", "delete_product"},
}


class PermissionDenied(Exception):
    pass


class IterationLimitExceeded(Exception):
    pass


def check_permission(role: str, tool_name: str) -> None:
    allowed_tools = PERMISSIONS.get(role, set())
    if tool_name not in allowed_tools:
        raise PermissionDenied(
            f"Role '{role}' is not permitted to call tool '{tool_name}'."
        )


def run_tool(tool_name: str, arguments: Dict[str, Any], role: str, call_count: int) -> Dict[str, Any]:
    """
    Central choke point every tool call must pass through.
    Returns a structured dict result (never raises) so the agent
    loop can feed it straight back to the model as an observation.
    """
    # --- D. Iteration / tool-call limit -----------------------------------
    if call_count > MAX_TOOL_CALLS:
        return {
            "ok": False,
            "error": "ITERATION_LIMIT",
            "message": f"Maximum of {MAX_TOOL_CALLS} tool calls per request exceeded.",
        }

    # --- Unknown tool guard --------------------------------------------
    if tool_name not in TOOL_IMPLEMENTATIONS:
        return {"ok": False, "error": "UNKNOWN_TOOL", "message": f"No such tool: {tool_name}"}

    # --- C. Permission control ------------------------------------------
    try:
        check_permission(role, tool_name)
    except PermissionDenied as e:
        return {"ok": False, "error": "PERMISSION_DENIED", "message": str(e)}

    # --- D. Input validation (Pydantic schema) ---------------------------
    model_cls = TOOL_INPUT_MODELS.get(tool_name)
    if not model_cls:
        return {"ok": False, "error": "NO_SCHEMA", "message": f"No schema registered for {tool_name}"}
    try:
        validated = model_cls(**arguments)
    except ValidationError as e:
        return {"ok": False, "error": "INVALID_INPUT", "message": str(e)}

    # --- D. Error handling: never let raw exceptions escape ---------------
    try:
        fn = TOOL_IMPLEMENTATIONS[tool_name]
        result = fn(**validated.model_dump())
        return result
    except Exception as e:  # last-resort safety net around business logic
        return {"ok": False, "error": "TOOL_EXECUTION_ERROR", "message": str(e)}