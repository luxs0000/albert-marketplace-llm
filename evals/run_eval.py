# Project step 4: the three prompt strategies on the 30 test cases, the judge, the swap,
# and the table of docs/evaluation.md. Every call goes through src/llm.py (logged in
# runs/calls.csv); every result is written to runs/eval/, one file per run, with each case's
# tokens, cost and latency, so every figure in the report can be traced to a file.
#
# Usage, from the repository root, virtual environment active:
#   python evals/run_eval.py run zero_shot          # one strategy on the 30 cases (about 2 min)
#   python evals/run_eval.py run few_shot
#   python evals/run_eval.py run cot
#   python evals/run_eval.py run zero_shot --model claude-haiku-5-5    # the same prompt, another model
#   python evals/run_eval.py judge                  # the judge on the latest run of each variant
#   python evals/run_eval.py swap zero_shot cot     # pairs judged in both orders
#   python evals/run_eval.py sheet                  # evals/human_scores.csv, to score 10 cases by hand
#   python evals/run_eval.py report                 # the table, the front, the failures to read
#   python evals/run_eval.py all                    # run x3, judge, swap and report, in that order
#
# Cost of `all`, measured on the L02 run's tokens: about $0.10 for the router, about $0.60
# for the judge (Sonnet 5.5, 90 scores and up to 60 pairwise verdicts). Under a dollar.

import argparse
import csv
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import evaluate, llm  # noqa: E402
from src.schema import Route, RouteCoT  # noqa: E402
from evals.run_prompt import load_tickets, load_prompt, PAUSE, TEST_FILE  # noqa: E402

OUT_DIR = Path("runs/eval")
STRATEGIES = {
    # name: (prompt file, schema, max_tokens)
    "zero_shot": ("prompts/route_zero_shot_v2.md", Route, 200),
    "few_shot": ("prompts/route_few_shot.md", Route, 200),
    "cot": ("prompts/route_cot.md", RouteCoT, 600),
}
# Haiku 5.5 thinks before it answers by default, and thinking counts against max_tokens:
# a model that thinks gets more room, or its answer is cut (stop_reason max_tokens).
THINKING_MODELS = {"claude-haiku-5-5": 2000, "claude-sonnet-5-5": 2000}
CALIBRATION_CASES = ["C03", "C05", "C08", "C11", "C15", "C17", "C21", "C24", "C27", "C30"]

FIELDS = ["case_id", "ticket_id", "language", "expected", "second_acceptable", "predicted",
          "confidence", "second_label", "reasoning", "strict_ok", "either_ok", "calls",
          "input_tokens", "output_tokens", "cost_usd", "latency_ms", "answer_json"]


