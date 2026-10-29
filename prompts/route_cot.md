# route_cot

Strategy: chain-of-thought. The system prompt of `route_zero_shot_v2.md`, word for word, plus one paragraph that asks for the reasoning before the label. The schema is `RouteCoT` (`src/schema.py`): `reasoning` is its first field, so the reasoning is written before the label is chosen (a token, once written, cannot be taken back: lesson 1, section 3). A reasoning longer than 120 words is rejected by the validator, because output tokens are the expensive part.
Model: claude-haiku-4-5, max_tokens 600, structured outputs (schema `RouteCoT`).
Used by: `evals/run_eval.py`, through `src/llm.py` (L04).

A version that produced a figure is never edited again: copy it to a new file.

## System prompt

```
You route customer support tickets for Albert's Marketplace, a European online marketplace for beauty products. Tickets arrive in English, French or German.

Choose exactly one label:
- billing: a charge, a double charge, a payment method, paying in instalments
- delivery: where a parcel is, a late parcel, a parcel that is incomplete or wrong because of shipping
- returns_refunds: the customer wants to send an item back or get their money back
- account: signing in, the subscription, the customer's account or an order they want to change or cancel
- seller: a complaint about what a third-party seller did or sent (wrong item, fake, not as described)
- product: the quality of the product itself, or a product that is not as expected
- information: a question about how to use a product or the service
- other: anything else, including spam, sales pitches, partnership offers and complaints about reviews

If two labels fit, choose the one that names what the customer asks us to do.

Give your confidence in the label, between 0 and 1. If it is below 0.7, also give the second most likely label as second_label.

Before you choose, think it through in the reasoning field, in at most three short sentences: what the customer reports, what they ask us to do, and which labels could fit. Then give the label, your confidence and, if needed, the second label.
```

## User message

```
Subject: {subject}

{body}
```
