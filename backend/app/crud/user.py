from datetime import date

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.core.timeutil import today_cn
from app.models.profile import UserAiDailyUsage
from app.models.user import User


class PhoneAlreadyRegistered(Exception):
    """Raised when the phone number already belongs to an account."""


def get_user_by_phone(db: Session, phone: str) -> User | None:
    return db.query(User).filter(User.phone == phone).first()


def create_user(db: Session, phone: str, nickname: str, password: str) -> User:
    user = User(phone=phone, nickname=nickname, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Two concurrent registrations can both pass the pre-check; the unique
        # index on ``phone`` is the real guard.
        db.rollback()
        raise PhoneAlreadyRegistered(phone) from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, phone: str, password: str) -> User | None:
    user = get_user_by_phone(db, phone)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def reset_password(db: Session, user: User, new_password: str) -> User:
    """Set a new password and invalidate every token issued before it."""
    user.password_hash = hash_password(new_password)
    user.token_version = int(user.token_version or 0) + 1
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class AiQuotaExceeded(Exception):
    """Raised when the daily AI question quota is already used up."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"daily AI quota of {limit} questions reached")
        self.limit = limit


def _ai_usage_row(db: Session, user_id: int, usage_date: date) -> UserAiDailyUsage | None:
    return (
        db.query(UserAiDailyUsage)
        .filter(UserAiDailyUsage.user_id == user_id, UserAiDailyUsage.usage_date == usage_date)
        .first()
    )


def ai_quota_used(db: Session, user_id: int, usage_date: date | None = None) -> int:
    """Questions already charged against ``user_id`` for ``usage_date``."""
    row = _ai_usage_row(db, user_id, usage_date or today_cn())
    return int(row.count) if row else 0


def consume_ai_quota(db: Session, user_id: int, limit: int, usage_date: date | None = None) -> None:
    """Atomically charge one question against the daily quota.

    ``UPDATE … SET count = count + 1 WHERE … AND count < limit`` is a single
    statement, so concurrent requests cannot overrun the limit. The first
    question of the day has no row yet, hence the INSERT fallback: if another
    request inserted that row first the unique index raises ``IntegrityError``,
    the transaction is rolled back and the UPDATE is retried once.
    """
    day = usage_date or today_cn()
    if limit <= 0:
        raise AiQuotaExceeded(limit)

    def try_increment() -> bool:
        result = db.execute(
            update(UserAiDailyUsage)
            .where(
                UserAiDailyUsage.user_id == user_id,
                UserAiDailyUsage.usage_date == day,
                UserAiDailyUsage.count < limit,
            )
            .values(count=UserAiDailyUsage.count + 1)
        )
        db.commit()
        return (result.rowcount or 0) > 0

    if try_increment():
        return
    # No row yet (first question of the day) or the limit is already reached.
    if _ai_usage_row(db, user_id, day) is not None:
        raise AiQuotaExceeded(limit)

    db.add(UserAiDailyUsage(user_id=user_id, usage_date=day, count=1))
    try:
        db.commit()
        return
    except IntegrityError:
        # Another request created today's row between our UPDATE and INSERT.
        db.rollback()
    if not try_increment():
        raise AiQuotaExceeded(limit)


def refund_ai_quota(db: Session, user_id: int, usage_date: date | None = None) -> None:
    """Give back one question (used when an answer never reached the client)."""
    day = usage_date or today_cn()
    db.execute(
        update(UserAiDailyUsage)
        .where(
            UserAiDailyUsage.user_id == user_id,
            UserAiDailyUsage.usage_date == day,
            UserAiDailyUsage.count > 0,
        )
        .values(count=UserAiDailyUsage.count - 1)
    )
    db.commit()

