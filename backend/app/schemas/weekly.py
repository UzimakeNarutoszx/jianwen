from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReadingActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: str = Field(min_length=1, max_length=64)
    kind: Literal["article", "classic"]
    content_id: str = Field(min_length=1, max_length=64)
    book_id: str | None = Field(default=None, max_length=64)
    scroll_progress: int = Field(default=0, ge=0, le=100)
    started_at: datetime
    ended_at: datetime

    @model_validator(mode="after")
    def valid_interval(self):
        if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
            raise ValueError("阅读时间必须包含时区")
        seconds = (self.ended_at - self.started_at).total_seconds()
        if not 0 < seconds <= 16:
            raise ValueError("每批阅读时间必须在 0–16 秒之间")
        if self.kind == "classic" and not self.book_id:
            raise ValueError("名著阅读必须指定书籍")
        return self
