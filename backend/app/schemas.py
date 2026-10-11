from typing import Literal

from pydantic import BaseModel, Field, field_validator


class QuestionOut(BaseModel):
    id: str
    position: int
    text: str
    topic: str | None = None
    difficulty: str | None = None
    key_points: list[str] = []
    accepted: bool = False


class GenerateRequest(BaseModel):
    n: int = Field(default=3, ge=2, le=4)


class QuestionPatch(BaseModel):
    text: str | None = Field(default=None, min_length=5, max_length=400)
    accepted: bool | None = None
    position: int | None = Field(default=None, ge=0, le=50)


class SessionCreate(BaseModel):
    document_id: str
    question_ids: list[str] = Field(min_length=2, max_length=4)


# ---- LLM outputs ----
class GeneratedQuestion(BaseModel):
    question: str
    topic: str = ""
    difficulty: Literal["basic", "medium", "hard"] = "medium"
    key_points: list[str] = Field(min_length=1, max_length=6)
    source_chunk_ids: list[str] = []

    @field_validator("question")
    @classmethod
    def _q(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 8:
            raise ValueError("question too short")
        return v


class GeneratedQuestions(BaseModel):
    questions: list[GeneratedQuestion]


class Verdict(BaseModel):
    verdict: Literal["clear", "vague", "repeat_request"]
    followup: str | None = None
    reason: str = ""


class Scores(BaseModel):
    accuracy: int = Field(ge=0, le=5)
    completeness: int = Field(ge=0, le=5)
    clarity: int = Field(ge=0, le=5)
    justification: int = Field(ge=0, le=5)


class QuestionEval(BaseModel):
    scores: Scores
    covered_points: list[str] = []
    missed_points: list[str] = []
    incorrect_claims: list[str] = []
    feedback: str = ""
    model_answer: str = ""


class SummaryOut(BaseModel):
    strengths: list[str] = []
    gaps: list[str] = []
    practice_next: list[str] = []
    overall_comment: str = ""
