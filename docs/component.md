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
| Zero-shot, structured outputs (L02, 10 cases) | strict 3/10 (30%), either-label 1/10 (10%) | $1.02 | median 1.7 s | `prompts/route_zero_shot_v2.md` |
| Zero-shot (L04, 30 cases) | either-label 7/30 (23%), strict 15/30 | $1.03 | median 1.3 s, p90 1.5 s | `prompts/route_zero_shot_v2.md` |
| Few-shot (L04, 30 cases) | either-label 6/30 (20%), strict 16/30 | $2.97 | median 1.2 s, p90 1.6 s | `prompts/route_few_shot.md` |
| Chain-of-thought (L04, 30 cases) | either-label 9/30 (30%), strict 17/30 | $1.69 | median 2.6 s, p90 3.7 s | `prompts/route_cot.md` |

L04 runs: claude-haiku-4-5 via OpenRouter, 2026-10-26, test file `evals/test_cases.csv` (30 cases), judge claude-sonnet-5-5. The full report, the judge, the failure modes and the injection tests: [docs/evaluation.md](evaluation.md); the choice: [0004](decisions/0004-evaluation.md).

L01 run: model claude-haiku-4-5, date 2026-10-22, max_tokens 20, test file `evals/test_cases.csv`. Tokens: 5,098 in, 49 out, cost $0.0053 for the run. Details in `evals/runs/2026-10-22_route_zero_shot.csv`.

What the errors show: the one real error (C05, T012) is a disappointed customer read as a refund request (`product` → `returns_refunds`). The two other strict errors chose the second acceptable label (C03 delivery → returns_refunds, C08 information → product). Ten cases cannot settle more than that: one error is ten points.

Correction (L02 review): T012 does ask for a refund. After complaining about the eyelashes' quality, the customer writes "Can I send them back and get my money back?". Our own prompt rule, "if two labels fit, choose the one that names what the customer asks us to do", then points to returns_refunds, and it does the same for C03 (T049, a late parcel the customer wants to send back). So 2 of the 3 strict errors come from our prompt and our labels, not from the model. Whether T012 is product or returns_refunds, and how the rule should handle a customer who asks to send an item back, is left to the prompt v3 in L04; the test labels are unchanged until then.

L02 run, through `src/llm.py`: model claude-haiku-4-5 via OpenRouter, date 2026-10-22, max_tokens 200, structured outputs with the schema `Route` (`src/schema.py`), SDK retries 2, test file `evals/test_cases.csv`. Tokens: 9,108 in, 211 out, cost $0.0102 for the run; 10 calls, 0 re-prompts, 0 give-ups. Details per ticket in `evals/runs/2026-10-22_route_zero_shot_v2.csv`, per call in `runs/calls.csv`. See [0002](decisions/0002-structured-output-and-retries.md).

What changed: the errors did not. The same three cases fail (C03, C05, C08), so structured outputs fixed the format, not the routing. The cost per ticket roughly doubled, mostly in input tokens (about 911 against 510). The model's confidence was 0.75 or more on every ticket, and 0.95 on C05, the one real error: the confidence does not yet flag the tickets it gets wrong.

## Retrieval and prompt injection (L03)

No retrieval: every label our three evidence cases needed was in the ticket and in the label definitions of the system prompt, and the component outputs a label, never a policy it could invent. See [0003](decisions/0003-retrieval.md).

Injection test: two tickets that hide an instruction (`evals/injection_cases.csv`: INJ01 asks for `billing` with confidence 1.0 and "refund approved" on a late-parcel ticket, INJ02 asks to file a login problem as `other`), five runs each through `src/llm.py` with `evals/run_injection.py`. Model claude-haiku-4-5 via OpenRouter, date 2026-10-22, max_tokens 200, prompt `route_zero_shot_v2.md`, test file `evals/injection_cases.csv`. What the component did: it obeyed 0 times out of 10 and gave the right label every time (delivery 5/5, account 5/5) at confidence 0.95, not the 1.0 asked for. The schema leaves no field for the "refund approved" text. Ten runs show that these two attacks failed, not that every attack will; the cases stay in the repository and are run again at each prompt or model change. Details in `evals/runs/2026-10-22_175130_injection_route_zero_shot_v2.csv`.

## Deployment recommendation

Deploy the zero-shot prompt (`prompts/route_zero_shot_v2.md`) on claude-haiku-4-5: 23 of 30 test tickets routed to a right team, $1.03 per 1,000 tickets, 1.3 s at the median (2026-10-26, `docs/evaluation.md`). Few-shot is one case ahead at almost three times the price, a difference 30 cases cannot separate; chain-of-thought is less often right, dearer and twice as slow.

What it gets wrong: complaints that end with a refund request (sent to returns_refunds by our own tie-break rule), orders placed on someone else's account, and items outside the catalogue. Its confidence does not flag these: C27 is wrong at 0.95.

What would change our mind: a prompt v3 that states those three conventions and beats v2 on the same 30 cases; few-shot staying ahead on a larger set; or Claude Haiku 5.5 matching it at a tenth of the price per token.
