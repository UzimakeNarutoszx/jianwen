from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicySource(StrictModel):
    id: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=1500)
    org: str = Field(min_length=1, max_length=120)
    published_at: date

    @field_validator("url")
    @classmethod
    def official_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".gov.cn") or parsed.username or parsed.password:
            raise ValueError("依据须使用 HTTPS 政府网站链接")
        return value


class PolicyOption(StrictModel):
    value: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=250)
    outcome: Literal["met", "not_met", "unknown"]
    reason: str = Field(min_length=1, max_length=1000)


class PolicyQuestion(StrictModel):
    id: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=250)
    help: str = Field(default="", max_length=2000)
    source_id: str
    options: list[PolicyOption] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def unique_options(self):
        if len({option.value for option in self.options}) != len(self.options):
            raise ValueError("选项值不能重复")
        if not any(option.outcome == "unknown" for option in self.options):
            raise ValueError("每题必须提供不确定选项")
        return self


class PolicyDocument(StrictModel):
    policy_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    title: str = Field(min_length=1, max_length=160)
    region: str = Field(min_length=1, max_length=80)
    version: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,39}$")
    summary: str = Field(min_length=1, max_length=2000)
    verified_at: date | None = None
    review_expires_at: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    reviewer: str = Field(default="", max_length=120)
    review_note: str = Field(default="", max_length=3000)
    sources: list[PolicySource] = Field(min_length=1, max_length=20)
    questions: list[PolicyQuestion] = Field(min_length=1, max_length=20)
    application_url: str
    materials: list[str] = Field(default_factory=list, max_length=20)
    next_steps: list[str] = Field(default_factory=list, max_length=20)
    article_ids: list[str] = Field(default_factory=list, max_length=100)
    issue_keys: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("application_url")
    @classmethod
    def application_is_official(cls, value):
        return PolicySource.official_url(value)

    @model_validator(mode="after")
    def valid_rules(self):
        ids = {item.id for item in self.sources}
        if len(ids) != len(self.sources) or len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("依据或问题 ID 重复")
        if any(q.source_id not in ids for q in self.questions):
            raise ValueError("问题必须关联已登记依据")
        if self.effective_until and self.effective_from and self.effective_until < self.effective_from:
            raise ValueError("政策有效区间错误")
        if self.verified_at and self.review_expires_at and self.review_expires_at < self.verified_at:
            raise ValueError("核验有效区间错误")
        return self


class PolicyEvaluateRequest(StrictModel):
    version: str = Field(min_length=1, max_length=40)
    answers: dict[str, str] = Field(default_factory=dict, max_length=20)

    @field_validator("answers")
    @classmethod
    def bounded_answers(cls, values):
        if any(len(k) > 60 or len(v) > 60 for k, v in values.items()):
            raise ValueError("答案标识过长")
        return values
