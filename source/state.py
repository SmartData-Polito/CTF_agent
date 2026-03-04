from langgraph.graph import MessagesState as BaseMessagesState
from typing import Any,Optional

class MessagesState(BaseMessagesState):
    llm_executor: Any
    success: bool
    use_evaluator: bool
    benchmark: str 
    report_timestamp: Optional[str] = None