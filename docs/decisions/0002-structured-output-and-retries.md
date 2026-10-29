# 0002: Get the routing as structured outputs, with the SDK as the only retry layer

- **Status:** accepted
- **Date:** 2026-10-22
- **Author:** Louis Pimont-Nishimura, Khaled Elnagar
- **Lesson:** L02

## Context

In L01 the model answered in free text and our code searched it for a label. That works while the model answers with one word; it breaks the day it writes a sentence that names two labels. Step 2 asks for one module, `src/llm.py`, that is the only code calling the API, returns an answer checked against our own schema (`src/schema.py`: label, confidence, second_label, and a rule that a confidence below 0.7 needs a second label), checks `stop_reason`, re-prompts with the error at most twice, logs every call, and has exactly one retry layer.

Figures, claude-haiku-4-5 through OpenRouter, 2026-10-22, test file `evals/test_cases.csv`:
- L01, free text, `prompts/route_zero_shot.md`, max_tokens 20: about 510 input and 5 output tokens per ticket, $0.53 per 1,000 tickets (`evals/runs/2026-10-22_route_zero_shot.csv`).
- L02, structured outputs, `prompts/route_zero_shot_v2.md`, max_tokens 200: about 911 input and 21 output tokens per ticket, $1.02 per 1,000 tickets, median latency 1.7 s, 0 re-prompts and 0 give-ups on 10 tickets (`runs/calls.csv`, `evals/runs/2026-10-22_route_zero_shot_v2.csv`). Strict errors 3/10, the same cases as L01 (C03, C05, C08); either-label errors 1/10 (C05).

## Options considered

| Option | For | Against |
|---|---|---|
| Structured outputs (`output_config` with the JSON schema from `anthropic.transform_schema`) | The API enforces the shape: the answer always parses; the schema comes from our Pydantic model, one source of truth | About 400 more input tokens per ticket; our own rules (second label, confidence range) still need a validator, because `transform_schema` moves `minimum` and `maximum` into a description |
| A strict tool the model must call | Also enforces the shape; checked to work through OpenRouter | Also several hundred extra input tokens (674 for a one-line message with a 3-label tool, demo call 2026-10-22), and a tool call to unwrap for an answer that is not an action |
| JSON asked for in the prompt | Fewest tokens | Nothing enforces it: a missing brace or an extra sentence means a failed parse and a re-prompt |
| Retry layer: the SDK's, at its default (`max_retries=2`) | Already there, retries only connection errors, 408, 409, 429 and 5xx, with backoff, and follows the API's `retry-after` header | Two retries may not cover a long rate limit |
| Retry layer: the SDK's, with a higher `max_retries` | One line to change, still one layer | Hides a rate limit behind long waits, and each retry adds latency for the customer |
| Retry layer: our own (tenacity, `max_retries=0` on the client) | We choose the wait and the number of attempts | More code to write and test; two layers if we forget `max_retries=0` |

## Criteria

- Every answer usable by code without guessing: structured outputs and the strict tool yes, JSON in the prompt no.
- Cost per 1,000 tickets: JSON in the prompt cheapest; structured outputs $1.02, about double L01, still about a tenth of a cent per ticket.
- Simplicity of `src/llm.py`: structured outputs and the SDK's retries need the fewest lines.
- Robustness to rate limits: our own policy could wait longer; the SDK's default has not failed on our runs so far.

## Decision

We use structured outputs, with our rules checked by a Pydantic validator and at most two re-prompts that tell the model what was wrong. We keep the SDK's retries at their default as the only layer, and pace the evaluation runs (4 seconds between tickets) to stay under OpenRouter's request limit instead of adding a second layer.

## Consequences

- Easier: no parser to maintain; every call is logged in `runs/calls.csv` with its `request_id`, tokens, latency, attempt, `stop_reason` and validity, so L04 can compute the cost per 1,000 calls from it and support can trace any call. An API error that survives the SDK's retries is logged too, and only that ticket is given up: the run goes on.
- Harder: each ticket costs about twice as many tokens as in L01. In the worst case one ticket makes 3 calls (1 + 2 re-prompts), each retried up to 2 times by the SDK: 9 requests.
- To watch: the pacing only protects our evaluation runs; in production a burst of tickets could still hit a 429. If it does, raise `max_retries` or replace the SDK's retries with our own policy and `max_retries=0`, in a new record that supersedes this one. The confidence is 0.75 or more on every ticket, and 0.95 on the one real error (C05): the 0.7 rule never fired, and we will check in L04 whether the confidence means anything.
