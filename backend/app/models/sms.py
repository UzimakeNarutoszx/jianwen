"""Which purpose (register / reset / login) the last SMS code was issued for.

Codes are generated and validated by the SMS provider, so the only way to bind
a code to the flow that requested it is to remember the purpose ourselves.
Keeping it in the database (rather than process memory) means the binding also
works when more than one worker is serving requests.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SmsCodeIssue(Base):
    __tablename__ = "sms_code_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Indexed, not unique: issuing a new code replaces older rows for the phone.
    phone: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    # Naive local time, matching the other tables' timestamp convention.
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
