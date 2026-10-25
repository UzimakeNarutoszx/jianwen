from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.private_route import PrivateRoute
from app.schemas.policy import PolicyEvaluateRequest
from app.services.policy_checks import current_policy, evaluate_policy, list_policy_checks, policy_detail


router = APIRouter(route_class=PrivateRoute)


def no_store(response: Response):
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/policy-checks")
def list_checks(response: Response, db: Annotated[Session, Depends(get_db)],
                article_id: str | None = Query(default=None, max_length=64),
                issue_key: str | None = Query(default=None, max_length=80)):
    no_store(response)
    return list_policy_checks(db, article_id=article_id, issue_key=issue_key)


@router.get("/policy-checks/{policy_key}")
def get_check(policy_key: str, response: Response, db: Annotated[Session, Depends(get_db)]):
    no_store(response)
    return policy_detail(current_policy(db, policy_key))


@router.post("/policy-checks/{policy_key}/evaluate")
def evaluate_check(policy_key: str, payload: PolicyEvaluateRequest, response: Response,
                   db: Annotated[Session, Depends(get_db)]):
    no_store(response)
    return evaluate_policy(db, policy_key, payload)
