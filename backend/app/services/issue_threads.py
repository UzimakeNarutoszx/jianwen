"""Published issue queries and human-reviewed publication transactions.

No function here invokes AI. Callers own commit/rollback boundaries.
"""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.content import ContentArticle
from app.models.issue import ContentIssue, ContentIssueEvent, IssueCandidate, IssueRevision, UserIssueFollow

STAGES = {"consulting", "published", "implementing", "ended", "ongoing"}
BEIJING = ZoneInfo("Asia/Shanghai")


def visible_issue(db: Session, key: str, *, lock: bool = False) -> ContentIssue:
    visited = set()
    while key not in visited and len(visited) < 100:
        visited.add(key)
        query = db.query(ContentIssue).filter_by(issue_key=key)
        if lock:
            query = query.with_for_update().populate_existing()
        issue = query.first()
        if issue is None:
            break
        if issue.is_visible:
            return issue
        if not issue.merged_into:
            break
        key = issue.merged_into
    raise HTTPException(404, "议题不存在或尚未发布")


def issue_events(db: Session, issue: ContentIssue) -> list[ContentIssueEvent]:
    return db.query(ContentIssueEvent).filter_by(issue_id=issue.id).order_by(
        ContentIssueEvent.event_date, ContentIssueEvent.id).all()


def brief(issue: ContentIssue, event: ContentIssueEvent | None = None, previous=None) -> dict:
    return {"issue_key": issue.issue_key, "title": issue.title, "stage": issue.stage,
            "status_line": issue.status_line, "event_count": issue.event_count,
            "published_version": issue.published_version,
            "position": event.position if event else None,
            "prev_delta": previous.delta_summary if previous else None}


def event_response(db: Session, event: ContentIssueEvent) -> dict:
    article = db.query(ContentArticle).filter_by(article_id=event.article_id).first()
    references = article.references if article and isinstance(article.references, list) else []
    return {"event_id": event.id, "article_id": event.article_id, "event_date": event.event_date,
            "delta_summary": event.delta_summary, "position": event.position,
            "updated_version": event.updated_version, "references": references,
            "historical": event.historical}


def article_issue(db: Session, article_id: str) -> dict | None:
    row = db.query(ContentIssue, ContentIssueEvent).join(
        ContentIssueEvent, ContentIssueEvent.issue_id == ContentIssue.id).filter(
        ContentIssue.is_visible.is_(True), ContentIssueEvent.article_id == article_id).first()
    if not row:
        return None
    issue, event = row
    events = issue_events(db, issue)
    index = next(i for i, item in enumerate(events) if item.id == event.id)
    return brief(issue, event, events[index - 1] if index else None)


def detail(db: Session, issue: ContentIssue, user_id: int | None = None) -> dict:
    from app.services.policy_checks import list_policy_checks
    follow = db.query(UserIssueFollow).filter_by(user_id=user_id, issue_id=issue.id).first() if user_id else None
    return {**brief(issue), "events": [event_response(db, event) for event in issue_events(db, issue)],
            "is_following": follow is not None, "last_seen_version": follow.last_seen_version if follow else None,
            "policy_checks": list_policy_checks(db, issue_key=issue.issue_key)}


def published_context(db: Session, key: str) -> dict:
    issue = visible_issue(db, key)
    events = issue_events(db, issue)
    return {**brief(issue), "events": [event_response(db, event) for event in events[-12:]],
            "earlier_events_omitted": max(0, len(events) - 12)}


def followed_updates(db: Session, user_id: int) -> list[dict]:
    rows = db.query(ContentIssue, UserIssueFollow).join(UserIssueFollow,
        UserIssueFollow.issue_id == ContentIssue.id).filter(UserIssueFollow.user_id == user_id,
        ContentIssue.is_visible.is_(True), ContentIssue.published_version > UserIssueFollow.last_seen_version
        ).order_by(ContentIssue.last_date.desc(), ContentIssue.id.desc()).all()
    result = []
    for issue, follow in rows:
        events = [e for e in issue_events(db, issue) if e.updated_version > follow.last_seen_version]
        result.append({"issue": brief(issue), "new_events": len(events),
                       "events": [event_response(db, e) for e in events]})
    return result


