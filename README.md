# Albert's Marketplace LLM component: group repo

This repository is your group's LLM component for **Albert's Marketplace**, the
fictional European beauty marketplace of the LLM Fundamentals, Prompting & API
Integration course (MSA-DATI07-08, Albert School).

It starts almost empty. Every lesson adds a layer on top of the previous one. By
the end of the course it holds the component your group defends orally: one of
- a prompt-driven **classifier** (support tickets)
- a **structured-extraction** tool (product reviews)
- a **retrieval** layer that answers from the company's own documents

with reproducible code, a comparison of prompting strategies on 30 test cases,
an evaluation report, prompt-injection guardrails and a cost per 1,000 calls.

## Team

| Name | GitHub | Role |
|---|---|---|
| Eliott Monneraie | emonneraie-blip | Task and test cases (ADR 0001) |
| Louis Pimont-Nishimura | LesCavesdAlbert | API module and structured output (ADR 0002, L02) |
| Lucas Stefani | luxs0000 | Retrieval decision and injection test (ADR 0003, L03) |
| Clément Badalucco | clementbada | Evaluation and cost (ADR 0004, L04) |

## How this repo grows

| Lesson | What your group adds | Where |
|---|---|---|
| L01 · Tokens and prompting | The business task your component serves, a first prompt, its first 10 test cases | `docs/component.md`, `prompts/`, `evals/` |
| L02 · API and structured outputs | Calls through the API with retries and validated output; how keys are handled | `src/`, `requirements.txt` |
| L03 · Retrieval-augmented generation | Retrieval, if your task needs it, **or a decision record saying why not** | `src/`, `docs/decisions/` |
| L04 · Evaluation, cost and guardrails | The evaluation report: golden set, rubric, 30 cases × 3 strategies, failure modes, cost per 1,000 calls, an injection test that must refuse | `evals/`, `docs/` |
| L05 · Review | Project clinic: what the defence will ask | |
| L06 · Project defences | The deployment recommendation you defend | `docs/component.md` |

Starter files for later lessons arrive as **pull requests** opened by the
teaching team. Review and merge them like any other change.

## How we work

- **Every change goes through a pull request,** reviewed by another member
  before it reaches `main`.
- **One decision, one record** in `docs/decisions/`: a prompt pattern, a model,
  a schema, a retrieval setting. Every member writes at least one. At the oral
  defence, each of you defends a choice unprepared.
- **The commit history is graded.** Commit in small steps, with messages that
  say why.
- **A prompt is code.** It lives in `prompts/`, under version control, and a
  change to it is measured on the test cases before it is merged.
- **Every figure says where it came from:** the model, the date, the
  parameters and the test file. A model does not give the same answer twice.

## Your API key

**Each of you has your own Anthropic key, with a spending limit.** It is
personal: it never goes in this repository, in a notebook, in a screenshot or in
a chat message.

- Keep it in a `.env` file, which `.gitignore` already excludes, and copy the
  variable names from `.env.example`.
- **If a key reaches GitHub, even for a minute, tell the teaching team at once**
  so it can be revoked. Deleting the commit does not help: the key has already
  been copied.

**New member? In five lines:**
1. Copy `.env.example` to `.env` in the repository root and paste your own key in it, using the lines that match your key (Anthropic `sk-ant-` or OpenRouter `sk-or-`).
2. `.env` never reaches Git because `.gitignore` excludes it: anyone who can read the repo could spend on your key.
3. The code creates the client without a key argument; the SDK reads the key from the environment.
4. Run `git status` before every commit: `.env` must never appear in it.
5. If a key is pushed, tell the school coordinator at once so it is revoked; deleting the commit does not help.

## Layout

```
docs/
  component.md     the task, the users, the deployment recommendation
  evaluation.md    the evaluation report, from L04
  decisions/       one record per decision
  defence/         the slides of the oral defence, as a PDF, from L05
prompts/           every prompt, versioned, from L01
evals/             test cases, golden set and results, from L01
src/               the code that calls the model, from L02
runs/              every call (calls.csv) and every evaluation run (eval/), from L02
tests/             the scorers' tests and the injection tests, from L04
```

## Run it

What it does: reads one support ticket of Albert's Marketplace and sends it to the
team that should handle it (one of eight), or to a person when it cannot route it
safely. Who uses it: the support agents and the team leads of each queue.

**Install** (Python 3.12, from the repository root):
```
python3.12 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                # Windows: copy .env.example .env
```
Then open `.env` and put your key in it: one line for an Anthropic key, two
lines for an OpenRouter key (see "Your API key" above).

**Run it on one ticket:**
```
python -c "from src.component import handle_ticket; print(handle_ticket('Where is my parcel?', 'Order 35683 should have arrived today. Where is it?'))"
```

**Run the evaluation** (project step 4; results in `runs/eval/`, report in `docs/evaluation.md`):
```
python evals/run_eval.py all        # 3 strategies x 30 cases, the judge, the swap, the table: about 40 min, about $1
python evals/run_eval.py report     # the table again, from the saved runs
```

**Run the tests:**
```
pytest tests/test_evaluate.py       # the scorers: free, no key needed
pytest tests/test_guardrails.py     # the injection tests: offline, then live (needs a key, under $0.02)
```

The first run of `evals/run_eval.py` or of the tests downloads the company's
tickets to `data/tickets_v1.csv` and checks their checksum. Every call to the
model adds a row to `runs/calls.csv`, and every report is saved in `runs/eval/`.

**If something fails:**

| You see | What it means | What to do |
|---|---|---|
| `Could not resolve authentication method` | no key in `.env` | put your key in `.env`, next to `.env.example`, with no quotes or spaces around `=` |
| `The API refused the key (401)` | a wrong or revoked key | check the key; with an OpenRouter key, keep only the two OpenRouter lines |
| `NotFoundError` or `404` with an OpenRouter key | the address ends in `/api/v1` | it must be exactly `https://openrouter.ai/api` |
| `5 skipped` in `tests/test_guardrails.py` | no key in `.env`: the 5 live attacks are skipped | normal without a key; the 11 offline tests still run |

## Data

Albert's Marketplace's data, and its 120 labelled support tickets, are in the
company repo (link on the course site). They are synthetic or derived from
public datasets; their licence and attribution are stated there.

## Ownership

**No licence is granted for this repository.**
- **The template:** this README, the `docs/` templates and the folder structure
  remain the course author's intellectual property. Do not reuse them outside
  the course.
- **Your work:** what your group writes here belongs to your group.