def load_cases():
    with open(TEST_FILE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def variant_name(strategy, model):
    return f"{strategy}" if model == llm.MODEL else f"{strategy}@{model}"


def out_file(kind, name):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR / f"{datetime.datetime.now():%Y-%m-%d_%H%M%S}_{kind}_{name.replace('@', '_')}.csv"


def latest(kind, name):
    # The most recent file of this kind for this variant (file names start with the date and time)
    files = sorted(OUT_DIR.glob(f"*_{kind}_{name.replace('@', '_')}.csv"))
    return files[-1] if files else None


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def stop_on_key_error(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (llm.anthropic.AuthenticationError, llm.anthropic.PermissionDeniedError) as e:
        sys.exit(f"The API refused the key ({e.status_code}): check the key in .env")


# --- run: one strategy on the 30 cases ------------------------------------------------

def run(strategy, model):
    prompt_file, schema, max_tokens = STRATEGIES[strategy]
    max_tokens = max(max_tokens, THINKING_MODELS.get(model, 0))
    name = variant_name(strategy, model)
    tickets = load_tickets()
    system, user_template = load_prompt(prompt_file)
    rows = []
    for i, case in enumerate(load_cases()):
        if i:
            time.sleep(PAUSE)
        ticket = tickets[case["input"]]
        user = user_template.replace("{subject}", ticket["subject"]).replace("{body}", ticket["body"])
        answer, calls = stop_on_key_error(llm.ask, system, user, schema=schema, model=model,
                                          max_tokens=max_tokens, tag=f"eval_{name}",
                                          case_id=case["case_id"])
        predicted = answer.label if answer else ""
        strict, either = evaluate.exact_match(predicted, case["expected"], case["second_acceptable"])
        row = {"case_id": case["case_id"], "ticket_id": case["input"], "language": ticket["language"],
               "expected": case["expected"], "second_acceptable": case["second_acceptable"],
               "predicted": predicted,
               "confidence": answer.confidence if answer else "",
               "second_label": (answer.second_label or "") if answer else "",
               "reasoning": getattr(answer, "reasoning", "") if answer else "",
               "strict_ok": strict, "either_ok": either, "calls": len(calls),
               "input_tokens": sum(c["input_tokens"] for c in calls),
               "output_tokens": sum(c["output_tokens"] for c in calls),
               "cost_usd": round(evaluate.calls_cost(calls), 6),
               # the customer waits for every attempt, re-prompts included
               "latency_ms": sum(c["latency_ms"] for c in calls),
               "answer_json": answer.model_dump_json() if answer else ""}
        rows.append(row)
        print(case["case_id"], case["input"], "expected:", case["expected"], "| got:", predicted or "(gave up)",
              "" if either else "  <-- error")
    path = out_file("run", name)
    write(path, rows, FIELDS)
    n = len(rows)
    print(f"\n{name}: prompt {prompt_file} | model {model} | max_tokens {max_tokens} "
          f"| {datetime.date.today()} | test file {TEST_FILE}")
    print(f"right (either label): {sum(r['either_ok'] for r in rows)}/{n} "
          f"| right (main label): {sum(r['strict_ok'] for r in rows)}/{n} "
          f"| per 1,000 calls: ${sum(r['cost_usd'] for r in rows) / n * 1000:.2f}")
    print(f"saved: {path}")
    return path


# --- judge: the pointwise judge on a run file -----------------------------------------

def judge_file(path):
    tickets = load_tickets()
    cases = {c["case_id"]: c for c in load_cases()}
    rows = read(path)
    out = []
    for i, row in enumerate(rows):
        if i:
            time.sleep(PAUSE)
        case = cases[row["case_id"]]
        verdict, calls = stop_on_key_error(evaluate.judge, tickets[row["ticket_id"]], case,
                                           evaluate.answer_text(row))
        row.update({"judge_score": verdict.score if verdict else "",
                    "judge_correct_label": verdict.correct_label if verdict else "",
                    "judge_second_label": verdict.second_label if verdict else "",
                    "judge_confidence": verdict.confidence if verdict else "",
                    "judge_format_and_grounding": verdict.format_and_grounding if verdict else "",
                    "judge_reason": verdict.reason if verdict else "",
                    "judge_right": (verdict.score >= evaluate.RIGHT_SCORE) if verdict else "",
                    "judge_cost_usd": round(evaluate.calls_cost(calls), 6),
                    "judge_latency_ms": sum(c["latency_ms"] for c in calls)})
        out.append(row)
        print(row["case_id"], "judge:", row["judge_score"] or "(gave up)")
    target = Path(str(path).replace("_run_", "_judged_"))
    write(target, out, list(out[0].keys()))
    print(f"saved: {target}")
    return target


# --- swap: two variants compared pair by pair, in both orders -------------------------

def swap_files(name_a, name_b):
    tickets = load_tickets()
    cases = {c["case_id"]: c for c in load_cases()}
    a_rows = {r["case_id"]: r for r in read(latest("run", name_a))}
    b_rows = {r["case_id"]: r for r in read(latest("run", name_b))}
    out = []
    first_call = True
    for case_id, a in a_rows.items():
        b = b_rows[case_id]
        row = {"case_id": case_id, "a": name_a, "b": name_b, "a_label": a["predicted"], "b_label": b["predicted"],
               "expected": a["expected"], "second_acceptable": a["second_acceptable"]}
        if evaluate.same_answer(a, b):
            row.update({"verdict": "tie", "letters": "", "judge_cost_usd": 0.0})
        else:
            if not first_call:
                time.sleep(PAUSE)
            first_call = False
            verdict, letters, calls = stop_on_key_error(evaluate.swap, tickets[a["ticket_id"]], cases[case_id],
                                                        evaluate.answer_text(a), evaluate.answer_text(b))
            row.update({"verdict": {"first": name_a, "second": name_b}.get(verdict, verdict),
                        "letters": "".join(letters), "judge_cost_usd": round(evaluate.calls_cost(calls), 6)})
        out.append(row)
        print(case_id, row["a_label"], "vs", row["b_label"], "->", row["verdict"])
    path = out_file("swap", f"{name_a}_vs_{name_b}")
    write(path, out, list(out[0].keys()))
    judged = [r for r in out if r["verdict"] != "tie"]
    print(f"\npairs judged: {len(judged)} | changed with the order: "
          f"{sum(r['verdict'] == 'position' for r in judged)} | saved: {path}")
    return path


# --- sheet: the calibration sheet, scored by hand --------------------------------------

def sheet(name="zero_shot"):
    if evaluate.HUMAN_SCORES.exists():
        sys.exit(f"{evaluate.HUMAN_SCORES} exists already: not overwritten")
    rows = {r["case_id"]: r for r in read(latest("run", name))}
    out = [{"case_id": c, "ticket_id": rows[c]["ticket_id"], "variant": name,
            "answer_json": rows[c]["answer_json"], "scored_by": "",
            "correct_label": "", "second_label": "", "confidence": "", "format_and_grounding": "",
            "score": "", "note": ""} for c in CALIBRATION_CASES]
    write(evaluate.HUMAN_SCORES, out, list(out[0].keys()))
    print(f"written: {evaluate.HUMAN_SCORES}. Score the ten answers with evals/rubric.md, "
          "WITHOUT looking at the judge's scores, then run: python evals/run_eval.py report")


# --- report: the table of docs/evaluation.md -------------------------------------------

def summarise(name):
    path = latest("judged", name) or latest("run", name)
    rows = read(path)
    n = len(rows)
    judged = [r for r in rows if r.get("judge_score")]
    usd = sum(float(r["cost_usd"]) for r in rows)
    lat = evaluate.latency_summary([int(r["latency_ms"]) for r in rows])
    return {"name": name, "file": str(path), "n": n,
            "right": sum(r["either_ok"] == "True" for r in rows),
            "strict": sum(r["strict_ok"] == "True" for r in rows),
            "judge_right": sum(r["judge_right"] == "True" for r in judged) if judged else None,
            "judged": len(judged),
            "gave_up": sum(r["predicted"] == "" for r in rows),
            "reprompts": sum(int(r["calls"]) - 1 for r in rows),
            "in_per_call": sum(int(r["input_tokens"]) for r in rows) / n,
            "out_per_call": sum(int(r["output_tokens"]) for r in rows) / n,
            "usd_per_1000": usd / n * 1000,
            "judge_usd_per_1000": (sum(float(r["judge_cost_usd"]) for r in judged) / len(judged) * 1000
                                   if judged else None),
            **lat, "rows": rows}


def report():
    names = sorted({p.name.split("_run_", 1)[1][:-4] for p in OUT_DIR.glob("*_run_*.csv")})
    if not names:
        sys.exit("no run yet: python evals/run_eval.py run zero_shot")
    variants = [summarise(n) for n in names]
    front = evaluate.pareto_front(variants)
    lines = [f"Report of {datetime.date.today()}, test file {TEST_FILE} ({variants[0]['n']} cases).", "",
             "| Variant | Right, either label (exact match) | Main label only | Right by the judge (score 4-5) "
             "| Gave up / re-prompts | Tokens per call, in / out | Per 1,000 calls | Judge per 1,000 "
             "| Median | p90 | Pareto |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for v in variants:
        jr = f"{v['judge_right']}/{v['judged']}" if v["judge_right"] is not None else "not judged"
        ju = f"${v['judge_usd_per_1000']:.2f}" if v["judge_usd_per_1000"] is not None else ""
        lines.append(f"| {v['name']} | {v['right']}/{v['n']} | {v['strict']}/{v['n']} | {jr} "
                     f"| {v['gave_up']} / {v['reprompts']} | {v['in_per_call']:.0f} / {v['out_per_call']:.0f} "
                     f"| ${v['usd_per_1000']:.2f} | {ju} | {v['median_s']:.1f} s | {v['p90_s']:.1f} s "
                     f"| {'on the front' if v['name'] in front else 'dominated'} |")
    lines += ["", "Files: " + "; ".join(f"`{v['file']}`" for v in variants), "",
              f"Pareto front (right answers, cost, median latency): {', '.join(front)}.",
              f"One case of {variants[0]['n']} is {100 / variants[0]['n']:.1f} points."]

    swaps = sorted(OUT_DIR.glob("*_swap_*.csv"))
    if swaps:
        s = read(swaps[-1])
        judged = [r for r in s if r["verdict"] != "tie"]
        counts = {k: sum(r["verdict"] == k for r in judged) for k in {r["verdict"] for r in judged}}
        lines += ["", f"Swap ({swaps[-1].name}): {len(judged)} pairs judged in both orders, "
                      f"{len(s) - len(judged)} ties not judged; verdicts: {counts}."]

    if evaluate.HUMAN_SCORES.exists():
        hs = read(evaluate.HUMAN_SCORES)
        name = hs[0]["variant"]
        jf = latest("judged", name)
        rows = evaluate.calibrate(jf) if jf else []
        if rows:
            lines += ["", f"Calibration on {len(rows)} cases scored by hand ({name}): same overall score "
                          f"{sum(r['same_score'] for r in rows)}/{len(rows)}, same right / not right "
                          f"{sum(r['same_right'] for r in rows)}/{len(rows)}."]

    lines += ["", "Every case one variant got wrong (either label), to be read by a person and grouped by cause:", ""]
    for v in variants:
        for r in v["rows"]:
            if r["either_ok"] != "True":
                lines.append(f"- {v['name']} {r['case_id']} ({r['ticket_id']}, {r['language']}): expected "
                             f"{r['expected']}{' / ' + r['second_acceptable'] if r['second_acceptable'] else ''}, "
                             f"got {r['predicted'] or '(gave up)'} ({r['confidence']}, second "
                             f"{r['second_label'] or 'none'})" + (f". Reasoning: {r['reasoning']}" if r["reasoning"] else ""))
    text = "\n".join(lines)
    print(text)
    path = OUT_DIR / f"{datetime.datetime.now():%Y-%m-%d_%H%M%S}_report.md"
    path.write_text(text + "\n", encoding="utf-8")
    print(f"\nsaved: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "judge", "swap", "sheet", "report", "all"])
    parser.add_argument("names", nargs="*")
    parser.add_argument("--model", default=llm.MODEL)
    args = parser.parse_args()

    if args.command == "run":
        for s in args.names or STRATEGIES:
            run(s, args.model)
    elif args.command == "judge":
        names = args.names or sorted({p.name.split("_run_", 1)[1][:-4] for p in OUT_DIR.glob("*_run_*.csv")})
        for name in names:
            judge_file(latest("run", name.replace("_claude", "@claude")) or latest("run", name))
    elif args.command == "swap":
        a, b = (args.names + ["zero_shot", "cot"])[:2] if len(args.names) < 2 else args.names[:2]
        swap_files(a, b)
    elif args.command == "sheet":
        sheet(*(args.names[:1] or ["zero_shot"]))
    elif args.command == "report":
        report()
    elif args.command == "all":
        for s in STRATEGIES:
            run(s, args.model)
        for s in STRATEGIES:
            judge_file(latest("run", variant_name(s, args.model)))
        swap_files(variant_name("zero_shot", args.model), variant_name("cot", args.model))
        report()


if __name__ == "__main__":
    main()
