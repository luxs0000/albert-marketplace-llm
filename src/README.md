# Source

The code that calls the model, from L02: the API client with its retries, the
output schemas and their validation, and, from L03, retrieval if your task
needs it.

The key is read from the environment (`.env`, see `.env.example`), never written
in the code.

- `schema.py`: the answer we accept (`Route`: label, confidence, second_label)
  and its rules. The labels are written here only.
- `llm.py`: the only code that calls the API. `route(system, user)` returns a
  checked `Route`, or `None` after two failed re-prompts, and logs every call in
  `runs/calls.csv`. Why it works this way: [ADR 0002](../docs/decisions/0002-structured-output-and-retries.md).

- `llm.py`, from L04: `ask(system, user, schema, model, max_tokens)` is the same
  call for any schema and model, so the chain-of-thought prompt (`RouteCoT`) and the
  judge (`JudgeScore`, `JudgeChoice`, on Claude Sonnet 5.5) go through it too.
- `component.py` (L04): the whole component, `handle_ticket(subject, body)`, and the
  output check that decides what is sent: a team, or a person (`triage`) when the
  call gave up or the label is the one an instruction in the ticket asked for.
- `evaluate.py` (L04): exact match on the label, the judge, the swap, cost and
  latency, the Pareto front, and the judge's calibration against our own scores.

Run from the repository root: `python evals/run_prompt.py prompts/route_zero_shot_v2.md`,
or `python evals/run_eval.py all` for the evaluation of L04.
