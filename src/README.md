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
  `runs/calls.csv`. Why it works this way: [ADR 0002](../docs/decisions/0002-structured-outputs-sdk-retries.md).

Run from the repository root: `python evals/run_prompt.py prompts/route_zero_shot_v2.md`.
