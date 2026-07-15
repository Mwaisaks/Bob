"""
terminal_ui.py — Rich terminal demo interface for Bob.

Wraps the BobAgent with a polished terminal experience:
  - Startup banner with model, quantization, and privacy statement
  - Connectivity indicator (live check on each question)
  - Inline tool-call traces so judges can see native function calling in action
  - Persona switcher via --persona flag
  - /reset, /persona, /quit slash commands

Run:
    python demo/terminal_ui.py --persona brian
    python demo/terminal_ui.py --persona wanjiku
    python demo/terminal_ui.py --persona athman

Or load your own real M-Pesa statement (dial *334# on Safaricom to request
one — see README "Using Your Own M-Pesa Data"):
    python demo/terminal_ui.py --statement path/to/statement.pdf

Or load your own SMS, pasted as text or exported via Termux:API:
    python demo/terminal_ui.py --sms-file path/to/messages.txt
"""

import argparse
import getpass
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from agent.bob import BobAgent, PERSONAS
from agent.ledger import Ledger
from tools.ingest import ingest_statement, ingest_sms_text

console = Console()

PERSONA_LABELS = {
    "brian":   ("Brian Otieno",   "KU · Year 2 · HELB student"),
    "wanjiku": ("Wanjiku Kamau",  "USIU · Year 3 · Mitumba hustler"),
    "athman":  ("Athman Hassan",  "Strathmore · Year 4 · Part-time dev"),
}

MODEL_TAG = "gemma4:e2b (local, CPU, no data leaves this machine)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_online() -> bool:
    try:
        urllib.request.urlopen("https://www.google.com", timeout=2)
        return True
    except Exception:
        return False


def _connectivity_badge(online: bool) -> Text:
    if online:
        return Text("● online", style="bold green")
    return Text("● offline", style="bold red")


