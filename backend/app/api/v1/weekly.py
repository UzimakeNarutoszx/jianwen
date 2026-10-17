from datetime import date
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.weekly import ReadingActivityRequest
from app.services.weekly_report import build_report, record_activity

router = APIRouter()


def private(response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"


@router.post("/reading-activity")
def reading_activity(payload: ReadingActivityRequest, response: Response,
                     current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    private(response)
    return record_activity(db, current_user, payload)


@router.get("/weekly-report")
def weekly_report(response: Response, week_start: date | None = None,
                  current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    private(response)
    return build_report(db, current_user, week_start)
