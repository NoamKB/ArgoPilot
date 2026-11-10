"""Minimal terminal chat agent: qwen3:1.7b via Ollama, with one tool."""

from datetime import date

import ollama

MODEL = "qwen3:1.7b"

def current_date() -> str:
    """Get today's date and weekday.
    Get today's date and day of the week. Call this whenever the user asks what day, date, or weekday it is.

    Returns:
        Today's date as YYYY-MM-DD followed by the weekday name.
    """
    today = date.today()
    return f"{today.isoformat()} ({today.strftime('%A')})"


TOOLS = {"current_date": current_date}

messages = [{"role": "system", "content": "You don't know today's date. Always use the tool, never guess."}]

while True:
    user_line = input("you> ").strip()
    if user_line == "exit":
        break
    messages.append({"role": "user", "content": user_line})

    # Keep calling the model until it answers with text instead of tool calls.
    while True:
        response = ollama.chat(
            model=MODEL, 
            messages=messages, 
            tools=list(TOOLS.values()), 
            think=False
        )
        
        messages.append(response.message)
        if not response.message.tool_calls:
            break
        for call in response.message.tool_calls:
            tool = TOOLS.get(call.function.name)
            result = tool(**call.function.arguments) if tool else f"Unknown tool: {call.function.name}"
            messages.append({"role": "tool", "tool_name": call.function.name, "content": str(result)})

    print(f"agent> {response.message.content}")

