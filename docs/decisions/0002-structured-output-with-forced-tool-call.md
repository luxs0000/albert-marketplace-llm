# 0002: Get the label through a forced tool call validated by pydantic

- **Status:** proposed
- **Date:** 2026-10-22
- **Author:** Louis Pimont-Nishimura
- **Lesson:** L02

## Context

The L01 script (`evals/run_prompt.py`) asks for "the label only" and takes the first known label in the free text. An answer with no known label counts as an error, so a formatting failure and a wrong routing look the same in the error rate. In production, a ticket with no label would reach no team.

Our keys are OpenRouter keys (`.env.example`), called through the Anthropic SDK. Any method must work through `https://openrouter.ai/api`.

## Options considered

| Option | For | Against |
|---|---|---|
| Free text, parsed in code (L01) | Cheapest: about 5 output tokens per ticket | No contract: a sentence, a typo or a new word gives no label, and is counted as a routing error |
| JSON asked for in the prompt, parsed with `json.loads` | Simple, no extra tokens for a tool | The model can still add text around the JSON or invent a label; we only find out after parsing |
| Forced tool call (`tool_choice` on a `route_ticket` tool), input checked by pydantic | The answer has a schema; the 8 labels are an enum; a bad answer raises an error we can retry | Each call carries the tool definition: more input and output tokens |
| Native structured outputs of the API | Schema enforced by the API itself | Not tested through OpenRouter; a newer feature, so a risk for a shared group setup |

## Criteria

- **A bad format is caught, not counted as a routing error:** only the tool call and native outputs guarantee it; the tool call is the one we checked works through OpenRouter (2026-10-22, claude-haiku-4-5).
- **Cost:** the tool adds tokens. Measured on two demo tickets (claude-haiku-4-5, 2026-10-22, max_tokens 100, short system prompt): 728 and 737 input tokens, 33 output tokens each. A one-line message with a 3-label tool already took 674 input tokens, so the tool and its framing cost several hundred tokens per call; the L01 zero-shot run used about 510 input and 5 output tokens per ticket. To be measured on `evals/test_cases.csv` before any figure is published.
- **Easy to change:** the labels live in one place, the `Label` type in `src/client.py`; the tool schema is generated from it.

## Decision

`src/client.py` calls the model with a forced `route_ticket` tool whose input schema is the pydantic model `Route`. The SDK retries rate limits, server and network errors (3 retries, 30 s timeout); an answer that fails validation is asked again once, then raises `InvalidOutput`.

## Consequences

- Easier: an error in `evals/` now means a wrong label, not a badly written one. A ticket the model cannot label raises an error the caller can send to a human.
- Harder: more tokens per call, so the cost per 1,000 calls in `docs/component.md` must be measured again with this client.
- To watch: the system prompt of `route_zero_shot.md` still says "answer with the label only", which is redundant with the tool; a v2 prompt should drop it. Whether the extra tokens change the cost ranking of strategies in L04.
