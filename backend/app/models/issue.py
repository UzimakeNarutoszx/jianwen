from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentIssue(Base):
    __tablename__ = "content_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status_line: Mapped[str] = mapped_column(Text, default="", nullable=False)
    stage: Mapped[str] = mapped_column(String(32), default="ongoing", nullable=False)
    category: Mapped[str | None] = mapped_column(String(64))
    first_date: Mapped[date | None] = mapped_column(Date)
    last_date: Mapped[date | None] = mapped_column(Date, index=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    merged_into: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ContentIssueEvent(Base):
    __tablename__ = "content_issue_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("content_issues.id"), index=True, nullable=False)
    # One article has one primary issue, including while that issue is hidden.
    article_id: Mapped[str] = mapped_column(ForeignKey("content_articles.article_id"), unique=True, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    delta_summary: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # True when this historical article was published into an issue after its event date.
    historical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class UserIssueFollow(Base):
    __tablename__ = "user_issue_follows"
    __table_args__ = (UniqueConstraint("user_id", "issue_id", name="uq_user_issue_follow"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    issue_id: Mapped[int] = mapped_column(ForeignKey("content_issues.id"), nullable=False)
    last_seen_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class IssueCandidateJob(Base):
    __tablename__ = "issue_candidate_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    content_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    article_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(Text)


class IssueCandidate(Base):
    __tablename__ = "issue_candidates"
    __table_args__ = (UniqueConstraint("job_id", "article_id", name="uq_issue_candidate_article"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("issue_candidate_jobs.id"), nullable=False)
    article_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    base_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(160))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class IssueRevision(Base):
    __tablename__ = "issue_revisions"
    __table_args__ = (UniqueConstraint("issue_id", "version", name="uq_issue_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("content_issues.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)
