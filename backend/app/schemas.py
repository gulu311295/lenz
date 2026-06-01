from datetime import datetime
from typing import Literal

from pydantic import BaseModel


OverallSentiment = Literal["positive", "neutral", "mixed", "negative"]


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ThemeItem(BaseModel):
    theme: str
    evidence_feedback_ids: list[str]


class SentimentResult(BaseModel):
    short_summary: str
    overall_sentiment: OverallSentiment
    top_themes: list[ThemeItem]
    recommended_actions: list[str]
    uncertainty_note: str


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    result: SentimentResult
