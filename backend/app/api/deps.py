from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User


auth_scheme = HTTPBearer(auto_error=False)


def _load_token_user(db: Session, token: str) -> User | None:
    """Resolve the user for ``token``, enforcing the token-version match.

    ``token_version`` is bumped on password change/reset, which invalidates
    every token issued before it. Tokens without the claim are treated as
    version 0 so existing sessions survive the upgrade.
    """
    payload = decode_access_token(token)
    if payload is None:
        return None

    user = db.get(User, payload.user_id)
    if not user or not user.is_active:
        return None
    if int(user.token_version or 0) != payload.token_version:
        return None
    return user


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    user = _load_token_user(db, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录")
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None

    return _load_token_user(db, credentials.credentials)