def _print_banner(persona: str, online: bool):
    name, label = PERSONA_LABELS.get(persona, (persona.title(), "Your real M-Pesa statement"))
    badge = _connectivity_badge(online)

    title_text = Text()
    title_text.append("BOB", style="bold cyan")
    title_text.append("  M-Pesa Finance Assistant", style="dim white")

    console.print()
    console.print(Panel(
        title_text,
        subtitle=Text.assemble(
            Text(f"  {name}  ·  {label}  ", style="white"),
            badge,
            Text(f"  ·  {MODEL_TAG}", style="dim"),
        ),
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print(Text(
        "  Type a question. Commands: /reset  /quit\n",
        style="dim",
    ))


def _print_trace(trace: list[dict]):
    if not trace:
        return

    for entry in trace:
        tool_name = entry["tool"]
        args = {k: v for k, v in entry["args"].items() if k != "persona"}
        result = entry["result"]

        # Tool call line
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        console.print(
            Text.assemble(
                Text("  ⚙  ", style="dim yellow"),
                Text(tool_name, style="yellow"),
                Text(f"({args_str})", style="dim yellow"),
            )
        )

        # Key result summary (not the full JSON dump — too noisy)
        _print_result_summary(tool_name, result)

    console.print()


def _print_result_summary(tool_name: str, result: dict):
    """Print a one-line summary of the tool result."""
    try:
        if tool_name == "get_spending_summary":
            total = result.get("grand_total_out", 0)
            breakdown = result.get("breakdown", [])
            top = breakdown[0]["type"] if breakdown else "?"
            console.print(Text(
                f"  ✓  KES {total:,.0f} total out · top category: {top}",
                style="dim green",
            ))

        elif tool_name == "get_balance_trend":
            low = result.get("lowest_balance", 0)
            high = result.get("highest_balance", 0)
            console.print(Text(
                f"  ✓  Balance range: KES {low:,.0f} – KES {high:,.0f}",
                style="dim green",
            ))

        elif tool_name == "get_top_counterparties":
            top = result.get("top", [])
            if top:
                name = top[0].get("counterparty", "?")
                amt = top[0].get("total_amount", 0)
                console.print(Text(
                    f"  ✓  Top: {name}  (KES {amt:,.0f})",
                    style="dim green",
                ))

        elif tool_name == "get_fee_analysis":
            total = result.get("total_fees_paid", 0)
            console.print(Text(
                f"  ✓  Total fees: KES {total:,.0f}",
                style="dim green",
            ))

        elif tool_name == "get_fuliza_summary":
            count = result.get("borrow_count", 0)
            total = result.get("total_borrowed", 0)
            charges = result.get("total_daily_charges", 0)
            console.print(Text(
                f"  ✓  {count} borrows · KES {total:,.0f} total · KES {charges:,.0f} in charges",
                style="dim green",
            ))

        elif tool_name == "get_income_vs_spending":
            inc = result.get("total_income", 0)
            spent = result.get("total_spending", 0)
            verdict = result.get("verdict", "")
            style = "dim green" if verdict == "net positive" else "dim red"
            console.print(Text(
                f"  ✓  Income KES {inc:,.0f}  ·  Spend KES {spent:,.0f}  ·  {verdict}",
                style=style,
            ))

        elif tool_name == "search_knowledge":
            results = result.get("results", [])
            if results:
                src = results[0].get("source", "?")
                score = results[0].get("score", 0)
                console.print(Text(
                    f"  ✓  Best match: {src}  (score {score:.2f})",
                    style="dim green",
                ))

        elif tool_name == "get_live_rates":
            source = result.get("source", "?")
            as_of = result.get("data_as_of", "?")
            style = "dim green" if source == "online_verified" else "dim yellow"
            console.print(Text(
                f"  ✓  Rates from: {source}  (as of {as_of})",
                style=style,
            ))

        else:
            # Generic fallback
            preview = str(result)[:60]
            console.print(Text(f"  ✓  {preview}", style="dim green"))

    except Exception:
        pass   # trace summary is cosmetic — never crash the demo over it


def _print_answer(answer: str):
    console.print(Panel(
        Text(answer, style="white"),
        title=Text("Bob", style="bold cyan"),
        title_align="left",
        border_style="dim cyan",
        padding=(0, 2),
    ))
    console.print()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(persona: str):
    online = _check_online()
    _print_banner(persona, online)

    agent = BobAgent(persona)

    while True:
        try:
            user_input = console.input("[bold]You:[/bold] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            console.print("[dim]Bob:[/dim] See you. Watch those fees.")
            break

        if user_input.lower() == "/reset":
            agent.reset()
            console.print("[dim]History cleared.[/dim]\n")
            continue

        # Thinking indicator
        console.print(Text("  Bob is thinking...", style="dim"), end="\r")

        try:
            answer = agent.chat(user_input)
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {escape(str(e))}\n")
            continue

        # Clear the "thinking" line
        console.print(" " * 30, end="\r")

        # Print tool traces, then the answer
        _print_trace(agent.last_trace)
        _print_answer(answer)

        # Refresh connectivity badge on each turn
        online = _check_online()


def main():
    parser = argparse.ArgumentParser(description="Bob — M-Pesa Finance Assistant")
    parser.add_argument(
        "--persona", choices=PERSONAS, default=None,
        help="Student persona to load (default: brian, unless --statement is given)"
    )
    parser.add_argument(
        "--statement", type=Path,
        help="Path to a real M-Pesa statement PDF (from *334# — see README)"
    )
    parser.add_argument(
        "--password",
        help="Statement PDF password (prompted securely if omitted)"
    )
    parser.add_argument(
        "--sms-file", type=Path,
        help="Path to pasted SMS text or termux-sms-list JSON export"
    )
    args = parser.parse_args()

    modes_given = sum(bool(x) for x in (args.persona, args.statement, args.sms_file))
    if modes_given > 1:
        parser.error("--persona, --statement, and --sms-file are mutually exclusive")

    if args.statement:
        password = args.password or getpass.getpass("Statement PDF password: ")
        console.print("[dim]Parsing statement...[/dim]")
        ledger = Ledger()
        ledger.clear(persona="me")
        count, stats = ingest_statement(args.statement, password, "me", ledger)
        console.print(
            f"[dim]Loaded {count} transactions "
            f"({stats['via_regex']} via regex, {stats['via_gemma']} via Gemma).[/dim]\n"
        )
        run("me")
    elif args.sms_file:
        console.print("[dim]Parsing SMS...[/dim]")
        ledger = Ledger()
        ledger.clear(persona="me")
        ingested, failed = ingest_sms_text(args.sms_file, "me", ledger)
        console.print(f"[dim]Loaded {ingested} transactions ({failed} failed to parse).[/dim]\n")
        run("me")
    else:
        run(args.persona or "brian")


if __name__ == "__main__":
    main()