def mark_seen(db: Session, issue: ContentIssue, user_id: int, version: int) -> None:
    if version > issue.published_version:
        raise HTTPException(422, "已读版本尚未发布")
    count = db.query(UserIssueFollow).filter_by(user_id=user_id, issue_id=issue.id).update(
        {UserIssueFollow.last_seen_version: case(
            (UserIssueFollow.last_seen_version < version, version), else_=UserIssueFollow.last_seen_version)},
        synchronize_session=False)
    if not count:
        raise HTTPException(404, "请先关注议题")


def _reindex(db: Session, issue: ContentIssue) -> None:
    db.flush()
    events = issue_events(db, issue)
    for index, event in enumerate(events, 1):
        event.position = index
    issue.event_count = len(events)
    issue.first_date = events[0].event_date if events else None
    issue.last_date = events[-1].event_date if events else None


def _revision(db: Session, issue: ContentIssue, action: str, reviewer: str) -> None:
    _reindex(db, issue)
    db.add(IssueRevision(issue_id=issue.id, version=issue.published_version, action=action,
        reviewer=reviewer, snapshot={**brief(issue), "is_visible": issue.is_visible,
        "merged_into": issue.merged_into, "events": [
            {**event_response(db, e), "event_date": e.event_date.isoformat()} for e in issue_events(db, issue)]}))


def validate_candidate(db: Session, candidate: IssueCandidate, payload: dict, *, _current_version: int | None = None) -> None:
    if candidate.status != "pending":
        raise ValueError("候选已经审核")
    if not isinstance(payload, dict):
        raise ValueError("候选必须是对象")
    if payload.get("article_id") != candidate.article_id:
        raise ValueError("不得替换候选来源文章")
    if payload.get("action") not in ("new", "join") or payload.get("stage") not in STAGES:
        raise ValueError("归并动作或阶段无效")
    if payload.get("action") != candidate.payload.get("action") or payload.get("issue_key") != candidate.payload.get("issue_key"):
        raise ValueError("不能更换候选归并目标，请拒绝并重新生成")
    for name, minimum, maximum in (("title", 1, 40), ("status_line", 1, 200), ("delta_summary", 40, 160)):
        value = payload.get(name)
        if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
            raise ValueError(f"{name} 长度须为 {minimum}–{maximum}")
    from app.services.daily_articles import PROHIBITED_CLICHES
    if any(word in payload[name] for word in PROHIBITED_CLICHES for name in ("title", "status_line", "delta_summary")):
        raise ValueError("候选含空泛套话")
    confidence = payload.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 60 <= confidence <= 100:
        raise ValueError("发布置信度须为 60–100，低置信度候选需人工补证后修改")
    if not db.query(ContentArticle.id).filter_by(article_id=candidate.article_id).first():
        raise ValueError("来源文章不存在")
    if payload["action"] == "join":
        issue = db.query(ContentIssue).filter_by(issue_key=payload.get("issue_key"), is_visible=True).first()
        if issue is None or issue.published_version != (_current_version if _current_version is not None else candidate.base_version):
            raise ValueError("目标不存在或发布基线已变化，请重新生成并审核候选")
    elif candidate.base_version != 0:
        raise ValueError("不能把已有议题候选改为新议题")


