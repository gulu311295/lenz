import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


@dataclass
class FeedbackEntry:
    feedback_id: str
    comment: str


ENTRY_PATTERN = re.compile(
    r"Feedback ID:\s*(?P<id>[A-Za-z0-9_-]+)\s*[\r\n]+Comment:\s*(?P<comment>.+?)(?=(?:[\r\n]+Feedback ID:)|\Z)",
    re.DOTALL,
)


def extract_feedback_from_pdf(content: bytes) -> list[FeedbackEntry]:
    reader = PdfReader(BytesIO(content))
    text_parts: list[str] = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    full_text = "\n".join(text_parts).strip()
    if not full_text:
        raise ValueError("The uploaded PDF appears to be empty.")

    matches = ENTRY_PATTERN.finditer(full_text)
    entries: list[FeedbackEntry] = []
    for match in matches:
        feedback_id = match.group("id").strip()
        comment = " ".join(match.group("comment").split())
        if feedback_id and comment:
            entries.append(FeedbackEntry(feedback_id=feedback_id, comment=comment))

    if not entries:
        raise ValueError("Could not find any valid `Feedback ID` and `Comment` pairs.")
    if len(entries) > 50:
        raise ValueError("The file contains more than 50 feedback responses.")
    return entries
