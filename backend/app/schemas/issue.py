from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

IssueStage = Literal["consulting", "published", "implementing", "ended", "ongoing"]


class IssueBriefResponse(BaseModel):
    issue_key: str
    title: str
    stage: IssueStage
    status_line: str
    event_count: int
    published_version: int
    position: int | None = None
    prev_delta: str | None = None


class IssueEventResponse(BaseModel):
    event_id: int
    article_id: str
    event_date: date
    delta_summary: str
    position: int
    updated_version: int
    historical: bool = False
    references: list[dict] = Field(default_factory=list)


class IssueDetailResponse(IssueBriefResponse):
    events: list[IssueEventResponse] = Field(default_factory=list)
    is_following: bool = False
    last_seen_version: int | None = None
    policy_checks: list[dict] = Field(default_factory=list)


class IssueUpdateItem(BaseModel):
    issue: IssueBriefResponse
    new_events: int
    events: list[IssueEventResponse] = Field(default_factory=list)


class IssueSeenRequest(BaseModel):
    published_version: int = Field(ge=0)
