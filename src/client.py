# Calls the model to route one ticket, and returns a label that has been checked.
#
# Two kinds of retry:
#   - the API fails (rate limit, overload, network): the SDK retries with backoff
#   - the answer does not pass the schema: we ask again, up to MAX_ATTEMPTS times
#
# The key is read from .env (see .env.example), never written here.
#
# Usage:  python src/client.py "Subject" "Body of the ticket"

import sys
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 100     # a tool call takes more tokens than a bare label
API_RETRIES = 3      # SDK retries on 429, 5xx and connection errors
MAX_ATTEMPTS = 2     # calls allowed when the answer fails validation
TIMEOUT = 30         # seconds per call

Label = Literal["billing", "delivery", "returns_refunds", "account",
                "seller", "product", "information", "other"]


class Route(BaseModel):
    label: Label


# The model must answer by calling this tool: its input is our schema
ROUTE_TOOL = {
    "name": "route_ticket",
    "description": "Record the team label chosen for the ticket.",
    "input_schema": Route.model_json_schema(),
}


class InvalidOutput(Exception):
    pass


def make_client():
    load_dotenv()
    return anthropic.Anthropic(max_retries=API_RETRIES, timeout=TIMEOUT)


def classify(client, system, user):
    # Returns (Route, usage of every call made), or raises InvalidOutput
    usage = []
    for attempt in range(MAX_ATTEMPTS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[ROUTE_TOOL],
            tool_choice={"type": "tool", "name": "route_ticket"},
            messages=[{"role": "user", "content": user}],
        )
        usage.append(response.usage)
        for block in response.content:
            if block.type == "tool_use":
                try:
                    return Route.model_validate(block.input), usage
                except ValidationError:
                    break
    raise InvalidOutput(f"no valid label after {MAX_ATTEMPTS} attempts")


if __name__ == "__main__":
    subject = sys.argv[1] if len(sys.argv) > 1 else "Charged twice"
    body = sys.argv[2] if len(sys.argv) > 2 else "I was charged twice for my last order."
    system = "You route customer support tickets for Albert's Marketplace to one team."
    route, usage = classify(make_client(), system, f"Subject: {subject}\n\n{body}")
    print(route.label, "|", sum(u.input_tokens for u in usage), "in,",
          sum(u.output_tokens for u in usage), "out")
