# The only place that calls the model.
#
# - Structured outputs: the API must answer with the JSON schema of Route (src/schema.py)
# - One retry layer: the SDK's (connection errors, 408, 409, 429, 5xx, with backoff)
# - If the answer is cut, refused or breaks a rule of the schema, we re-prompt with
#   the error, at most MAX_REPROMPTS times, then give up
# - Every call is logged in runs/calls.csv, one line per call
#
# The key is read from .env (see .env.example), never written here.

import csv
import datetime
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from src.schema import Route

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 200
MAX_REPROMPTS = 2
SDK_RETRIES = 2      # the SDK's default, written here so it is a visible choice
CALLS_LOG = Path("runs/calls.csv")
LOG_FIELDS = ["timestamp", "tag", "case_id", "model", "attempt", "stop_reason",
              "input_tokens", "output_tokens", "latency_ms", "valid", "error"]

OUTPUT_FORMAT = {"type": "json_schema", "schema": anthropic.transform_schema(Route)}

load_dotenv()
client = anthropic.Anthropic(max_retries=SDK_RETRIES)


def log_call(row):
    new_file = not CALLS_LOG.exists()
    CALLS_LOG.parent.mkdir(exist_ok=True)
    with open(CALLS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def check(response):
    # Returns (Route, "") if the answer is usable, or (None, what went wrong)
    if response.stop_reason != "end_turn":
        return None, f"stop_reason was {response.stop_reason}, not end_turn"
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return Route.model_validate_json(text), ""
    except ValidationError as e:
        return None, "; ".join(err["msg"] for err in e.errors())


def route(system, user, tag="", case_id=""):
    # Returns (Route or None if we gave up, list of the logged calls)
    messages = [{"role": "user", "content": user}]
    calls = []
    for attempt in range(1, MAX_REPROMPTS + 2):
        start = time.perf_counter()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config={"format": OUTPUT_FORMAT},
        )
        answer, error = check(response)
        row = {"timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
               "tag": tag, "case_id": case_id, "model": MODEL, "attempt": attempt,
               "stop_reason": response.stop_reason,
               "input_tokens": response.usage.input_tokens,
               "output_tokens": response.usage.output_tokens,
               "latency_ms": round((time.perf_counter() - start) * 1000),
               "valid": answer is not None, "error": error}
        log_call(row)
        calls.append(row)
        if answer is not None:
            return answer, calls
        if response.stop_reason == "refusal":
            break   # asking again will not change a refusal
        # Re-prompt: show the model its answer and what was wrong with it
        text = "".join(block.text for block in response.content if block.type == "text")
        messages.append({"role": "assistant", "content": text.strip() or "(empty answer)"})
        messages.append({"role": "user", "content": f"Your answer was rejected: {error}. "
                                                    "Answer again, following the schema."})
    return None, calls
