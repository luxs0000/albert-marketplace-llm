# The answers we accept from the model, and the rules they must follow.
# The JSON schema sent to the API is generated from these models (src/llm.py),
# so the labels are written in one place only.
#
# - Route: the routing answer (zero-shot and few-shot prompts)
# - RouteCoT: the same answer with the reasoning written FIRST (chain-of-thought prompt, L04).
#   A token, once written, cannot be taken back (lesson 1, section 3): if the label came
#   first, the reasoning would only justify it. So reasoning is the first field.
# - JudgeScore, JudgeChoice: what the judge returns (L04, src/evaluate.py, evals/rubric.md)

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Label = Literal["billing", "delivery", "returns_refunds", "account",
                "seller", "product", "information", "other"]
LABELS = list(Label.__args__)

LOW_CONFIDENCE = 0.7
MAX_REASONING_WORDS = 120


def check_route_rules(answer):
    # The rules a JSON schema cannot express, shared by Route and RouteCoT
    # Below 0.7 the model must say what else it hesitated with
    if answer.confidence < LOW_CONFIDENCE and answer.second_label is None:
        raise ValueError(f"confidence {answer.confidence} is below {LOW_CONFIDENCE}: give a second_label")
    if answer.second_label == answer.label:
        raise ValueError("second_label must differ from label")
    return answer


class Route(BaseModel):
    label: Label
    confidence: float = Field(ge=0, le=1)
    second_label: Optional[Label] = None

    @model_validator(mode="after")
    def check_second_label(self):
        return check_route_rules(self)


class RouteCoT(BaseModel):
    reasoning: str
    label: Label
    confidence: float = Field(ge=0, le=1)
    second_label: Optional[Label] = None

    @model_validator(mode="after")
    def check_rules(self):
        # Output tokens are the expensive part: a reasoning that runs on is rejected
        if len(self.reasoning.split()) > MAX_REASONING_WORDS:
            raise ValueError(f"reasoning is longer than {MAX_REASONING_WORDS} words: "
                             "keep it to three short sentences")
        return check_route_rules(self)


# --- The judge (L04) -------------------------------------------------------------
# One score per criterion of evals/rubric.md, then the overall score. The reason comes
# first, for the same reason as RouteCoT: the scores are written after it.

class JudgeScore(BaseModel):
    reason: str
    correct_label: int = Field(ge=1, le=5)
    second_label: int = Field(ge=1, le=5)
    confidence: int = Field(ge=1, le=5)
    format_and_grounding: int = Field(ge=1, le=5)
    score: int = Field(ge=1, le=5)


class JudgeChoice(BaseModel):
    reason: str
    better: Literal["A", "B"]
