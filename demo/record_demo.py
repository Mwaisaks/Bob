"""
record_demo.py — drives terminal_ui.py through a scripted golden-path
conversation with realistic per-character typing, so the demo recording is
reproducible rather than a one-shot manual take.

Wrap it with asciinema to produce the submission asset:
    asciinema rec -c "python3 demo/record_demo.py" demo/bob_demo.cast

Runs two parts in one continuous recording:
  1. Online — Brian asks two real questions (multi-tool calls, real CPU
     inference, real wait time — no speed-up, no smoke and mirrors).
  2. Offline — HTTPS_PROXY/HTTP_PROXY point at an unroutable address, which
     makes every network call fail fast. The connectivity badge flips to
     "offline" and get_live_rates degrades to cached data instead of
     refusing to answer — the "kill-the-WiFi" moment from Phase 5.

Nothing here is faked: it's the same terminal_ui.py a person would run by
hand, just with typing and waiting done by a script instead of a human.
"""

import os
import subprocess
import sys
import time

import pexpect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT = "You:"
TURN_TIMEOUT = 240  # generous — CPU inference has run up to ~2 minutes in testing


def type_line(child: pexpect.spawn, text: str, delay: float = 0.05):
    """Send text one character at a time, like a person typing."""
    for ch in text:
        child.send(ch)
        time.sleep(delay)
    child.send("\r")


def run_part(cmd: str, questions: list[str], env: dict, label: str):
    print(f"\n\n--- {label} " + "-" * (60 - len(label)) + "\n", flush=True)
    time.sleep(1)

    child = pexpect.spawn(cmd, encoding="utf-8", timeout=TURN_TIMEOUT,
                           cwd=ROOT, env=env, dimensions=(32, 100))
    child.logfile_read = sys.stdout

    child.expect(PROMPT)
    time.sleep(1)

    for q in questions:
        type_line(child, q)
        child.expect(PROMPT, timeout=TURN_TIMEOUT)
        time.sleep(1.5)

    type_line(child, "/quit")
    child.expect(pexpect.EOF)


def main():
    base_env = os.environ.copy()

    run_part(
        "python3 demo/terminal_ui.py --persona brian",
        questions=[
            "why am I always broke by week 3?",
            "what's the current ziidi rate?",
        ],
        env=base_env,
        label="ONLINE",
    )

    offline_env = base_env.copy()
    offline_env["HTTPS_PROXY"] = "http://127.0.0.1:1"
    offline_env["HTTP_PROXY"] = "http://127.0.0.1:1"
    # Ollama itself is an HTTP call to localhost — without this exception the
    # proxy trick would take Bob's own brain offline too, not just the internet.
    offline_env["NO_PROXY"] = "localhost,127.0.0.1,::1"
    offline_env["no_proxy"] = "localhost,127.0.0.1,::1"

    run_part(
        "python3 demo/terminal_ui.py --persona brian",
        questions=["what's the current ziidi rate?"],
        env=offline_env,
        label="AIRPLANE MODE (network blocked)",
    )


if __name__ == "__main__":
    main()
