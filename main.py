"""
main.py
-------
Entry point. Starts the application, accepts a user request (and a
role, for permission control), and runs the pure Python agent loop
against Qwen served locally by Ollama.

Prerequisites:
    1. Install Ollama: https://ollama.com/download
    2. Pull the Qwen model:
           ollama pull qwen3:8b
    3. Make sure Ollama is running (`ollama serve`).

Usage:
    # Interactive terminal mode:
    python main.py
    python main.py --role admin

    # One-shot mode:
    python main.py --prompt "Find a laptop in stock"
    python main.py --role admin --prompt "Delete product 1"
"""

import utils.transport
import utils.session
import os
import sys
import argparse
from dotenv import load_dotenv

# Ensure UTF-8 output encoding on Windows terminals to support emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent import build_agent, run_agent

load_dotenv()

DEFAULT_MODEL = os.getenv("MODEL_NAME", "qwen3:8b")
DEFAULT_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_ROLE = os.getenv("DEFAULT_ROLE", "customer")


def main():
    parser = argparse.ArgumentParser(
        description="Simple Safe Shopping Agent (Pure Python + Qwen via Ollama in Terminal)"
    )
    parser.add_argument(
        "--role",
        default=DEFAULT_ROLE,
        choices=["customer", "admin"],
        help=f"Role used for permission control (default: {DEFAULT_ROLE})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model tag to use (default from .env: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Ollama server URL (default from .env: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Optional single prompt to run once and exit instead of interactive mode",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Simple Safe Shopping Agent")
    print(f"Role: {args.role} | Model: {args.model} | URL: {args.base_url}")
    print("=" * 60)

    try:
        agent = build_agent(model_name=args.model, base_url=args.base_url)
    except Exception as e:
        print(f"Error initializing agent or model: {e}", file=sys.stderr)
        sys.exit(1)

    # One-shot mode
    if args.prompt:
        try:
            answer = run_agent(args.prompt, args.role, agent)
            print(f"\n[FINAL ANSWER]\n{answer}\n")
        except Exception as e:
            print(f"Execution error: {e}", file=sys.stderr)
        return

    # Interactive REPL mode
    print("Type your request below. Type 'quit' or 'exit' to end.\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in {"quit", "exit"}:
                print("Goodbye!")
                break
            if not user_input:
                continue

            answer = run_agent(user_input, args.role, agent)
            print(f"\n[FINAL ANSWER]\n{answer}\n")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n", file=sys.stderr)


if __name__ == "__main__":
    main()