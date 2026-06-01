from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[JobStatus] = mapped_column(SqlEnum(JobStatus), default=JobStatus.queued)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    result: Mapped["JobResult | None"] = relationship(
        "JobResult",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )


class JobResult(Base):
    __tablename__ = "job_results"

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), primary_key=True)
    summary_json: Mapped[str] = mapped_column(Text)

    job: Mapped[Job] = relationship("Job", back_populates="result")
