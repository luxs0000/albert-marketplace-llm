# 0003: Route tickets without retrieval

- **Status:** proposed
- **Date:** 2026-10-22
- **Author:** Lucas Stefani
- **Lesson:** L03

## Context

Our component routes each support ticket to one of eight teams. Lesson 3 asks whether it needs facts the model cannot know (a policy, a catalogue) and therefore retrieval. The component does not answer the customer: its output is one of eight labels, so it cannot state an invented policy, fee or deadline.

Evidence: three test cases run through `src/llm.py` (to be filled in once the module is merged).

| Case | Ticket | Expected | Answer | Anything missing from the ticket? |
|---|---|---|---|---|
| C02 | T027 | delivery | TODO | TODO |
| C05 | T012 | product | TODO | TODO |
| C08 | T040 | information | TODO | TODO |

Model, date, parameters, test file: TODO.

## Options considered

| Option | For | Against |
|---|---|---|
| No retrieval | Everything the label needs is in the ticket; no extra cost, no extra failure point | Cannot use facts outside the ticket |
| RAG over the help centre (6 PDFs) | Grounds answers in company policy | Routing needs no policy; adds an index, an embedding model and a second injection surface |
| Tool `get_order` (lesson 2, capped loop) | Uses the order and shipment data when the label depends on who shipped | More calls per ticket; only useful for delivery vs seller tickets |

## Criteria

- Does the label depend on information outside the ticket?
- Cost and latency per ticket.
- New ways to fail, including prompt injection.

## Decision

TODO after the three runs: no retrieval, if the three answers needed nothing outside the ticket.

## What would change our mind

A ticket whose right label depends on data outside it. "My parcel arrived incomplete" is `delivery` if the carrier lost an item and `seller` if the third-party seller packed it wrong: the answer is in the order and shipment table, not in the ticket. That calls for the `get_order` tool, not for retrieval over documents.

## Untrusted inputs and what stops them

Every ticket is written by someone outside the group, so the whole ticket is untrusted. What stops an injected instruction: the output schema only allows one of eight labels, so a promise such as "refund approved" has nowhere to go. What it does not stop: a wrong label. Measured on `evals/injection_cases.csv`, five runs per case: TODO.

## Consequences

TODO.
