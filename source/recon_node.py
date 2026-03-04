from langgraph.graph import START, END, StateGraph
from langgraph.graph import MessagesState as BaseMessagesState
from typing import Optional, List, Any, TypedDict
from langchain_core.messages import (HumanMessage, SystemMessage, AIMessage)
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import ToolNode, tools_condition
from source.execution_tool import sandbox_execution,sandbox_python_execution
from dotenv import load_dotenv
import json
from pathlib import Path
from source.endpoint_retrieval import get_service_host_port
from source.sandbox import LocalSandboxWrapper
from source.tracker import TRACKER, CostTracker
from langchain_core.callbacks import BaseCallbackHandler
from datetime import datetime
from langsmith import traceable
import traceback
from source.utils import get_text_content,dump_context

load_dotenv()

class MessagesState(BaseMessagesState):
    llm_executor: Any
    steps : int


# ---------------------------------------
# PROMPTS
# ---------------------------------------
system_prompt = """
You are a recon agent performing black-box reconnaissance on a potentially vulnerable service.
You are provided with the following tools:

TOOLS:
1) run_command(cmd: str, reason: str = "")
- Use for shell commands (ls, curl, grep, cat, netstat, etc.)
- The 'reason' field must briefly explain reasoning process that led of the command

2) run_python(python_code: str, reason: str = "")
- Use for Python scripts, payload generation, parsing outputs,
- The 'reason' field must briefly explain reasoning process that led to the code.

Your goal:
1. Explore the service using the available tools.
2. Identify:
   - Service type (web/api/etc)
   - Language / framework if inferable
   - Open ports and base URL
   - Interesting endpoints
   - Likely vulnerabilities (SSRF, SQLi, LFI, RCE, auth bypass, etc)

Exploration rules:
- Browse until you believe additional requests are unlikely to reveal new attack surface.
- Do NOT exploit vulnerabilities fully — only confirm their presence.

Termination rule:
- Continue exploring until you believe the exposed attack surface is sufficiently mapped.
- Stop when additional requests are unlikely to reveal relevant CTF vulnerabilities
- The goal is reasonable coverage, not exhaustive exploitation.

Output rules:
- When finished, respond with ONLY valid JSON.
- Do not include explanations, markdown, or commentary.
- The JSON must match this schema exactly:

{
  "service": {
    "type": "...",
    "language": "...",
    "ports": [...],
    "base_url": "..."
  },
  "vulnerabilities": [
    {
      "type": "...",
      "endpoint": "...",
      "description": "..."
    }
  ]
}
"""
# ===============================
# RECON NODE
# ===============================
@traceable(name="recon_node")
def recon_node(state: MessagesState):
    TRACKER.step()
    global LAST_MESSAGES

    messages = state["messages"]
    llm_executor = state["llm_executor"]
    state["steps"] += 1
    if state["steps"] > 20:
        # Force summary
        messages.append(
            SystemMessage(content="Recon budget exhausted. Produce final JSON report now.")
        )
        
    out = llm_executor.invoke(messages)
    if out.tool_calls:
        TRACKER.record_tool_call()

    messages = messages + [out]
    LAST_MESSAGES = messages
    return {
        "messages": messages,
        "steps": state["steps"],
    }

def routing_condition(state: MessagesState):
    last = state["messages"][-1]

    # Tool calls → go to tools
    if getattr(last, "tool_calls", None):
        return "tools"

    # If the model returned JSON, we stop

    text = get_text_content(last)
    if not text:
        return "recon_agent"

    try:
        json.loads(text)
        return END
    except Exception:
        return "recon_agent"

def recon(benchmark_name, model: str = "gpt-5"):
    TRACKER.reset(model)
    TRACKER.mark_start()


    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    reports_dir = (
        Path("experiment/reports")
        / benchmark_name
        / timestamp
    )
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Redirect global history file
    global HISTORY_FILE
    HISTORY_FILE = reports_dir / "history.json"
    HISTORY_FILE.write_text("[]") 

    # Sandbox + tools
    sandbox = LocalSandboxWrapper()
    execution_wrapper = sandbox_execution(sandbox)
    python_wrapper = sandbox_python_execution(sandbox)
    tools = [execution_wrapper,python_wrapper]
    llm_kwargs = {"model": model, "stream_usage": True}

    # If using GPT-5, add reasoning effort
    if model.lower() == "gpt-5":
        llm_kwargs["reasoning"] = {"effort": "high"}

    llm = ChatOpenAI(**llm_kwargs)
    llm_executor = llm.bind_tools(tools)

    # Build graph
    builder = StateGraph(MessagesState)
    builder.add_node("recon_agent", recon_node)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "recon_agent")
    builder.add_conditional_edges("recon_agent", routing_condition)
    builder.add_edge("tools", "recon_agent")

    ctf_graph = builder.compile()

    # Prepare initial state
    endpoint = get_service_host_port(benchmark_name)
    print(f"Access the service at: {endpoint}")

    initial_state = {
        "messages": [
            SystemMessage(content=system_prompt),
            SystemMessage(
                content=f"The access point to the vulnerable service is: {endpoint}"
            ),
        ],
        "llm_executor": llm_executor,
        "steps": 0
    }
    try:
        ctf_graph.invoke(
        initial_state,
        config={
            "recursion_limit": 60,
            "callbacks": [CostTracker(model)],
        })

    except Exception as e:
        err = str(e).lower()
        if "recursion" in err or "depth" in err:
            print("\n❌ Recursion limit reached — stopping execution safely.")
        else:
            print("\n❌ Unexpected error while executing graph:")
            traceback.print_exc() 

    finally:
        sandbox.kill()

        if LAST_MESSAGES:
            context_dump = {
                "messages": dump_context(LAST_MESSAGES),
                "total_messages": len(LAST_MESSAGES),
            }
            (reports_dir / "history.json").write_text(
                json.dumps(context_dump, indent=2)
            )
            final_content = get_text_content(LAST_MESSAGES[-1])
            try:
                report = json.loads(final_content)
                (reports_dir / "report.json").write_text(
                    json.dumps(report, indent=2)
                )
            except Exception:
                (reports_dir / "report.txt").write_text(
                    str(final_content)
                )

        TRACKER.mark_end()
        TRACKER.print_summary()
        TRACKER.save(reports_dir / "tracker.json")

    return 