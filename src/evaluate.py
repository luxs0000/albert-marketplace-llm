# The instruments of the evaluation (L04): scores, the judge, the swap, cost and latency.
#
# - A score that needs no model: exact match on the label, after normalise_label().
#   Tested on pairs whose answer we know: tests/test_evaluate.py.
# - A judge from another model (JUDGE, Claude Sonnet 5.5; the component runs on
#   Claude Haiku 4.5), scoring the four criteria of evals/rubric.md, as a JudgeScore record.
# - The swap: a pair of answers judged in both orders; a preference counts only when it
#   survives (lesson 4, section 3).
# - The cost of every call, input and output tokens at their own prices, and its latency.
#
# Every call to a model goes through src/llm.py, which logs it in runs/calls.csv.
# evals/run_eval.py runs the strategies and writes the results in runs/eval/.
#
# Calibration of the judge against our own scores:  python -m src.evaluate calibrate

import csv
import json
import re
import statistics
import sys
from pathlib import Path

# Prices in $ per million tokens, input and output: Anthropic's pricing as quoted in
# lesson 4, section 4 (14 October 2026). Our keys go through OpenRouter, which charges
# the provider's price for these models; check runs against the OpenRouter activity page.
PRICE = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}
JUDGE = "claude-sonnet-5-5"
JUDGE_MAX_TOKENS = 2000      # Sonnet 5.5 may think before it answers, and thinking is billed as output
JUDGE_PROMPT = Path("prompts/judge.md")
RIGHT_SCORE = 4              # "right by the judge" = an overall score of 4 or 5 (evals/rubric.md)
HUMAN_SCORES = Path("evals/human_scores.csv")


# --- 1. The score without a model: exact match on the label ------------------------

def normalise_label(text):
    # "Returns refunds", " returns-refunds ", "RETURNS_REFUNDS" -> "returns_refunds"; None -> ""
    if text is None:
        return ""
    text = str(text).strip().lower()
    text = re.sub(r"[\s\-/]+", "_", text)
    return text.strip("_")


def exact_match(predicted, expected, second_acceptable=""):
    # Returns (strict, either): the main label only, or the main label or the second acceptable one.
    # An empty prediction (the call gave up) is never right, even when second_acceptable is empty.
    p = normalise_label(predicted)
    if not p:
        return False, False
    strict = p == normalise_label(expected)
    either = strict or (p == normalise_label(second_acceptable))
    return strict, either


# --- 2. Cost and latency ---------------------------------------------------------------

def cost(model, input_tokens, output_tokens):
    # Input tokens at the input price PLUS output tokens at the output price, per million
    p_in, p_out = PRICE[model]
    return (input_tokens * p_in + output_tokens * p_out) / 1e6


def calls_cost(calls):
    # The cost of a list of logged calls (src/llm.py), each at its own model's price
    return sum(cost(c["model"], c["input_tokens"], c["output_tokens"]) for c in calls)


