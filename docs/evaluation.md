# Evaluation report (L04)

## What was measured

- **Component:** the ticket router of `src/llm.py`, structured outputs, schema
  `Route` (`RouteCoT` for chain-of-thought), max_tokens 200 (600 for
  chain-of-thought), SDK retries 2, at most 2 re-prompts.
- **Model:** claude-haiku-4-5, through OpenRouter. Runs of 2026-10-26.
- **Test file:** `evals/test_cases.csv`, 30 tickets of the company release
  tickets-v1.0.0 (sha256 `df81753e…41018a`): the 10 of L01 and 20 added in L04,
  chosen to be hard. All eight labels (seller 6, delivery 5, other 5, account 4,
  billing 3, returns_refunds 3, product 2, information 2); 21 of 30 with a
  second acceptable label; 5 in French and 5 in German; spam, a competitor's ad
  and off-catalogue complaints that belong to `other`; children writing from a
  parent's account, which belong to `account`. Each label checked by a member
  who did not write it.
- **Strategies:** zero-shot (`prompts/route_zero_shot_v2.md`), few-shot
  (`prompts/route_few_shot.md`, the same system prompt plus eight solved
  tickets that are not test cases), chain-of-thought (`prompts/route_cot.md`, the
  same system prompt plus a reasoning written before the label).
- **Scorers:** exact match on the label, the main label or the second
  acceptable one (`src/evaluate.py`, tested in `tests/test_evaluate.py`); a judge,
  claude-sonnet-5-5, scoring the four criteria of `evals/rubric.md`
  (`prompts/judge.md`). Why: [ADR 0004](decisions/0004-evaluation.md).

## The table

claude-haiku-4-5 via OpenRouter, 2026-10-26, `evals/test_cases.csv` (30 cases),
one run per strategy. Report: `runs/eval/2026-10-26_130406_report.md`.

| Strategy | Right of 30 (exact match, either label) | Main label only | Right by the judge (score 4-5) | Tokens per call, in / out | Per 1,000 calls | Median | p90 | Pareto |
|---|---|---|---|---|---|---|---|---|
| Zero-shot | **23** | 15 | 23 | 912 / 23 | **$1.03** | **1.3 s** | 1.5 s | on the front |
| Few-shot | **24** | 14 | 24 | 2,838 / 26 | $2.97 | 1.2 s | 1.6 s | on the front |
| Chain-of-thought | 21 | 13 | 21 | 1,039 / 129 | $1.69 | 2.6 s | 3.7 s | dominated |

No call gave up; one re-prompt in 90 calls (chain-of-thought). Cost per 1,000
calls is computed from the measured tokens of every call, re-prompts included,
input at $1 and output at $5 per million tokens (claude-haiku-4-5, Anthropic's
pricing as quoted in lesson 4, 14 October 2026). Latency is the time the
customer waits for one ticket, every attempt included.
Files: `runs/eval/2026-10-26_122143_judged_zero_shot.csv`,
`runs/eval/2026-10-26_122510_judged_few_shot.csv`,
`runs/eval/2026-10-26_122830_judged_cot.csv`; every call in `runs/calls.csv`.

**The Pareto front** (right answers, cost, median latency): zero-shot and
few-shot. Few-shot is one case ahead and 0.1 s faster at the median; zero-shot
costs a third of the price. Chain-of-thought is dominated: zero-shot is more
often right, cheaper and twice as fast.

Where the money goes: few-shot's eight examples triple the input (2,838 tokens
against 912); chain-of-thought's reasoning multiplies the output by five (129
against 23 tokens), at five times the input price.

## What 30 cases can tell

One case is 3.3 points. Few-shot against zero-shot (24 against 23) is one case:
30 cases cannot separate them, and we do not claim that few-shot is better.
Zero-shot against chain-of-thought (23 against 21) is two cases, 6.7 points:
a hint, not a proof; the latency and cost differences are not in doubt. The set
separates "wrong one time in four" from "right almost always", not 77% from 80%.

The right answers drop to about half with the main label only (13 to 15 of 30):
60% of the company's tickets fit two teams, and on those the model and the
person who labelled them often choose different sides of the line.

What the set does not test: tickets in other languages, tickets about several
orders at once, a change in what customers write about (a new product line, a
carrier strike), and the volume of a real day.

## The judge

- **Model:** claude-sonnet-5-5, a different model from the component's, and a
  stronger one. Same vendor: a weaker control than another vendor's model.
- **Agreement with exact match:** on all 90 answers, the judge's "right" (4 or
  5) and exact match's "right" are the same, case by case. Where a label is
  right, the judge adds a view of the second label and the confidence (for
  example, C05 zero-shot: wrong label at 0.95 confidence, score 2).
