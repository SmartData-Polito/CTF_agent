
from langchain_core.messages import BaseMessage
from langchain_core.messages import AIMessage, SystemMessage

def dump_context(messages):
    """
    Convert LangChain/LangGraph messages into a readable, compact history.
    Safe for GPT-5 reasoning outputs and tool calls.
    """
    readable = []
    step = 0

    for msg in messages:
        entry = {}

        # ------------------------
        # Human message
        # ------------------------
        if msg.__class__.__name__ == "HumanMessage":
            step += 1
            entry = {
                "step": step,
                "role": "human",
                "content": msg.content.strip()
            }

        # ------------------------
        # System message 
        # ------------------------
        elif msg.__class__.__name__ == "SystemMessage":
            entry = {
                "role": "system",
                "content": msg.content.strip()
            }

        # ------------------------
        # AI message
        # ------------------------
        elif msg.__class__.__name__ == "AIMessage":
            step += 1
            entry = {
                "step": step,
                "role": "agent",
            }

            # Tool call
            if getattr(msg, "tool_calls", None):
                call = msg.tool_calls[0]
                entry["action"] = call["name"]
                entry["args"] = call["args"]

            # Final answer (no tool)
            else:
                content = msg.content
                if isinstance(content, list):
                    parts = []
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            parts.append(str(c.get("text", "")))
                    content = " ".join(parts)

                entry["final_output"] = content.strip()
        # ------------------------
        # Tool output
        # ------------------------
        elif msg.__class__.__name__ == "ToolMessage":
            output = msg.content
            if isinstance(output, str):
                output = output.strip()
                # Truncate very long tool output
                if len(output) > 800:
                    output = output[:800] + "\n... (truncated)"
            entry = {
                "role": "tool",
                "output": output
            }

        if entry:
            readable.append(entry)

    return readable


def get_text_content(msg) -> str:
    if msg is None:
        return ""

    content = msg.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
        )

    return str(content)