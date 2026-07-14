"""
bob.py — the Bob agent loop.

Bob receives a user's financial question, asks Gemma 4 which query tool
to call, executes that tool against the SQLite ledger, and returns a
grounded natural-language answer backed by real transaction data.

Usage:
    python agent/bob.py --persona brian
    python agent/bob.py --persona wanjiku
    python agent/bob.py --persona athman
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ollama
from tools.query_tools import QUERY_TOOLS, TOOL_REGISTRY
from tools.knowledge_lookup import KNOWLEDGE_TOOL, search_knowledge
from tools.live_rates import LIVE_RATES_TOOL, get_live_rates as _get_live_rates

ALL_TOOLS = QUERY_TOOLS + [KNOWLEDGE_TOOL, LIVE_RATES_TOOL]

# Tools that don't need the persona parameter injected
_NO_PERSONA_TOOLS = {"search_knowledge", "get_live_rates"}

ALL_TOOL_REGISTRY = {
    **TOOL_REGISTRY,
    "search_knowledge": search_knowledge,
    "get_live_rates": _get_live_rates,
}

MODEL = "gemma4:e2b"
NUM_CTX = 8192
PERSONAS = ["brian", "wanjiku", "athman"]

SYSTEM_PROMPT = """\
You are Bob, a personal M-Pesa finance assistant for Kenyan university students.
You have access to the user's transaction history through a set of tools.

Rules:
- Always use a tool to look up data before making any financial claim.
- Ground every number in what the tool returns — never guess or estimate.
- Be direct and practical. The students you help have real money pressures.
- When you spot a problem (Fuliza dependency, fee bleed, spending > income), name it clearly.
- Keep responses concise — two or three sentences is usually enough.

The persona (which student's data to query) is set automatically — do not ask the user for it.\
"""


class BobAgent:
    def __init__(self, persona: str):
        if persona not in PERSONAS:
            raise ValueError(f"Unknown persona '{persona}'. Choose from: {PERSONAS}")
        self.persona = persona
        self.history: list[dict] = []

    def _execute_tool(self, name: str, args: dict) -> str:
        """Run one tool call, injecting persona for ledger tools, and return JSON result."""
        if name not in ALL_TOOL_REGISTRY:
            return json.dumps({"error": f"unknown tool: {name}"})
        if name not in _NO_PERSONA_TOOLS:
            args["persona"] = self.persona
        result = ALL_TOOL_REGISTRY[name](**args)
        return json.dumps(result, ensure_ascii=False)

    def chat(self, user_message: str) -> str:
        """
        One conversational turn.
        Returns Bob's final answer as a plain string.
        """
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + self.history
            + [{"role": "user", "content": user_message}]
        )

        response = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=ALL_TOOLS,
            options={"num_ctx": NUM_CTX},
        )

        if response.message.tool_calls:
            self.history.append({"role": "user", "content": user_message})
            self.history.append(response.message)

            for call in response.message.tool_calls:
                name = call.function.name
                args = dict(call.function.arguments)
                result_json = self._execute_tool(name, args)
                self.history.append({
                    "role": "tool",
                    "content": result_json,
                    "name": name,
                })

            # Second call: Gemma reads the tool results and answers the user
            final = ollama.chat(
                model=MODEL,
                messages=(
                    [{"role": "system", "content": SYSTEM_PROMPT}]
                    + self.history
                ),
                options={"num_ctx": NUM_CTX},
            )
            answer = final.message.content

        else:
            # Gemma answered directly without needing a tool
            answer = response.message.content
            self.history.append({"role": "user", "content": user_message})

        self.history.append({"role": "assistant", "content": answer})
        return answer

    def reset(self):
        """Clear conversation history (keep persona)."""
        self.history = []


# ---------------------------------------------------------------------------
# CLI / REPL
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chat with Bob")
    parser.add_argument(
        "--persona", choices=PERSONAS, default="brian",
        help="Which student's data to load (default: brian)"
    )
    args = parser.parse_args()

    agent = BobAgent(args.persona)

    persona_labels = {
        "brian":   "Brian Otieno — KU Year 2, HELB student",
        "wanjiku": "Wanjiku Kamau — USIU Year 3, mitumba hustler",
        "athman":  "Athman Hassan — Strathmore Year 4, part-time dev",
    }

    print(f"\n╔══════════════════════════════════════╗")
    print(f"║  Bob — M-Pesa Finance Assistant      ║")
    print(f"║  {persona_labels[args.persona]:<36}║")
    print(f"╚══════════════════════════════════════╝")
    print(f"\nType your question. 'reset' clears history. 'quit' exits.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print("Bob: See you. Stay on top of those transactions.")
            break
        if user_input.lower() == "reset":
            agent.reset()
            print("Bob: History cleared. Fresh start.\n")
            continue

        print("Bob: ", end="", flush=True)
        answer = agent.chat(user_input)
        print(answer)
        print()


if __name__ == "__main__":
    main()
