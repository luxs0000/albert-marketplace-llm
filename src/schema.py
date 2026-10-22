# The answer we accept from the model, and the rules it must follow.
# The JSON schema sent to the API is generated from this model (src/llm.py),
# so the labels are written in one place only.

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Label = Literal["billing", "delivery", "returns_refunds", "account",
                "seller", "product", "information", "other"]

LOW_CONFIDENCE = 0.7


class Route(BaseModel):
    label: Label
    confidence: float = Field(ge=0, le=1)
    second_label: Optional[Label] = None

    @model_validator(mode="after")
    def check_second_label(self):
        # Below 0.7 the model must say what else it hesitated with
        if self.confidence < LOW_CONFIDENCE and self.second_label is None:
            raise ValueError(f"confidence {self.confidence} is below {LOW_CONFIDENCE}: give a second_label")
        if self.second_label == self.label:
            raise ValueError("second_label must differ from label")
        return self
