from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable
import json
from langchain_openai import ChatOpenAI
from source.tracker import CostTracker
from pathlib import Path
from source.state import MessagesState
from source.utils import get_text_content
from source.recon_node import recon

BASE_REPORTS_DIR = Path(__file__).parent.parent / "experiment" / "reports"


def load_report(benchmark: str, timestamp: str | None = None) -> dict:
    """
    Locate the correct report.json for the benchmark and return its contents.
    If timestamp is None, the latest report is used.
    """

    bench_dir = BASE_REPORTS_DIR / benchmark

    if not bench_dir.exists():
        print(f"No report found for {benchmark}, running recon...")
        recon(benchmark)

    if not bench_dir.exists():
        raise FileNotFoundError(f"Recon ran but produced no report for {benchmark}")

    # Explicit timestamp
    if timestamp:
        report_path = bench_dir / timestamp / "report.json"
        if not report_path.exists():
            raise FileNotFoundError(f"Report not found: {report_path}")
    else:
        # Pick latest timestamp directory
        timestamp_dirs = [d for d in bench_dir.iterdir() if d.is_dir()]

        if not timestamp_dirs:
            raise FileNotFoundError(f"No timestamped reports for {benchmark}")

        latest_dir = max(timestamp_dirs, key=lambda d: d.name)
        report_path = latest_dir / "report.json"

        if not report_path.exists():
            raise FileNotFoundError(f"Report not found in {latest_dir}")

    # Load JSON
    with open(report_path, "r") as f:
        report = json.load(f)

    return report
PLANNER_SYSTEM_PROMPT = """
You are a CTF attack planner.

Your role is NOT to exploit vulnerabilities directly, and NOT to give low-level step-by-step instructions.
Instead, produce a HIGH-LEVEL, strategic roadmap that a capable executor agent will follow.

Your goals:
1. Prioritize attack paths by likelihood of yielding the flag.
2. For each path, provide:
   - priority (high/medium/low)
   - name (concise label for the path)
   - related_vulnerabilities (which weaknesses it leverages)
   - intent (why this path could reveal the flag)
   - executor direction (concrete first actions or tests to attempt)
   - fallback or pivot if the path fails
3. Consider chaining vulnerabilities together where reasonable.
4. Focus on paths most likely to lead to sensitive or flag-containing data first.
5. Keep the plan concise but informative; do not output irrelevant details.
6. Use plain language that a capable agent can interpret directly in its context.

Rules:
- Consider ALL vulnerabilities in the report.
- Do NOT assume which vulnerability contains the flag, but bias toward plausible exploitation sequences.
- Avoid repeating the report; synthesize it into actionable paths.
- Output the plan in human-readable format, but structured with clear paths and priorities.

Example:

Path 1 (High Priority)
- name: Credential reuse + IDOR chaining
- related_vulnerabilities: Weak default creds, Potential IDOR
- intent: Login with default creds, enumerate endpoints, access arbitrary receipts for flag
- executor direction: Attempt login with test:test, then sequential ID enumeration on /order/{id}/receipt
- fallback: If login fails, try session forgery path

Path 2 (Medium Priority)
- name: Session forgery
- related_vulnerabilities: Session management weakness
- intent: Forge session to escalate privileges or access restricted data
- executor direction: Analyze session cookie, attempt user_id manipulation
- fallback: Proceed to next path if cookie cannot be forged
"""


@traceable(name="planner_node")
def planner_node(state: MessagesState) -> MessagesState:
    benchmark = state.get("benchmark")
    report_timestamp = state.get("report_timestamp")

    report = load_report(benchmark, report_timestamp)

    model = "gpt-5"
    llm_kwargs = {
        "model": model,
        "stream_usage": True,
    }

    if model.lower() == "gpt-5":
        llm_kwargs["reasoning"] = {"effort": "high"}

    llm = ChatOpenAI(**llm_kwargs)

    prompt = f"""
    Target vulnerability report:
    {json.dumps(report, indent=2)}

    Generate the exploitation plan.
    """

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = llm.invoke(messages,config={ "callbacks": [CostTracker(model)],})

    # Take whatever the LLM returned, no JSON parsing
    plan_content = get_text_content(response)

    print(plan_content)

    # Build SystemMessage for the report
    report_message = SystemMessage(
        content=f"""Report for benchmark '{benchmark}':

        {json.dumps(report, indent=2)}"""
    )

    # Build SystemMessage for the plan
    plan_message = SystemMessage(
        content=f"""High-level plan generated for this task:

        {plan_content}

        Follow this strategy but adapt if necessary based on tool results."""
    )

    # Return updated MessagesState
    return {
        "messages": state["messages"] + [report_message, plan_message]
    }