import ollama
import json
import re

# Step 1: The actual Python function Bob will call
def get_weather(city: str) -> dict:
    # Fake data for now — this is just a smoke test
    return {"city": city, "temperature": "28°C", "condition": "sunny"}

# Step 2: The schema — describes the tool to Gemma
weather_tool = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "The city name"}
            },
            "required": ["city"]
        }
    }
}

# Step 3: System prompt that enforces JSON tool calls
SYSTEM_PROMPT = """You are a helpful assistant with access to tools.
When you need to use a tool, respond ONLY with valid JSON in this exact format:
{"tool": "tool_name", "args": {"arg1": "value1"}}

Available tools:
- get_weather(city: str) -> returns weather for a city

Do not add any text before or after the JSON when calling a tool."""

# Step 4: Send the message
print("Sending message to Gemma (JSON-mode tool calling)...")

response = ollama.chat(
    model="gemma3:4b",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "What's the weather like in Nairobi?"}
    ]
)

raw = response.message.content.strip()
raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
print(f"Gemma raw response: {raw}")

# Step 5: Parse and dispatch
try:
    call = json.loads(raw)
    tool_name = call["tool"]
    args = call["args"]
    print(f"\n✅ Tool call detected: {tool_name}({args})")

    # Dispatch
    if tool_name == "get_weather":
        result = get_weather(**args)
        print(f"Tool result: {result}")
    else:
        print(f"Unknown tool: {tool_name}")

except json.JSONDecodeError:
    print(f"\n⚠️  Model did not return JSON. Raw output was:\n{raw}")
    print("Fallback: treating as plain text answer.")


print("Gemma's response:")
print(f"  tool_calls: {response.message.tool_calls}")
