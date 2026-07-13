"""
smoke_test.py — verifies the Gemma 4 tool-calling round-trip before any real agent code.

Two paths are tested:
  1. Native function calling via Gemma 4 (gemma4:e2b) — the primary path.
  2. JSON-mode dispatch via Gemma 3 (gemma3:4b) — kept as documented fallback.

Run with: python demo/smoke_test.py
"""

import json
import re

import ollama

MODEL_PRIMARY = "gemma4:e2b"
MODEL_FALLBACK = "gemma3:4b"


def get_weather(city: str) -> dict:
    """Dummy tool. Returns hardcoded data — smoke test only."""
    return {"city": city, "temperature": "28°C", "condition": "sunny"}


# Tool schema in the format Ollama expects
WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "The city name"}
            },
            "required": ["city"],
        },
    },
}

TOOL_REGISTRY = {
    "get_weather": get_weather,
}


# ---------------------------------------------------------------------------
# Path 1: Native function calling (Gemma 4)
# ---------------------------------------------------------------------------

print(f"\n[1/2] Native tool calling — {MODEL_PRIMARY}")

response = ollama.chat(
    model=MODEL_PRIMARY,
    messages=[{"role": "user", "content": "What's the weather like in Nairobi?"}],
    tools=[WEATHER_TOOL],
    options={"num_ctx": 8192},
)

if response.message.tool_calls:
    for call in response.message.tool_calls:
        fn_name = call.function.name
        fn_args = call.function.arguments  # dict, no parsing needed

        print(f"  tool called : {fn_name}")
        print(f"  arguments   : {fn_args}")

        if fn_name in TOOL_REGISTRY:
            result = TOOL_REGISTRY[fn_name](**fn_args)
            print(f"  result      : {result}")

            # Second turn: feed the tool result back so the model can answer
            final = ollama.chat(
                model=MODEL_PRIMARY,
                messages=[
                    {"role": "user", "content": "What's the weather like in Nairobi?"},
                    response.message,
                    {"role": "tool", "content": str(result), "name": fn_name},
                ],
                options={"num_ctx": 8192},
            )
            print(f"\n  final answer: {final.message.content}")
        else:
            print(f"  unknown tool: {fn_name}")
else:
    print("  model did not trigger a tool call — answered directly")
    print(f"  response: {response.message.content}")


# ---------------------------------------------------------------------------
# Path 2: JSON-mode dispatch (Gemma 3 fallback)
# gemma3:4b does not support the native tools parameter; we prompt-engineer
# a strict JSON response and dispatch it ourselves.
# ---------------------------------------------------------------------------

FALLBACK_SYSTEM = """You are a helpful assistant with access to tools.
When you need to call a tool, respond ONLY with valid JSON:
{"tool": "tool_name", "args": {"arg_name": "value"}}

Available tools:
- get_weather(city: str)

No explanation, no markdown — raw JSON only."""

print(f"\n[2/2] JSON-mode fallback — {MODEL_FALLBACK}")

fb_response = ollama.chat(
    model=MODEL_FALLBACK,
    messages=[
        {"role": "system", "content": FALLBACK_SYSTEM},
        {"role": "user", "content": "What's the weather like in Nairobi?"},
    ],
)

raw = fb_response.message.content.strip()
raw = re.sub(r"```(?:json)?\s*", "", raw).strip()  # strip markdown fences if present

try:
    call = json.loads(raw)
    fn_name = call["tool"]
    fn_args = call["args"]

    print(f"  tool called : {fn_name}")
    print(f"  arguments   : {fn_args}")

    if fn_name in TOOL_REGISTRY:
        result = TOOL_REGISTRY[fn_name](**fn_args)
        print(f"  result      : {result}")
    else:
        print(f"  unknown tool: {fn_name}")

except json.JSONDecodeError:
    print(f"  model returned non-JSON — fallback to plain text")
    print(f"  raw output: {raw}")

print("\nSmoke test complete.")
