# Simple Safe Agent (Pure Python + Qwen3:8b)

An autonomous agentic shopping assistant implementing a closed-loop decision cycle (`User Request → Agent / LLM → Tool Call → Application Harness Execution → Observation → Next Action → Final Answer`) with strict application-level safety controls and role-based permissions.

Built using **Pure Python** (no LangGraph, no LangChain) running locally via the official **Ollama** Python SDK (`qwen3:8b`) in the terminal.

---

## 1. Project Overview

The Simple Safe Shopping Agent acts as an intelligent e-commerce catalog assistant. When given a user request, it:
1. Dynamically plans and proposes actions (tool calls).
2. Passes every proposed action through an application-side **safety harness** (`harness.py`).
3. Executes approved tools against the business logic (`tools.py`) and observes the output.
4. Reasons over the tool observation and determines if another action is needed or if it can deliver a final answer to the user.

### Core Principle
> **The model proposes an action. The application decides whether that action is allowed to execute.**

The LLM is never trusted to enforce permissions or safety constraints on its own. All permission rules, schema validations, error captures, and loop limits are enforced strictly in deterministic Python code.

---

## 2. Available Tools

The application provides three registered tools backed by explicit Pydantic schemas:

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `search_products` | `query: str` (non-empty string) | Searches products in the catalog matching keyword(s) (case-insensitive). |
| `check_stock` | `product_id: int` (`> 0`) | Checks the available inventory level and pricing for a specific product ID. |
| `delete_product` | `product_id: int` (`> 0`) | Permanently deletes a product from the catalog (**Admin role required**). |

---

## 3. Agent Loop

The agent loop is implemented as an explicit, pure Python `while` loop:

```
       +--------------------+
       |    User Request    |
       +--------------------+
                 |
                 v
       +--------------------+
+----> |   Ollama Client    | (LLM: qwen3:8b)
|      +--------------------+
|                |
|         Does LLM propose
|           tool calls?
|          /           \
|     [Yes]             [No]
|        |                 \
|        v                  v
|  +------------+     +--------------+
|  | Harness    |     | Final Answer |
|  +------------+     +--------------+
|        |                   |
|  harness.run_tool()        v
|  - Role Permission        END
|  - Schema Validation
|  - Execution / Error Handling
|  - Iteration Limit Guard
|        |
|        v
|  Observation (role: "tool")
+--------+
```

### Flow Walkthrough
1. **Decision**: The LLM receives the message history and decides whether to invoke a tool or formulate a final response.
2. **Interception**: Any tool call is intercepted by the loop and dispatched to `harness.run_tool()`.
3. **Execution**: The harness validates the arguments and role permission. If allowed, it executes the Python function in `tools.py`.
4. **Observation**: The structured result (or controlled error dict) is appended as a `{"role": "tool", "content": ...}` message.
5. **Decide Again**: The `while` loop repeats. The LLM evaluates the observation to decide the next step (e.g., check stock of an item, report an error, or provide the final answer).

---

## 4. Permission Rule

