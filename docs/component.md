# Our component

Filled in from L01, and kept current: it is the page you present at the defence.

## The task

Albert's Marketplace receives support tickets in English, French and German, about payments, parcels, returns, accounts, third-party sellers and products, mixed with spam and sales pitches. Today an agent reads each ticket to decide which team handles it. A ticket sent to the wrong team waits in the wrong queue, and the customer waits with it. The users of the result are the support agents and the team leads who staff each queue.

The difficulty is real: in the company's sample of 120 labelled tickets (tickets_v1.csv), 72 (60%) have a second plausible label, and 37 (31%) belong to none of the teams (`other`: spam, partnership offers, complaints about reviews).

## Which component

A prompt-driven classifier. The answer to "which team?" is in the ticket itself: the model needs no company document to choose a label, and the output is one of eight known labels, which code can check and an error rate can measure. Extraction would give more detail than the routing needs; retrieval answers questions from documents, which is not the task. See [0001](decisions/0001-component-and-task.md).

## Inputs and outputs

| | |
|---|---|
| Input | one ticket: its subject and body, in English, French or German |
| Output | one label: billing, delivery, returns_refunds, account, seller, product, information, other |
| Data used | `tickets_v1.csv`, release tickets-v1.0.0 of the company repo, sha256 `df81753e…41018a`, downloaded and checked by `evals/run_prompt.py` |

Test cases: 10 tickets in `evals/test_cases.csv`, covering the 8 labels, 3 languages, 5 with a second acceptable label. They are not among the tickets used in class (T005, T008, T016, T018, T023, T024, T032, T034, T042, T045).

## Strategies compared

Zero-shot, few-shot and chain-of-thought on the same 30 test cases (L04).

| Strategy | Error rate | Cost per 1,000 calls | Latency | Prompt file |
|---|---|---|---|---|
| Zero-shot (L01, 10 cases) | strict 3/10 (30%), either-label 1/10 (10%) | $0.53 | not measured | `prompts/route_zero_shot.md` |

L01 run: model claude-haiku-4-5, date 2026-10-22, max_tokens 20, test file `evals/test_cases.csv`. Tokens: 5,098 in, 49 out, cost $0.0053 for the run. Details in `evals/runs/2026-10-22_route_zero_shot.csv`.

What the errors show: the one real error (C05, T012) is a disappointed customer read as a refund request (`product` → `returns_refunds`). The two other strict errors chose the second acceptable label (C03 delivery → returns_refunds, C08 information → product). Ten cases cannot settle more than that: one error is ten points.

## Deployment recommendation

Which variant you would deploy, what it costs, what it gets wrong, and what would make you change your mind.
