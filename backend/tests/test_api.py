import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import worker
from app.database import Base, engine
from app.main import app
from app.models import JobStatus


client = TestClient(app)


def _fake_pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_valid_upload(monkeypatch):
    monkeypatch.setattr("app.main.submit_job", lambda job_id: None)
    response = client.post(
        "/jobs",
        files={"file": ("survey.pdf", _fake_pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == JobStatus.queued.value
    status_response = client.get(f"/jobs/{body['job_id']}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == JobStatus.queued.value


def test_invalid_input_non_pdf():
    response = client.post(
        "/jobs",
        files={"file": ("survey.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_job_lifecycle_with_mock_llm(monkeypatch):
    monkeypatch.setattr(
        "app.worker.extract_feedback_from_pdf",
        lambda content: [SimpleNamespace(feedback_id="fb_001", comment="Great support")],
    )
    monkeypatch.setattr(
        "app.worker.analyze_feedback",
        lambda payload: {
            "short_summary": "Mostly positive with onboarding friction.",
            "overall_sentiment": "mixed",
            "top_themes": [
                {"theme": "support", "evidence_feedback_ids": ["fb_001"]},
                {"theme": "onboarding", "evidence_feedback_ids": ["fb_001"]},
                {"theme": "pricing", "evidence_feedback_ids": ["fb_001"]},
            ],
            "recommended_actions": ["Improve onboarding copy", "Keep support SLA"],
            "uncertainty_note": "Small sample size.",
        },
    )
    monkeypatch.setattr("app.main.submit_job", lambda job_id: worker.process_job(job_id))

    create = client.post("/jobs", files={"file": ("survey.pdf", _fake_pdf(), "application/pdf")})
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    status = client.get(f"/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == JobStatus.completed.value

    result = client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    assert result.json()["result"]["overall_sentiment"] == "mixed"


def test_mock_llm_success(monkeypatch):
    monkeypatch.setattr(
        "app.worker.extract_feedback_from_pdf",
        lambda content: [SimpleNamespace(feedback_id="fb_001", comment="Fast support and smooth setup")],
    )
    monkeypatch.setattr(
        "app.worker.analyze_feedback",
        lambda payload: {
            "short_summary": "Positive early experience.",
            "overall_sentiment": "positive",
            "top_themes": [
                {"theme": "support", "evidence_feedback_ids": ["fb_001"]},
                {"theme": "onboarding", "evidence_feedback_ids": ["fb_001"]},
                {"theme": "value", "evidence_feedback_ids": ["fb_001"]},
            ],
            "recommended_actions": ["Keep support quality high", "Preserve onboarding simplicity"],
            "uncertainty_note": "Single mocked response.",
        },
    )
    monkeypatch.setattr("app.main.submit_job", lambda job_id: worker.process_job(job_id))

    create = client.post("/jobs", files={"file": ("survey.pdf", _fake_pdf(), "application/pdf")})
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == JobStatus.completed.value

    result = client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    payload = result.json()["result"]
    assert payload["overall_sentiment"] == "positive"
    assert payload["short_summary"] == "Positive early experience."


def test_multiple_jobs_keep_separate_results(monkeypatch):
    monkeypatch.setattr(
        "app.worker.extract_feedback_from_pdf",
        lambda content: [SimpleNamespace(feedback_id="fb_001", comment="Great support")],
    )

    def fake_analyze(payload):
        fb_id = payload[0]["feedback_id"]
        return {
            "short_summary": f"Summary for {fb_id}",
            "overall_sentiment": "positive",
            "top_themes": [
                {"theme": "theme-a", "evidence_feedback_ids": [fb_id]},
                {"theme": "theme-b", "evidence_feedback_ids": [fb_id]},
                {"theme": "theme-c", "evidence_feedback_ids": [fb_id]},
            ],
            "recommended_actions": ["Action 1", "Action 2"],
            "uncertainty_note": "None.",
        }

    monkeypatch.setattr("app.worker.analyze_feedback", fake_analyze)
    monkeypatch.setattr("app.main.submit_job", lambda job_id: worker.process_job(job_id))

    job_ids = []
    for _ in range(3):
        create = client.post("/jobs", files={"file": ("survey.pdf", _fake_pdf(), "application/pdf")})
        assert create.status_code == 200
        job_ids.append(create.json()["job_id"])

    assert len(set(job_ids)) == 3
    results = [client.get(f"/jobs/{job_id}/result").json() for job_id in job_ids]
    assert all(r["status"] == JobStatus.completed.value for r in results)
    assert all("Summary for fb_001" in json.dumps(r) for r in results)


def test_mock_llm_failure(monkeypatch):
    monkeypatch.setattr(
        "app.worker.extract_feedback_from_pdf",
        lambda content: [SimpleNamespace(feedback_id="fb_001", comment="Great support")],
    )
    monkeypatch.setattr("app.worker.analyze_feedback", lambda payload: (_ for _ in ()).throw(RuntimeError("LLM failed")))
    monkeypatch.setattr("app.main.submit_job", lambda job_id: worker.process_job(job_id))

    create = client.post("/jobs", files={"file": ("survey.pdf", _fake_pdf(), "application/pdf")})
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == JobStatus.failed.value
    assert "LLM failed" in (status["error_message"] or "")