Permissions are enforced in application code inside [`harness.py`](file:///G:/AI-agent/harness.py) using a role-based access control (RBAC) matrix:

Customer can search_product, check_stock
Admin can search_product, check_stock, delete_product


### Enforcement in Code
```python
PERMISSIONS = {
    "customer": {"search_products", "check_stock"},
    "admin": {"search_products", "check_stock", "delete_product"},
}

def check_permission(role: str, tool_name: str) -> None:
    allowed_tools = PERMISSIONS.get(role, set())
    if tool_name not in allowed_tools:
        raise PermissionDenied(
            f"Role '{role}' is not permitted to call tool '{tool_name}'."
        )
```
If an unprivileged role (e.g., `customer`) proposes `delete_product`, the harness blocks execution and returns a structured error:
`{"ok": False, "error": "PERMISSION_DENIED", "message": "Role 'customer' is not permitted to call tool 'delete_product'."}`. The agent observes this and politely explains the restriction to the user.

---

## 5. Safety Controls

### A. Input Validation
Every tool input is validated against Pydantic models defined in [`schemas.py`](file:///G:/AI-agent/schemas.py):
- `product_id` must be a strictly positive integer (`gt=0`).
- `query` strings must not be empty or whitespace-only.
- If validation fails, a structured `INVALID_INPUT` error is returned to the agent without crashing the system.

### B. Controlled Error Handling
Raw Python exceptions are never exposed to the agent or the user:
- Missing products return `{"ok": False, "error": "NOT_FOUND", ...}`.
- Unregistered tools return `{"ok": False, "error": "UNKNOWN_TOOL", ...}`.
- Permission violations return `{"ok": False, "error": "PERMISSION_DENIED", ...}`.
- Schema violations return `{"ok": False, "error": "INVALID_INPUT", ...}`.
- A top-level `try...except` wrapper catches unexpected runtime exceptions and converts them into `{"ok": False, "error": "TOOL_EXECUTION_ERROR", ...}`.

### C. Maximum Iteration / Loop Limit
To prevent runaway loops or infinite tool-calling recursion:
- A hard ceiling `MAX_TOOL_CALLS = 6` is configured (configurable via `.env`).
- Both `harness.py` and the pure Python loop in [`agent.py`](file:///G:/AI-agent/agent.py) check the `call_count`. If exceeded, the loop terminates safely with an iteration limit notice.

---

## 6. Example Runs

### Example 1: Multi-Step Decision & Observation (Search & Stock Check)
**Request**: `"Find available laptops and check stock for product id 1."`  
**Role**: `customer`

```text
============================================================
Simple Safe Shopping Agent (Pure Python + Qwen in Terminal)
Role: customer | Model: qwen3:8b | URL: http://localhost:11434
============================================================

[USER REQUEST] (customer): Find available laptops and check stock for product id 1.
  -> tool_call #1: search_products({'query': 'laptop'})
     result: {'ok': True, 'results': [{'id': 1, 'name': 'Dell XPS 13 Laptop', 'stock': 5, 'price': 999}, {'id': 4, 'name': 'ThinkPad X1 Carbon Laptop', 'stock': 3, 'price': 1299}]}
  -> tool_call #2: check_stock({'product_id': 1})
     result: {'ok': True, 'product_id': 1, 'name': 'Dell XPS 13 Laptop', 'stock': 5}

[FINAL ANSWER]
We have two laptops available: the Dell XPS 13 Laptop (ID 1) with 5 units in stock at $999, and the ThinkPad X1 Carbon Laptop (ID 4) with 3 units in stock at $1,299. Product ID 1 currently has 5 units available.
```

---

### Example 2: Permission Enforcement (Customer attempting Admin action)
**Request**: `"Please delete product id 1 from the store."`  
**Role**: `customer`

```text
============================================================
Simple Safe Shopping Agent (Pure Python + Qwen in Terminal)
Role: customer | Model: qwen3:8b | URL: http://localhost:11434
============================================================

[USER REQUEST] (customer): Please delete product id 1 from the store.
  -> tool_call #1: delete_product({'product_id': 1})
     result: {'ok': False, 'error': 'PERMISSION_DENIED', 'message': "Role 'customer' is not permitted to call tool 'delete_product'."}

[FINAL ANSWER]
I'm sorry, but I can't perform that action. Only admins are allowed to delete products from the store. You may need to contact a store administrator if you need assistance with product management.
```

---

### Example 3: Admin Deletion (Allowed)
**Request**: `"Delete product 3 from the catalog."`  
**Role**: `admin`

```text
============================================================
Simple Safe Shopping Agent (Pure Python + Qwen in Terminal)
Role: admin | Model: qwen3:8b | URL: http://localhost:11434
============================================================

[USER REQUEST] (admin): Delete product 3 from the catalog.
  -> tool_call #1: delete_product({'product_id': 3})
     result: {'ok': True, 'message': "Deleted product 'Logitech Wireless Mouse' (id=3)."}

[FINAL ANSWER]
Product 3 ("Logitech Wireless Mouse") has been successfully deleted from the catalog. Let me know if you need any further assistance!
```

---

## 7. Project Architecture

```
AI-agent/
├── .env                  # Local environment configuration (model, base URL, role)
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore file
├── README.md             # Complete documentation and run instructions
├── requirements.txt      # Project dependencies (ollama, pydantic, python-dotenv)
├── main.py               # Application entrypoint (interactive REPL and CLI runner)
├── agent.py              # Pure Python closed-loop agent and Ollama client integration
├── harness.py            # Safety harness: RBAC permissions, Pydantic validation, loop limit
├── schemas.py            # Pydantic input schemas and tool definitions
├── tools.py              # Business logic implementations (search, stock, delete)
└── test_harness_offline.py # Standalone offline test suite (permission & validation tests)
```

---

## 8. Setup and Run Instructions

### Prerequisites
1. **Python 3.10+** (Python 3.12 recommended).
2. **Ollama**:
   - Download and install Ollama from [ollama.com](https://ollama.com).
   - Pull the required model:
     ```bash
     ollama pull qwen3:8b
     ```
   - Ensure the Ollama service is running (`ollama serve` or running in background).

### Installation
1. Clone the repository and navigate into the project directory:
   ```bash
   git clone <repo-url>
   cd AI-agent
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables (optional, defaults provided):
   ```bash
   cp .env.example .env
   ```

### Running the Application

#### A. Interactive Terminal Mode (Default Customer Role)
```bash
python main.py
```

#### B. Interactive Terminal Mode as Admin
```bash
python main.py --role admin
```

#### C. Single-Command (One-Shot) Mode
```bash
# Customer searching for available laptops:
python main.py --prompt "Find a laptop currently in stock"

# Admin deleting an item:
python main.py --role admin --prompt "Delete product 1"
```

#### D. Running the Offline Safety & Permission Suite
To test permission rules, input validation, and error guards without calling an LLM:
```bash
python test_harness_offline.py
```
