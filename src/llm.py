# The only place that calls the model.
#
# - Structured outputs: the API must answer with the JSON schema of the answer we expect
#   (Route by default, src/schema.py)
# - One retry layer: the SDK's (connection errors, 408, 409, 429, 5xx, with backoff)
# - If the answer is cut, refused or breaks a rule of the schema, we re-prompt with
#   the error, at most MAX_REPROMPTS times, then give up
# - If the API still fails after the SDK's retries, the call is logged and we give up
#   on this ticket instead of stopping the whole run; a 401 or 403 is not retried
#   or caught, since a wrong key fails every ticket
# - Every call is logged in runs/calls.csv, one line per call, with its request_id
#
# L04: ask() takes the schema, the model and max_tokens as arguments, so that the
# chain-of-thought prompt (RouteCoT) and the judge (JudgeScore, JudgeChoice, on another
# model) go through this module too: nothing else in the repository calls the API.
# route() is unchanged for the code of L02 and L03.
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
LOG_FIELDS = ["timestamp", "tag", "case_id", "model", "attempt", "request_id", "stop_reason",
              "input_tokens", "output_tokens", "latency_ms", "valid", "error"]

load_dotenv()
client = anthropic.Anthropic(max_retries=SDK_RETRIES)


def output_format(schema):
    return {"type": "json_schema", "schema": anthropic.transform_schema(schema)}


OUTPUT_FORMAT = output_format(Route)   # kept for the code that imported it in L02


def log_call(row):
    new_file = not CALLS_LOG.exists()
    CALLS_LOG.parent.mkdir(exist_ok=True)
    with open(CALLS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def check(response, schema=Route):
    # Returns (answer, "") if the answer is usable, or (None, what went wrong)
    if response.stop_reason != "end_turn":
        return None, f"stop_reason was {response.stop_reason}, not end_turn"
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return schema.model_validate_json(text), ""
    except ValidationError as e:
        return None, "; ".join(err["msg"] for err in e.errors())


def ask(system, user, schema=Route, model=MODEL, max_tokens=MAX_TOKENS, tag="", case_id=""):
    # Returns (an instance of schema, or None if we gave up; the list of the logged calls)
    messages = [{"role": "user", "content": user}]
    calls = []
    fmt = output_format(schema)
    for attempt in range(1, MAX_REPROMPTS + 2):
        start = time.perf_counter()
        row = {"timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
               "tag": tag, "case_id": case_id, "model": model, "attempt": attempt}
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_config={"format": fmt},
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            raise   # a 401 or 403 will fail for every ticket: let the caller stop the run
        except anthropic.APIError as e:
            # The SDK has already retried: note the failure and give up on this ticket
            row.update({"request_id": getattr(e, "request_id", "") or "", "stop_reason": "",
                        "input_tokens": 0, "output_tokens": 0,
                        "latency_ms": round((time.perf_counter() - start) * 1000),
                        "valid": False, "error": f"{type(e).__name__}: {e}"})
            log_call(row)
            calls.append(row)
            return None, calls
        answer, error = check(response, schema)
        row.update({"request_id": response._request_id or "",
                    "stop_reason": response.stop_reason,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                    "valid": answer is not None, "error": error})
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


def route(system, user, tag="", case_id=""):
    # The routing call of L02 and L03: the Route schema, the default model and max_tokens
    return ask(system, user, schema=Route, tag=tag, case_id=case_id)
