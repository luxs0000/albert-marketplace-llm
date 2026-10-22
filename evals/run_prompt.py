# Runs one prompt from prompts/ on the test cases in evals/test_cases.csv
# and prints the error rate with its four facts: model, date, parameters, test file.
#
# Usage:  python evals/run_prompt.py prompts/route_zero_shot.md

import csv
import datetime
import hashlib
import sys
import urllib.request
from pathlib import Path

import anthropic
from dotenv import load_dotenv

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 20
PRICE_IN = 1.00   # $ per million input tokens (Haiku 4.5)
PRICE_OUT = 5.00  # $ per million output tokens

LABELS = ["billing", "delivery", "returns_refunds", "account", "seller", "product", "information", "other"]

DATA_URL = ("https://github.com/TangoAI-AlbertSchool-Data-Eng-Cloud/albert-marketplace"
            "/releases/download/tickets-v1.0.0/tickets_v1.csv")
DATA_FILE = Path("data/tickets_v1.csv")
DATA_SHA256 = "df81753ed1bd30bf2af45821c63e4696373f5fcd223bba716973a9964f41018a"
TEST_FILE = Path("evals/test_cases.csv")


def load_tickets():
    # Download the tickets once, then check the file is the expected version
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(DATA_URL, DATA_FILE)
    checksum = hashlib.sha256(DATA_FILE.read_bytes()).hexdigest()
    if checksum != DATA_SHA256:
        sys.exit("data/tickets_v1.csv is not the expected version (checksum differs)")
    tickets = {}
    with open(DATA_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tickets[row["ticket_id"]] = row
    return tickets


def load_prompt(path):
    # The prompt file has two code blocks: the system prompt, then the user message
    text = Path(path).read_text(encoding="utf-8")
    blocks = text.split("```")
    system = blocks[1].strip()
    user_template = blocks[3].strip()
    return system, user_template


def find_label(answer):
    # The first known label in the answer, or "" if there is none
    answer = answer.strip().lower()
    for word in answer.replace(",", " ").replace(".", " ").split():
        if word in LABELS:
            return word
    return ""


def main():
    prompt_file = sys.argv[1] if len(sys.argv) > 1 else "prompts/route_zero_shot.md"
    load_dotenv()
    client = anthropic.Anthropic()
    tickets = load_tickets()
    system, user_template = load_prompt(prompt_file)

    with open(TEST_FILE, encoding="utf-8") as f:
        cases = list(csv.DictReader(f))

    rows = []
    strict_errors = 0
    either_errors = 0
    tokens_in = 0
    tokens_out = 0

    for case in cases:
        ticket = tickets[case["input"]]
        user = user_template.replace("{subject}", ticket["subject"]).replace("{body}", ticket["body"])
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        answer = response.content[0].text
        predicted = find_label(answer)
        tokens_in += response.usage.input_tokens
        tokens_out += response.usage.output_tokens

        strict_ok = predicted == case["expected"]
        either_ok = strict_ok or (predicted != "" and predicted == case["second_acceptable"])
        if not strict_ok:
            strict_errors += 1
        if not either_ok:
            either_errors += 1

        print(case["case_id"], case["input"], "expected:", case["expected"], "| got:", predicted,
              "" if either_ok else "  <-- error")
        rows.append({"case_id": case["case_id"], "ticket_id": case["input"],
                     "expected": case["expected"], "second_acceptable": case["second_acceptable"],
                     "predicted": predicted, "raw_answer": answer.strip(),
                     "strict_ok": strict_ok, "either_ok": either_ok})

    cost = tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT
    today = datetime.date.today().isoformat()
    n = len(cases)

    print()
    print(f"prompt: {prompt_file}")
    print(f"model: {MODEL} | date: {today} | max_tokens={MAX_TOKENS} | test file: {TEST_FILE}")
    print(f"strict errors: {strict_errors}/{n} ({strict_errors / n:.0%})")
    print(f"either-label errors: {either_errors}/{n} ({either_errors / n:.0%})")
    print(f"tokens: {tokens_in} in, {tokens_out} out | cost: ${cost:.4f} | per 1,000 tickets: ${cost / n * 1000:.2f}")

    # Keep the run: one file per run, so a figure can always be traced back
    out = Path("evals/runs") / f"{today}_{Path(prompt_file).stem}.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