def publish_candidate(db: Session, candidate_id: int, payload: dict | None, reviewer: str,
                      *, _current_version: int | None = None) -> ContentIssue:
    if not reviewer.strip():
        raise ValueError("必须提供审核人")
    candidate = db.query(IssueCandidate).filter_by(id=candidate_id).with_for_update().populate_existing().first()
    if candidate is None:
        raise ValueError("候选不存在")
    if candidate.status == "published":
        # Repeating the identical approval is safe; differing text requires a new candidate.
        if payload is not None and payload != candidate.payload:
            raise ValueError("已发布候选不能修改")
        event = db.query(ContentIssueEvent).filter_by(article_id=candidate.article_id).first()
        if event is None:
            raise ValueError("已发布事件已被移除")
        return db.get(ContentIssue, event.issue_id)
    selected = payload if payload is not None else candidate.payload
    validate_candidate(db, candidate, selected, _current_version=_current_version)
    if selected["action"] == "join":
        issue = visible_issue(db, selected["issue_key"], lock=True)
        if issue.published_version != (_current_version if _current_version is not None else candidate.base_version):
            raise ValueError("发布基线已变化")
    else:
        issue = ContentIssue(issue_key="issue-" + uuid4().hex[:20], title=selected["title"], published_version=0)
        db.add(issue)
        db.flush()
    existing = db.query(ContentIssueEvent).filter_by(article_id=candidate.article_id).with_for_update().first()
    if existing and existing.issue_id != issue.id:
        raise ValueError("该文章已有主议题，请先人工 detach 或 merge")
    issue.title, issue.status_line, issue.stage = selected["title"], selected["status_line"], selected["stage"]
    issue.is_visible = True
    issue.published_version += 1
    from app.models.issue import IssueCandidateJob
    job = db.get(IssueCandidateJob, candidate.job_id)
    if existing:
        existing.delta_summary = selected["delta_summary"]
        existing.updated_version = issue.published_version
    else:
        db.add(ContentIssueEvent(issue_id=issue.id, article_id=candidate.article_id,
            event_date=job.content_date, delta_summary=selected["delta_summary"],
            updated_version=issue.published_version,
            historical=job.content_date < datetime.now(BEIJING).date()))
    candidate.payload, candidate.status = selected, "published"
    candidate.reviewed_by, candidate.reviewed_at = reviewer, datetime.utcnow()
    _revision(db, issue, "publish", reviewer)
    return issue


