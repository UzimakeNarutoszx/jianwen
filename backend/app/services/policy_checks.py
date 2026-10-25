"""Deterministic, anonymous policy checks backed by reviewed snapshots."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy import ContentPolicyCheck
from app.schemas.policy import PolicyDocument, PolicyEvaluateRequest


def beijing_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def unavailable_reason(record: ContentPolicyCheck, doc: PolicyDocument, today: date) -> str:
    if record.status != "published":
        return "该政策自查已暂停，请查看官方最新说明。"
    if not doc.verified_at or not doc.review_expires_at or not doc.effective_from or not doc.reviewer.strip() or not doc.review_note.strip():
        return "规则尚未完成核验。"
    if doc.verified_at > today or doc.review_expires_at < today:
        return "规则需要重新核验，暂不提供适用判断。"
    if today < doc.effective_from:
        return "政策尚未生效。"
    if doc.effective_until and today > doc.effective_until:
        return "该版本政策已到期，请查看官方最新说明。"
    return ""


def current_policy(db: Session, key: str, *, lock: bool = False) -> ContentPolicyCheck:
    query = select(ContentPolicyCheck).where(
        ContentPolicyCheck.current_key == key,
        ContentPolicyCheck.status.in_(("published", "paused")),
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    record = db.scalar(query)
    if record is None:
        raise HTTPException(404, "未找到已发布的政策自查")
    return record


def pause_policy(db: Session, key: str) -> ContentPolicyCheck:
    # Serialize with publication against the current snapshot, not a retired version
    # that may have been loaded before a concurrent publication committed.
    record = current_policy(db, key, lock=True)
    record.status = "paused"
    db.flush()
    return record


def policy_detail(record: ContentPolicyCheck, today: date | None = None) -> dict:
    doc = PolicyDocument.model_validate(record.document)
    reason = unavailable_reason(record, doc, today or beijing_today())
    result = doc.model_dump(mode="json", exclude={"reviewer", "review_note", "article_ids", "issue_keys"})
    result.update(status=record.status, available=not reason, unavailable_reason=reason)
    result["questions"] = [
        {"id": q.id, "title": q.title, "help": q.help,
         "options": [{"value": o.value, "label": o.label} for o in q.options]}
        for q in doc.questions
    ] if not reason else []
    return result


def list_policy_checks(db: Session, *, article_id: str | None = None, issue_key: str | None = None) -> list[dict]:
    records = db.scalars(select(ContentPolicyCheck).where(
        ContentPolicyCheck.current_key.is_not(None),
        ContentPolicyCheck.status.in_(("published", "paused")),
    ).order_by(ContentPolicyCheck.policy_key)).all()
    result = []
    for record in records:
        doc = PolicyDocument.model_validate(record.document)
        if article_id is not None and article_id not in doc.article_ids:
            continue
        if issue_key is not None and issue_key not in doc.issue_keys:
            continue
        detail = policy_detail(record)
        result.append({k: detail[k] for k in (
            "policy_key", "title", "region", "version", "summary", "status", "available",
            "unavailable_reason", "verified_at", "review_expires_at",
        )})
    return result


def evaluate_policy(db: Session, key: str, payload: PolicyEvaluateRequest, *, today: date | None = None) -> dict:
    record = current_policy(db, key)
    doc = PolicyDocument.model_validate(record.document)
    if payload.version != record.version:
        raise HTTPException(409, "政策规则已更新，请重新加载并自查")
    reason = unavailable_reason(record, doc, today or beijing_today())
    if reason:
        raise HTTPException(410, reason)
    questions = {q.id: q for q in doc.questions}
    if set(payload.answers) - questions.keys():
        raise HTTPException(422, "存在未知问题，请重新加载")
    checks = []
    for question in doc.questions:
        value = payload.answers.get(question.id)
        option = next((o for o in question.options if o.value == value), None)
        if value is not None and option is None:
            raise HTTPException(422, "存在无效选项，请重新选择")
        checks.append({"question_id": question.id, "title": question.title,
                       "status": option.outcome if option else "unknown",
                       "reason": option.reason if option else "此项尚未回答，需要进一步确认。",
                       "source_id": question.source_id})
    statuses = {c["status"] for c in checks}
    outcome = "not_eligible" if "not_met" in statuses else "insufficient_information" if "unknown" in statuses else "potentially_eligible"
    titles = {"not_eligible": "暂不符合", "insufficient_information": "信息不足", "potentially_eligible": "可能符合"}
    return {"policy_key": key, "version": doc.version, "result": outcome, "title": titles[outcome],
            "checks": checks, "next_steps": doc.next_steps,
            "sources": [s.model_dump(mode="json") for s in doc.sources],
            "application_url": doc.application_url, "materials": doc.materials,
            "notice": "这是依据所选答案的初步自查，最终以官方受理审核为准。"}


def policy_ask_context(db: Session, key: str) -> dict:
    record = current_policy(db, key)
    doc = PolicyDocument.model_validate(record.document)
    reason = unavailable_reason(record, doc, beijing_today())
    if reason:
        raise HTTPException(410, reason)
    return {"政策": doc.title, "版本": doc.version, "核验日期": doc.verified_at.isoformat(),
            "说明": doc.summary, "条款": [{"条件": q.title, "解释": q.help} for q in doc.questions],
            "来源": [s.model_dump(mode="json") for s in doc.sources],
            "边界": "只解释公开条款；没有用户自查答案，不得判断用户资格。"}


def import_policy(db: Session, doc: PolicyDocument, *, publish: bool = False) -> ContentPolicyCheck:
    """Import a new immutable version. Callers explicitly choose publication."""
    requested = select(ContentPolicyCheck).where(
        ContentPolicyCheck.policy_key == doc.policy_key, ContentPolicyCheck.version == doc.version,
    )
    if publish:
        requested = requested.with_for_update().execution_options(populate_existing=True)
    existing = db.scalar(requested)
    data = doc.model_dump(mode="json")
    if existing and existing.document != data:
        raise ValueError("此版本已存在；修改规则或核验日期必须使用新版本")
    record = existing or ContentPolicyCheck(policy_key=doc.policy_key, version=doc.version, document=data, status="draft")
    if publish:
        # Validate before retiring the previous public snapshot.
        probe = ContentPolicyCheck(status="published", document=data)
        reason = unavailable_reason(probe, doc, beijing_today())
        if reason:
            raise ValueError(reason)
        current = db.scalar(select(ContentPolicyCheck).where(ContentPolicyCheck.current_key == doc.policy_key)
                            .with_for_update().execution_options(populate_existing=True))
        if current and current is not record:
            current.current_key = None
            db.flush()
        record.current_key = doc.policy_key
        record.status = "published"
    db.add(record)
    db.flush()
    return record
