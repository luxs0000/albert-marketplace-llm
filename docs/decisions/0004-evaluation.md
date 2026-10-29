# 0004: Score the label by exact match, check it with a Sonnet 5.5 judge, and deploy the zero-shot prompt

- **Status:** accepted
- **Date:** 2026-10-26
- **Author:** Clément Badalucco
- **Lesson:** L04

## Context

Until L03 our classifier was judged on ten test cases read by eye: 3/10 strict
errors, 1/10 with the second acceptable label counted right (claude-haiku-4-5
via OpenRouter, 2026-10-22, `prompts/route_zero_shot_v2.md`). Ten cases cannot
separate two prompts: one case is ten points. Step 4 asks for three decisions,
recorded here: which scorers, which judge and how we know it can be trusted,
and which prompt strategy we deploy.

The facts that frame them:
- The output is a label from a closed list of eight. Whether it is right needs
  no model: it equals the label a person checked, or it does not.
- What a match cannot see is whether the rest of the answer helps the team that
  receives the ticket: a second label when two teams fit, and a confidence that
  says how clear the ticket is (60% of the company's tickets have a second
  plausible label, `docs/component.md`).
- The test set is now 30 cases (`evals/test_cases.csv`): one case is 3.3
  points.

## Options considered

**Scorers**

| Option | For | Against |
|---|---|---|
| Exact match on the label, either label counted right | Free, instant, no bias; tested on known pairs (`tests/test_evaluate.py`) | Blind to the second label and the confidence |
| BLEU, ROUGE, token F1 | Taught in L04 | Made for sentences; on a one-word label they reduce to exact match, and lesson 4 showed them rewarding wrong answers that copy |
| A model as judge only | Reads the second label, the confidence and the reasoning | Costs money, and is biased (position, verbosity); a label needs no reader |
| Exact match first, a judge for the rest (chosen) | Each tool where it is reliable | Two numbers to report and explain |

**Judge**

| Option | For | Against |
|---|---|---|
| Claude Haiku 4.5 | Cheapest | It is the component's own model: it would grade its own answers; lesson 4 measured 9 verdicts of 25 changed by the order |
| Claude Haiku 5.5 | Twenty times cheaper than Sonnet 5.5 | Lesson 4's Exercise 1: harsher and less reliable than Sonnet on the same answers |
| Claude Sonnet 5.5 (chosen) | A different model from the component's, and the strongest judge measured in lesson 4 (5 of 25 changed by the order) | Same vendor and training lineage as our model: a weaker control than another vendor; about $6.40 per 1,000 verdicts |

**Strategy:** zero-shot, few-shot (eight solved tickets) or chain-of-thought
(reasoning before the label), the same label definitions in all three.

## Criteria

- Quality: right answers out of 30, by exact match, with the judge's score as a
  second view.
- Cost per 1,000 calls, from the measured tokens, input and output at their own
  prices.
- Latency: median and 90th percentile.
- Whether the judge agrees with us: calibrated on ten cases scored by hand with
  `evals/rubric.md`.

## Results

claude-haiku-4-5 via OpenRouter, 2026-10-26, `evals/test_cases.csv` (30 cases),
judge claude-sonnet-5-5 (`runs/eval/2026-10-26_130406_report.md`):

| Strategy | Right of 30 | Per 1,000 calls | Median / p90 | Pareto |
|---|---|---|---|---|
| Zero-shot | 23 | $1.03 | 1.3 s / 1.5 s | on the front |
| Few-shot | 24 | $2.97 | 1.2 s / 1.6 s | on the front |
| Chain-of-thought | 21 | $1.69 | 2.6 s / 3.7 s | dominated |

The judge's "right" (score 4 or 5) matched exact match on all 90 answers. The
swap (zero-shot against chain-of-thought, both orders) changed 1 verdict of the
18 pairs judged. Calibration against our hand scores (ten zero-shot answers,
`evals/human_scores.csv`): 9/10 same overall score, 10/10 same right / not
right.

## Decision

1. **Scorers:** exact match on the label (either label counted right) is the
   number we report as "right"; the Sonnet 5.5 judge scores the four criteria of
   `evals/rubric.md` as a second view, and every pairwise comparison is judged in
   both orders.
2. **Judge:** Claude Sonnet 5.5. We trust it as far as the evidence goes: it
   agreed with exact match on every label, the order changed 1 verdict in 18,
   and it gave our own overall score on 9 of the 10 answers we scored by hand
   (the tenth one point harsher).
3. **Strategy:** zero-shot on claude-haiku-4-5, with a person routing every
   ticket answered below 0.7 confidence (on our 30 cases, the two such answers
   are both wrong, and no right answer is below 0.7). Few-shot is one case ahead (24
   against 23), which 30 cases cannot separate, at 2.9 times the cost.
   Chain-of-thought is dominated: two cases fewer, 64% dearer, twice as slow.

## What it cost

The evaluation itself: about $0.17 for the 90 router calls (from the table)
and about $0.80 for the judge's 90 scores and 36 pairwise verdicts (estimated at
$6.40 per 1,000 verdicts). Choosing zero-shot over
few-shot gives up one case on 30 that we cannot show is real, and saves $1.94
per 1,000 tickets.

## What would change our mind

- A larger test set (100 cases, about 1 point each) on which few-shot stays
  ahead of zero-shot: then its cost may be worth it.
- Claude Haiku 5.5, the course's default model from L04 (ten times cheaper per
  token than Haiku 4.5): if it is as right on our 30 cases, it dominates.
- A prompt v3 that states the three conventions behind most errors (see
  `docs/evaluation.md`, failure modes): if it beats v2 on the 30 cases, it
  replaces it, in a new record.
- A calibration where the judge and we disagree on more than 2 of 10: then the
  judge's scores are not reported, only exact match.

## Consequences

- Every prompt or model change is run on the 30 cases and the judge before it
  is merged (`python evals/run_eval.py all`, under $1).
- The judge's cost is paid only when we evaluate, never per ticket.
- To watch: the judge shares its vendor with our model; a check by another
  vendor's model, or by a person on a sample, is the next control. And
  confidence does not flag errors yet (C27: wrong at 0.95).