def publish_review_batch(db: Session, documents: list[dict], reviewer: str) -> None:
    """Approve a reviewed file atomically, including several articles joining one issue."""
    if not isinstance(documents, list) or not documents:
        raise ValueError("审阅文件须为非空数组")
    ids = [item["candidate_id"] for item in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("文件含重复候选")
    candidates = {c.id: c for c in db.query(IssueCandidate).filter(IssueCandidate.id.in_(ids)).order_by(
        IssueCandidate.id).with_for_update().populate_existing().all()}
    keys = sorted({item["payload"]["issue_key"] for item in documents if item["payload"].get("action") == "join"})
    targets = {issue.issue_key: issue for issue in db.query(ContentIssue).filter(ContentIssue.issue_key.in_(keys)).order_by(
        ContentIssue.issue_key).with_for_update().populate_existing().all()}
    for item in documents:
        candidate = candidates.get(item["candidate_id"])
        if candidate is None or item["base_version"] != candidate.base_version:
            raise ValueError("候选或审核基线无效")
        if candidate.status != "published":
            validate_candidate(db, candidate, item["payload"])
    for item in documents:
        target = targets.get(item["payload"].get("issue_key"))
        publish_candidate(db, item["candidate_id"], item["payload"], reviewer,
                          _current_version=target.published_version if target else None)


def moderate(db: Session, action: str, key: str, reviewer: str, *, target: str | None = None,
             article_id: str | None = None) -> None:
    if not reviewer.strip():
        raise ValueError("必须提供审核人")
    # Lock in stable order so opposite merge requests cannot deadlock.
    keys = sorted(set([key] + ([target] if target else [])))
    rows = db.query(ContentIssue).filter(ContentIssue.issue_key.in_(keys)).order_by(
        ContentIssue.issue_key).with_for_update().populate_existing().all()
    issues = {i.issue_key: i for i in rows}
    if key not in issues:
        raise ValueError("议题不存在")
    issue = issues[key]
    if action == "hide":
        if not issue.is_visible:
            return
        issue.is_visible = False
    elif action == "detach":
        event = db.query(ContentIssueEvent).filter_by(issue_id=issue.id, article_id=article_id).first()
        if event is None:
            raise ValueError("议题中无此文章")
        db.delete(event)
    elif action == "merge":
        if target not in issues or target == key or not issues[target].is_visible or issue.merged_into:
            raise ValueError("归并目标无效")
        destination = issues[target]
        destination.published_version += 1
        for event in issue_events(db, issue):
            event.issue_id, event.updated_version = destination.id, destination.published_version
        for follow in db.query(UserIssueFollow).filter_by(issue_id=issue.id).all():
            other = db.query(UserIssueFollow).filter_by(user_id=follow.user_id, issue_id=destination.id).first()
            if other:
                db.delete(follow)
            else:
                follow.issue_id, follow.last_seen_version = destination.id, 0
        issue.is_visible, issue.merged_into = False, destination.issue_key
        _revision(db, destination, "merge", reviewer)
    else:
        raise ValueError("不支持的操作")
    issue.published_version += 1
    _revision(db, issue, action, reviewer)


def revise_issue(db: Session, key: str, document: dict, reviewer: str) -> None:
    """Explicit human correction, with optimistic version check and complete audit snapshot."""
    issue = visible_issue(db, key, lock=True)
    if not reviewer.strip() or document.get("published_version") != issue.published_version:
        raise ValueError("审核人为空或修订基线已变化")
    changes = document.get("events", [])
    if not isinstance(changes, list):
        raise ValueError("events 必须是数组")
    events = {e.article_id: e for e in issue_events(db, issue)}
    selected = []
    for change in changes:
        article_id, delta = change.get("article_id"), change.get("delta_summary")
        if article_id not in events or not isinstance(delta, str) or not 40 <= len(delta.strip()) <= 160:
            raise ValueError("修订文章不存在或摘要长度无效")
        if article_id in selected:
            raise ValueError("重复修订事件")
        selected.append(article_id)
    for name, maximum in (("title", 40), ("status_line", 200)):
        if name in document and (not isinstance(document[name], str) or not 1 <= len(document[name].strip()) <= maximum):
            raise ValueError("修订标题或现状长度无效")
    if "stage" in document and document["stage"] not in STAGES:
        raise ValueError("阶段无效")
    issue.published_version += 1
    for name in ("title", "status_line", "stage"):
        if name in document:
            setattr(issue, name, document[name])
    for change in changes:
        event = events[change["article_id"]]
        event.delta_summary, event.updated_version = change["delta_summary"], issue.published_version
    _revision(db, issue, "revise", reviewer)


def weekly_issues(db: Session, user_id: int, start: datetime, end: datetime) -> list[dict]:
    rows = db.query(ContentIssue).join(UserIssueFollow, UserIssueFollow.issue_id == ContentIssue.id).filter(
        UserIssueFollow.user_id == user_id, ContentIssue.is_visible.is_(True)).all()
    output = []
    for issue in rows:
        revisions = db.query(IssueRevision).filter(IssueRevision.issue_id == issue.id,
            IssueRevision.published_at >= start, IssueRevision.published_at < end).order_by(IssueRevision.version).all()
        if not revisions:
            continue
        # Snapshots preserve what was published that week, including subsequently detached nodes.
        changed = {}
        for revision in revisions:
            for event in revision.snapshot["events"]:
                if event["updated_version"] == revision.version:
                    changed[event["event_id"]] = event
        output.append({"issue": {key: revisions[-1].snapshot[key] for key in brief(issue)},
                       "new_events": len(changed), "events": list(changed.values())})
    return output