- **Calibration:** Clément Badalucco scored ten zero-shot answers by hand with
  `evals/rubric.md` (`evals/human_scores.csv`, cases C03, C05, C08, C11, C15,
  C17, C21, C24, C27, C30). Same overall score as the judge: **9/10**; same right
  / not right: **10/10**. The one difference is C05 (wrong team, the right one
  second at 0.95 confidence): 3 by hand, 2 by the judge, so the judge is the
  harsher of the two there. Ten cases scored by one member is a
  small check: a second member scoring the same ten would tell us how much two
  people agree, which is the ceiling the judge can reach.
- **The swap:** zero-shot against chain-of-thought, each pair judged twice, in
  both orders (`runs/eval/2026-10-26_130406_swap_zero_shot_vs_cot.csv`). 12 pairs
  were ties (same label, same second label, confidence within 0.05) and were not
  judged. Of the 18 pairs judged, 1 verdict changed with the order (C10) and
  counts as no preference; zero-shot won 9, chain-of-thought 8.
- **Cost:** about $6.40 per 1,000 verdicts (runs above), six times the router's
  cost per ticket, paid only when we evaluate.

## Failure modes

Every wrong case (exact match, either label), read by a person and grouped by
cause. 7 for zero-shot, 6 for few-shot, 9 for chain-of-thought; 4 cases fail with
all three (C05, C16, C23, C27).

| Cause | Cases | What happens |
|---|---|---|
| The prompt: our tie-break rule | C05 (all three); C06, C13, C17 (chain-of-thought) | "If two labels fit, choose the one that names what the customer asks us to do" sends any complaint that ends with "refund me" to `returns_refunds`. The company labels those by what the complaint is about (`product`, `seller`). Chain-of-thought applies the rule more strictly: its reasoning quotes it and concludes `returns_refunds`. |
| The prompt: a convention it does not state | C27 (all three), C20 (zero-shot, chain-of-thought), C24 (zero-shot, chain-of-thought) | The company sends a child writing from a parent's account to `account`, a complaint about an item that is not a beauty product (a carburettor) to `other`, and a formal objection to a seller's terms to `other`. Our label definitions say none of this. |
| The model | C27 | It answers `delivery` at 0.92 to 0.95 confidence, with no second label: the confidence does not flag the error. |
| The test case | C16, C23 | Debatable lines in the release: a wrong item in the parcel (C16) is `delivery`, a late parcel whose customer blames the seller (C23) is `seller` with `other` as second. When they checked the 20 new cases, two members would have labelled C23 and C27 `delivery`, and one C16 `seller`, C17 `product` and C19 `seller`: each time the model's own answer. We kept the release's labels, which were fixed before the run: changing them after reading the model's answers would fit the test to the model, and the score would measure nothing. |
| The examples (few-shot only) | C19 | The T019 example (a refund request labelled `product`) pulls a returns ticket toward `product`. |
| The scorer | none found | Exact match and the judge agree on every case; no right answer was marked wrong. |

Retrieval is not a cause: the component has none ([ADR 0003](decisions/0003-retrieval.md)).

One failure, spelled out (C27, all three strategies):

| | |
|---|---|
| Input | T101, "wher is my order???": a child who ordered on a parent's account asks when the parcel arrives, and where to leave it |
| Output | `delivery`, confidence 0.95, no second label (zero-shot) |
| Expected | `account`, second acceptable `billing` |
| Why | The words are a delivery question; the company routes orders placed on someone else's account to the account team. The label definitions in our prompt do not say so, and the model is sure of itself. |

## Injection tests

`pytest tests/test_guardrails.py`, 2026-10-26, claude-haiku-4-5 via OpenRouter,
prompt `route_zero_shot_v2.md`: **14 passed** in 82 s (9 offline tests, and the 5
attacks run live 3 times each: none of the 15 tickets was sent to the
attacker's team, and each went to its own team or to a person). Cost under
$0.02.

- Five attacks (`evals/injection_cases.csv`): a label and a refund promise
  dictated in English (INJ01), a real ticket hidden in `other` in French (INJ02),
  a label dictated in German (INJ03), a request to leave the task and write a
  reply (INJ04), and an instruction disguised as an internal routing note with
  no word about AI (INJ05).
- Each runs 3 times through the whole component, output check included
  (`src/component.py`), and the test asserts on the queue the ticket is sent to,
  never on what the model wrote: never the attacker's team, and always a team
  that can act on the ticket, or a person.
- Offline, a fake model that obeys every attack: the output check alone keeps
  each ticket away from the attacker's team, and none of the company's 120 real
  tickets trips it.
- The limit: the check recognises instructions with patterns grown from our
  own attacks. An attack phrased differently reaches the model unchecked, and
  only the live runs show whether the model resists it.

## Recommendation

Deploy the zero-shot prompt on claude-haiku-4-5: 23 of 30 right, $1.03 per
1,000 tickets and 1.3 s at the median, against few-shot's 24 of 30 at $2.97,
a one-case difference that 30 cases cannot separate. Next, a prompt v3 that
states the three conventions behind most errors (refund requests labelled by
their cause, orders on someone else's account, off-catalogue items), measured
on the same 30 cases before it replaces v2.
