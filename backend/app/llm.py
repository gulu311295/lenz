import json
import os
from typing import Any

from openai import OpenAI

from .schemas import SentimentResult


def analyze_feedback(feedback_payload: list[dict[str, str]]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are an analyst for consumer feedback. "
        "Return strict JSON only with keys: short_summary, overall_sentiment, top_themes, "
        "recommended_actions, uncertainty_note. "
        "overall_sentiment must be one of positive|neutral|mixed|negative. "
        "top_themes must be 3 to 7 items, each with: theme, evidence_feedback_ids (list of feedback IDs). "
        "recommended_actions should contain 2 to 5 concise actions."
    )

    user_prompt = (
        "Analyze the following customer feedback entries.\n"
        f"{json.dumps(feedback_payload, ensure_ascii=True)}\n"
        "Be concise and practical."
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = completion.choices[0].message.content or "{}"
    parsed = json.loads(raw)
    validated = SentimentResult.model_validate(parsed)
    return validated.model_dump()
