from datetime import datetime
from typing import Optional
import json
from langchain_core.callbacks import BaseCallbackHandler

MODEL_PRICING = {
    "gpt-5":      {"prompt": 0.0125, "cached": 0.00125, "completion": 0.10},
    "gpt-5-mini": {"prompt": 0.0025, "cached": 0.00025, "completion": 0.02},
    "gpt-5-nano": {"prompt": 0.0005, "cached": 0.00005, "completion": 0.004},
    "gpt-4.1":    {"prompt": 0.02,   "cached": 0.005,   "completion": 0.08},
    "gpt-4.1-mini":{"prompt": 0.004, "cached": 0.001,  "completion": 0.016},
    "gpt-4.1-nano":{"prompt": 0.001, "cached": 0.00025,"completion": 0.004},
    "gpt-4o":     {"prompt": 0.025,  "cached": 0.0125, "completion": 0.10},
    "gpt-4o-mini":{"prompt": 0.0015, "cached": 0.00075,"completion": 0.006},
}



class Tracker:
    def __init__(self):
        self.reset()

    def reset(self, model: str = "gpt-5"):
        if model not in MODEL_PRICING:
            raise ValueError(f"Unknown model '{model}'. Choose from: {list(MODEL_PRICING.keys())}")

        self.model = model
        self.start_time = None
        self.end_time = None
        self.llm_calls = 0
        self.tokens_in = 0           # billable prompt tokens
        self.cached_tokens = 0       # discounted cache reads
        self.tokens_out = 0          # completion tokens
        self.reasoning_tokens = 0    # special output tokens
        self.total_tokens = 0
        self.cost = 0.0
        self.tool_calls = 0
        self.steps = 0
        self.success = None

    # ---- TIME -----------------------------------------------------
    def mark_start(self):
        self.start_time = datetime.now()

    def mark_end(self, success: Optional[bool] = None):
        self.end_time = datetime.now()
        if success is not None:
            self.success = success

    # ---- STEPS ----------------------------------------------------
    def step(self):
        self.steps += 1

    # ---- LLM USAGE -----------------------------------------------

    def add_llm_usage(self, model: str, usage: dict):
        if model not in MODEL_PRICING:
            raise ValueError(f"Unknown model '{model}'")

        pricing = MODEL_PRICING[model]
        # Extract token counts
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        input_details = usage.get("input_token_details", {})

        # Billable prompt tokens = input - cache_read
        cache_tokens = input_details.get("cache_read", 0)
        billable_prompt_tokens = max(input_tokens - cache_tokens, 0)

        # Update counters
        self.llm_calls += 1
        self.tokens_in += billable_prompt_tokens
        self.cached_tokens += cache_tokens
        self.tokens_out += output_tokens
        self.total_tokens += billable_prompt_tokens + cache_tokens + output_tokens

        prompt_units = billable_prompt_tokens / 10000
        cache_units  = cache_tokens / 10000
        output_units = output_tokens / 10000

        cost  = prompt_units * pricing["prompt"]
        cost += cache_units  * pricing["cached"]
        cost += output_units * pricing["completion"]
        self.cost += cost

    # ---- TOOL CALLS ----------------------------------------------
    def record_tool_call(self ):
        self.tool_calls += 1

    # ---- EXPORT ---------------------------------------------------
    def to_dict(self):
        duration = None
        if self.start_time and self.end_time:
            duration = str(self.end_time - self.start_time)


        data = {
            "llm_calls": self.llm_calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "total_tokens": self.total_tokens,
            "tool_calls": self.tool_calls,
            "cost_usd": self.cost,
            "duration": duration,
        }

        if hasattr(self, "success") and self.success is not None:
            data["success"] = self.success

        return data

    def save(self, path="tracker.json"):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def print_summary(self):
        data = self.to_dict()
        print("\n===== EXECUTION METRICS =====")
        for k, v in data.items():
            print(f"{k}: {v}")
        print("================================\n")


# =================================================================
# GLOBAL SINGLETON (THIS IS THE IMPORTANT PART)
# =================================================================

TRACKER = Tracker()


# =================================================================
# CALLBACK (USES THE GLOBAL TRACKER)
# =================================================================

class CostTracker(BaseCallbackHandler):
    def __init__(self, model_name: str):
        self.model_name = model_name

    def on_llm_end(self, response, **kwargs):
        usage = None

        try:
            generation = response.generations[0][0]
            message = generation.message
            usage = getattr(message, "usage_metadata", None)
            if not usage:
                return
        except Exception:
            return
        
        TRACKER.add_llm_usage(
            model=self.model_name,
            usage=usage
        )