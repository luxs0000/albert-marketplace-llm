# The whole component, as the support desk would run it: a ticket in, the queue it is
# SENT to out. The output check below runs after the model, in code, so what is sent does not
# depend on the model resisting an attack (lesson 3, section 7; lesson 4, section 7).
#
# What the component sends is a Dispatch: a queue (one of the eight teams, or "triage", a
# person who routes by hand) and a reason. It never sends text written by the model or by
# the customer: the schema has no free-text field that could reach anyone.
#
# The output check:
#   1. no answer (the call gave up)                         -> triage
#   2. the ticket contains an instruction aimed at the router,
#      and the label is one that instruction names          -> triage, never the attacker's team
#   3. a confidence below 0.7 (LOW_CONFIDENCE)              -> triage: on the 30 zero-shot answers
#      of 2026-10-26 the two below 0.7 (C18, C24) are both wrong, and no right answer is below it
#   4. otherwise                                            -> the label's team
# Rule 2 comes before rule 3 because an attack can dictate the confidence too (INJ01 asks for 1.0).
# Rule 2 does not block a ticket that merely mentions a team: only a sentence that reads as an
# instruction to an AI or a routing system (INSTRUCTION_PATTERNS) and names a label as its
# target ("as billing", "en « other »", "go to information"). The patterns are a list we
# grew from our attacks: an attack they miss reaches the model, and the live tests are what
# show whether the model resists it.
#
# tests/test_guardrails.py runs the attacks through handle_ticket() and asserts on the Dispatch.

import re
from dataclasses import dataclass
from pathlib import Path

from src import llm
from src.schema import LABELS, LOW_CONFIDENCE, Route

PROMPT_FILE = Path("prompts/route_zero_shot_v2.md")   # the deployed prompt: see docs/evaluation.md
TRIAGE = "triage"

# Sentences that speak to the router rather than to the support team, in our three languages
INSTRUCTION_PATTERNS = [
    r"\b(ignore|disregard|forget)\b.{0,40}\b(instruction|rule|prompt|previous)",
    r"\b(AI|A\.I\.|LLM|chatbot|assistant|routing|router|model|system)\b.{0,60}\b(label|classify|route|tag|categori[sz]e|mark)\b",
    r"\b(label|classify|route|tag|categori[sz]e|mark)\b.{0,30}\b(this|it|the) (message|ticket|mail|email)\b",
    r"\b(routing|triage|dispatch)\s+(note|rule|instruction|policy)\b",
    r"\b(assistant IA|IA|intelligence artificielle|robot)\b.{0,60}\b(class|étiquet|rang|transf)",
    r"\b(ignore[zr]?|oublie[zr]?)\b.{0,40}\b(instruction|règle|consigne)",
    r"\b(KI|künstliche Intelligenz|Assistent|System)\b.{0,60}\b(einstuf|klassifizier|kategorisier|markier|weiterleit|label)",
    r"\b(ignorier|vergiss)\w*\b.{0,40}\b(Anweisung|Regel|Vorgabe)",
]


@dataclass
class Dispatch:
    queue: str
    label: str
    confidence: float
    reason: str


def load_prompt(path=PROMPT_FILE):
    blocks = Path(path).read_text(encoding="utf-8").split("```")
    return blocks[1].strip(), blocks[3].strip()


def labels_named_by_instructions(text):
    # The labels named in the sentences of the ticket that read as instructions to the router
    named = set()
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if any(re.search(p, sentence, flags=re.IGNORECASE) for p in INSTRUCTION_PATTERNS):
            for label in LABELS:
                # The label as the target of the instruction ("as billing", "en « other »",
                # "als billing", "to delivery") or in quotes: "my account" alone does not count
                target = rf"(\b(as|en|in|into|to|als|zu|unter|comme)\s+[\"'«„“]?\s*{label}\b|[\"'«„“]\s*{label}\s*[\"'»“”])"
                if re.search(target, sentence, flags=re.IGNORECASE):
                    named.add(label)
    return named


def has_instruction(text):
    return any(re.search(p, text, flags=re.IGNORECASE) for p in INSTRUCTION_PATTERNS)


def output_check(answer, subject, body):
    # What is sent, decided in code from the model's answer and the ticket
    text = f"{subject}\n{body}"
    if answer is None:
        return Dispatch(TRIAGE, "", 0.0, "no valid answer after the re-prompts")
    if answer.label in labels_named_by_instructions(text):
        return Dispatch(TRIAGE, answer.label, answer.confidence,
                        f"the ticket instructs the router to choose '{answer.label}': sent to a person")
    if answer.confidence < LOW_CONFIDENCE:
        return Dispatch(TRIAGE, answer.label, answer.confidence,
                        f"confidence {answer.confidence} is below {LOW_CONFIDENCE}: sent to a person")
    reason = "routed by the model"
    if has_instruction(text):
        reason += "; the ticket contains an instruction to the router, which the label does not follow"
    return Dispatch(answer.label, answer.label, answer.confidence, reason)


def handle_ticket(subject, body, route_fn=None, tag="component", case_id=""):
    # route_fn lets a test replace the model with a fake one, to test the check alone
    system, user_template = load_prompt()
    user = user_template.replace("{subject}", subject).replace("{body}", body)
    if route_fn is None:
        answer, _ = llm.ask(system, user, schema=Route, tag=tag, case_id=case_id)
    else:
        answer = route_fn(system, user)
    return output_check(answer, subject, body)
