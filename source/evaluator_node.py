from langchain_core.messages import (HumanMessage, SystemMessage, AIMessage)
from langsmith import traceable
from source.utils import dump_context
import json
from langchain_openai import ChatOpenAI
from source.tracker import CostTracker

@traceable(name="evaluator_node")
def evaluate(messages: list, proposed_tool_call: dict) -> str:
    """
    Evaluates a single proposed tool call in the context of the solver's messages.
    Returns a JSON string with:
      - Command
      - CorrectDirection: "yes" or "no"
      - Explanation
    """

    # Prepare the context for the LLM
    context_str = dump_context(messages)
    model="gpt-4o-mini"
    llm_kwargs = {"model": model, "temperature": 0, "stream_usage": True}
    llm = ChatOpenAI(**llm_kwargs)

    system_prompt = SystemMessage(content="""
        You are a strict Capture The Flag (CTF) evaluator.

        You are given:
        - The solver’s prior context
        - One proposed tool call to execute next

        Decide whether this tool call is moving the solver toward solving the challenge.

        Rules:
        - If a vulnerability or promising attack surface has already been identified,
          the command must exploit it or meaningfully extend it.
        - Random endpoint guessing is always "no".
        - Random guessing credentials is always "no"

        Output ONLY valid JSON with exactly these fields:
        - Action: run_command or run_python
        - Command: the command or code being executed
        - CorrectDirection: "yes" or "no"
        - Explanation: (≤25 words)

    """)

    human_prompt = HumanMessage(content=f"""
    Context (previous messages):

    {context_str}

    Proposed tool call:

    {json.dumps(proposed_tool_call, indent=2)}

    Return a structured JSON evaluation for this single tool call only.
    """)

    out = llm.invoke([system_prompt, human_prompt], config={ "callbacks": [CostTracker(model)],})

    if isinstance(out.content, list):
        for block in out.content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
        return ""  # fallback
    else:
        return out.content