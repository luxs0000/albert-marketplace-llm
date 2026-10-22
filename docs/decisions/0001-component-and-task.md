# 0001: Route support tickets with a prompt-driven classifier

Status: accepted
Date: 2026-10-22
Author: Eliott Monneraie
Lesson: L01

## Context

Albert's Marketplace's support tickets arrive in one inbox, in English, French and German, and must reach one of eight teams. In the company's sample (tickets_v1.csv, 120 tickets), 60% have a second plausible label and 31% belong to no team (`other`). The course offers three kinds of component; we must choose one and defend it.

## Options considered

| Option | For | Against |
|---|---|---|
| Classifier (tickets) | The answer is in the ticket; 120 tickets already labelled by people; output is one of 8 labels, easy to check in code and to score | Ambiguous tickets: a strict error rate will look worse than the real one |
| Extraction (reviews or tickets) | Richer output (order id, product, request) | No business owner asked for these records yet; harder to score (several fields per case) |
| Retrieval (help centre) | Answers customers directly | Solves another problem (answering, not routing); more moving parts before the first figure |

## Criteria

- The business need is clear and measurable: classifier yes, extraction partly, retrieval yes.
- The right answer can be checked by a person: classifier yes (one label), the others take longer per case.
- Labelled data exists: classifier yes (120 tickets), the others no.
- Risk of misuse can be shown: all three (a ticket can carry an injected instruction).

## Decision

We build a classifier that routes each ticket to one of eight labels, starting with a zero-shot prompt (`prompts/route_zero_shot.md`).

## Consequences

- First figure: zero-shot on the 10 test cases, claude-haiku-4-5, 2026-10-22, max_tokens 20: 3/10 strict errors, 1/10 either-label, $0.53 per 1,000 tickets.
- Easier: every prompt change is scored on the same test cases, strict and either-label.
- Harder: ambiguous tickets. We report both error rates and keep the second acceptable label in the test file.
- To watch: the `other` label, which mixes spam and real complaints; tickets written to manipulate the model (lesson 3); and whether retrieval is needed at all (likely not, decision expected in L03).
