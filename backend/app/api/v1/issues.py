from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.api.private_route import PrivateRoute
from app.models.issue import ContentIssue, UserIssueFollow
from app.models.user import User
from app.schemas.issue import IssueBriefResponse, IssueDetailResponse, IssueSeenRequest, IssueUpdateItem
from app.services.issue_threads import brief, detail, followed_updates, mark_seen, visible_issue

def no_store(response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"


router = APIRouter(route_class=PrivateRoute, dependencies=[Depends(no_store)])


@router.get("/content/issues", response_model=list[IssueBriefResponse])
def list_issues(limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_db)):
    rows = db.query(ContentIssue).filter_by(is_visible=True).order_by(
        ContentIssue.last_date.desc(), ContentIssue.id.desc()).limit(limit).all()
    return [brief(issue) for issue in rows]


@router.get("/content/issues/{issue_key}", response_model=IssueDetailResponse)
def get_issue(issue_key: str, current_user: User | None = Depends(get_optional_current_user), db: Session = Depends(get_db)):
    return detail(db, visible_issue(db, issue_key), current_user.id if current_user else None)


@router.get("/profile/issues/updates", response_model=list[IssueUpdateItem])
def issue_updates(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return followed_updates(db, current_user.id)


@router.get("/profile/issues", response_model=list[IssueBriefResponse])
def followed_issues(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(ContentIssue).join(UserIssueFollow, UserIssueFollow.issue_id == ContentIssue.id).filter(
        UserIssueFollow.user_id == current_user.id, ContentIssue.is_visible.is_(True)).order_by(
        ContentIssue.last_date.desc(), ContentIssue.id.desc()).all()
    return [brief(issue) for issue in rows]


@router.post("/profile/issues/{issue_key}/follow")
def follow_issue(issue_key: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    issue = visible_issue(db, issue_key, lock=True)
    if not db.query(UserIssueFollow.id).filter_by(user_id=current_user.id, issue_id=issue.id).first():
        try:
            with db.begin_nested():
                db.add(UserIssueFollow(user_id=current_user.id, issue_id=issue.id, last_seen_version=issue.published_version))
                db.flush()
        except IntegrityError:
            pass
    db.commit()
    return {"is_following": True}


@router.delete("/profile/issues/{issue_key}/follow")
def unfollow_issue(issue_key: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Serialize with merge's canonical issue lock before deleting the follow.
    issue = visible_issue(db, issue_key, lock=True)
    db.query(UserIssueFollow).filter_by(user_id=current_user.id, issue_id=issue.id).delete()
    db.commit()
    return {"is_following": False}


@router.post("/profile/issues/{issue_key}/seen")
def seen_issue(issue_key: str, payload: IssueSeenRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    issue = visible_issue(db, issue_key, lock=True)
    if issue_key != issue.issue_key:
        # GET may resolve a merged alias, but writes must name the canonical
        # issue so an old page cannot acknowledge a different version number.
        from fastapi import HTTPException
        raise HTTPException(409, "议题已归并，请重新加载当前议题")
    mark_seen(db, issue, current_user.id, payload.published_version)
    db.commit()
    return {"last_seen_version": db.query(UserIssueFollow).filter_by(user_id=current_user.id, issue_id=issue.id).one().last_seen_version}