def percentile(values, p):
    # Nearest-rank percentile: the smallest value with at least p% of the values at or below it
    values = sorted(values)
    if not values:
        return float("nan")
    rank = max(1, -(-len(values) * p // 100))     # ceil(n * p / 100), at least 1
    return values[int(rank) - 1]


def latency_summary(ms):
    return {"median_s": statistics.median(ms) / 1000, "p90_s": percentile(ms, 90) / 1000}


def pareto_front(variants, keys=(("right", "max"), ("usd_per_1000", "min"), ("median_s", "min"))):
    # A variant is on the front if no other is at least as good on every axis and better on one
    def at_least_as_good(a, b):
        return all((a[k] >= b[k]) if d == "max" else (a[k] <= b[k]) for k, d in keys)

    def better_on_one(a, b):
        return any((a[k] > b[k]) if d == "max" else (a[k] < b[k]) for k, d in keys)

    front = []
    for v in variants:
        if not any(at_least_as_good(o, v) and better_on_one(o, v) for o in variants if o is not v):
            front.append(v["name"])
    return front


# --- 3. The judge, and the swap --------------------------------------------------------

def load_judge_prompts(path=JUDGE_PROMPT):
    # Four code blocks, in order: pointwise system, pointwise user, pairwise system, pairwise user
    blocks = Path(path).read_text(encoding="utf-8").split("```")
    return [blocks[i].strip() for i in (1, 3, 5, 7)]


def fill(template, **values):
    # str.replace rather than str.format: a ticket may contain braces
    for name, value in values.items():
        template = template.replace("{" + name + "}", str(value))
    return template


def answer_text(row):
    # The router's answer as the judge sees it: the record, as JSON, exactly as the model returned it
    return row["answer_json"] or "(no answer: the router gave up)"


def judge(ticket, case, answer, model=JUDGE):
    # One pointwise verdict: (JudgeScore or None, the logged calls)
    from src import llm
    from src.schema import JudgeScore
    system, user_t, _, _ = load_judge_prompts()
    user = fill(user_t, subject=ticket["subject"], body=ticket["body"], expected=case["expected"],
                second_acceptable=case["second_acceptable"] or "none", answer=answer)
    return llm.ask(system, user, schema=JudgeScore, model=model, max_tokens=JUDGE_MAX_TOKENS,
                   tag="judge", case_id=case["case_id"])


def judge_pair(ticket, case, a, b, model=JUDGE):
    # Which of two answers is better: ("A" or "B" or "" if the judge gave up, the logged calls)
    from src import llm
    from src.schema import JudgeChoice
    _, _, system, user_t = load_judge_prompts()
    user = fill(user_t, subject=ticket["subject"], body=ticket["body"], expected=case["expected"],
                second_acceptable=case["second_acceptable"] or "none", a=a, b=b)
    choice, calls = llm.ask(system, user, schema=JudgeChoice, model=model, max_tokens=JUDGE_MAX_TOKENS,
                            tag="judge_pair", case_id=case["case_id"])
    return (choice.better if choice else ""), calls


def swap_verdict(once, twice):
    # once: the verdict with `first` shown as A; twice: with `first` shown as B.
    # "first" or "second" when the same answer won both times; "position" when the same LETTER won
    # both times (the order decided, not the answers); "gave_up" if either verdict is missing.
    if not once or not twice:
        return "gave_up"
    if once == "A" and twice == "B":
        return "first"
    if once == "B" and twice == "A":
        return "second"
    return "position"


def swap(ticket, case, first, second, model=JUDGE):
    # The pair judged twice, once in each order: (verdict, the two letters, the logged calls)
    once, calls1 = judge_pair(ticket, case, first, second, model)
    twice, calls2 = judge_pair(ticket, case, second, first, model)
    return swap_verdict(once, twice), (once, twice), calls1 + calls2


def same_answer(row_a, row_b, tolerance=0.05):
    # Two answers that route the same way, with the same second label and nearly the same
    # confidence, are a tie: the judge has nothing to choose between (evals/rubric.md)
    if row_a["predicted"] != row_b["predicted"] or row_a["second_label"] != row_b["second_label"]:
        return False
    try:
        return abs(float(row_a["confidence"]) - float(row_b["confidence"])) <= tolerance
    except ValueError:
        return False


# --- 4. Calibration: the judge against our own scores ---------------------------------

def calibrate(judged_file, human_file=HUMAN_SCORES):
    # Compares the judge's overall score with each member's, on the cases scored by hand.
    # One row per member and case: two members can score the same ten (column scored_by).
    with open(human_file, encoding="utf-8") as f:
        human = [r for r in csv.DictReader(f) if r["score"].strip()]
    with open(judged_file, encoding="utf-8") as f:
        judged = {r["case_id"]: r for r in csv.DictReader(f)}
    rows = []
    for h in human:
        j = judged.get(h["case_id"])
        if not j or not j.get("judge_score"):
            continue
        hs, js = int(h["score"]), int(j["judge_score"])
        rows.append({"case_id": h["case_id"], "scored_by": h["scored_by"], "human": hs, "judge": js,
                     "same_score": hs == js,
                     "same_right": (hs >= RIGHT_SCORE) == (js >= RIGHT_SCORE), "gap": js - hs})
    return rows


def members_agreement(human_file=HUMAN_SCORES):
    # How often two members give the same score to the same answer: the ceiling for the judge
    with open(human_file, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["score"].strip()]
    by_case = {}
    for r in rows:
        by_case.setdefault(r["case_id"], {})[r["scored_by"]] = int(r["score"])
    pairs = [list(v.values())[:2] for v in by_case.values() if len(v) >= 2]
    return {"cases": len(pairs), "same_score": sum(a == b for a, b in pairs),
            "same_right": sum((a >= RIGHT_SCORE) == (b >= RIGHT_SCORE) for a, b in pairs)}


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "calibrate":
        if len(sys.argv) < 3:
            sys.exit("usage: python -m src.evaluate calibrate runs/eval/<judged results file>.csv")
        rows = calibrate(sys.argv[2])
        if not rows:
            sys.exit(f"no case scored in {HUMAN_SCORES} has a judge score in {sys.argv[2]}")
        for member in sorted({r["scored_by"] for r in rows}):
            mine = [r for r in rows if r["scored_by"] == member]
            for r in mine:
                print(f"{r['case_id']}: {member} {r['human']}, judge {r['judge']}"
                      + ("" if r["same_right"] else "   <-- disagree on right / not right"))
            print(f"{member}: same overall score {sum(r['same_score'] for r in mine)}/{len(mine)} "
                  f"| same right / not right {sum(r['same_right'] for r in mine)}/{len(mine)}\n")
        m = members_agreement()
        if m["cases"]:
            print(f"two members: same score {m['same_score']}/{m['cases']} "
                  f"| same right / not right {m['same_right']}/{m['cases']}")
        return
    sys.exit("usage: python -m src.evaluate calibrate runs/eval/<judged results file>.csv")


if __name__ == "__main__":
    main()
