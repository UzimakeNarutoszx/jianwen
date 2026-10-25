"""Human-only review commands. No command publishes automatically after AI generation."""
import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.issue import IssueCandidate
from app.models.content import ContentArticle
from app.services.issue_candidates import backfill, process_one
from app.services.issue_threads import moderate, publish_review_batch, revise_issue, validate_candidate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fill = commands.add_parser("backfill", help="仅排入候选任务，不直接调用 AI 或发布")
    fill.add_argument("--since", required=True, type=date.fromisoformat)
    fill.add_argument("--dry-run", action="store_true")
    commands.add_parser("work-once", help="执行一个候选 AI 任务，不发布")
    export = commands.add_parser("export")
    export.add_argument("--output", required=True, type=Path)
    for name in ("validate", "publish"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--file", required=True, type=Path)
        if name == "publish":
            cmd.add_argument("--reviewer", required=True)
    reject = commands.add_parser("reject")
    reject.add_argument("candidate_id", type=int)
    reject.add_argument("--reviewer", required=True)
    revise = commands.add_parser("revise")
    revise.add_argument("issue_key")
    revise.add_argument("--file", required=True, type=Path)
    revise.add_argument("--reviewer", required=True)
    for name in ("hide", "merge", "detach"):
        cmd = commands.add_parser(name)
        cmd.add_argument("issue_key")
        cmd.add_argument("--reviewer", required=True)
        if name == "merge":
            cmd.add_argument("target")
        if name == "detach":
            cmd.add_argument("article_id")
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        try:
            if args.command == "backfill":
                result = backfill(db, args.since, dry_run=args.dry_run)
                if args.dry_run:
                    db.rollback()
                else:
                    db.commit()
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.command == "work-once":
                print(json.dumps({"processed": process_one(db)}))
            elif args.command == "export":
                rows = db.query(IssueCandidate).filter_by(status="pending").order_by(IssueCandidate.id).all()
                data = []
                for candidate in rows:
                    article = db.query(ContentArticle).filter_by(article_id=candidate.article_id).first()
                    data.append({"candidate_id": candidate.id, "base_version": candidate.base_version,
                        "payload": candidate.payload, "source_article": {
                            "article_id": candidate.article_id, "title": article.title,
                            "summary": article.summary, "sections": article.sections,
                            "references": article.references} if article else None})
                # Never overwrite an existing human-edited review document.
                with args.output.open("x", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)
                print(f"导出 {len(data)} 条待审候选至 {args.output}")
            elif args.command in ("validate", "publish"):
                data = json.loads(args.file.read_text(encoding="utf-8"))
                if not isinstance(data, list) or not data:
                    raise ValueError("审阅文件须为非空数组")
                seen = set()
                for item in data:
                    cid = item["candidate_id"]
                    if cid in seen:
                        raise ValueError("文件含重复候选")
                    seen.add(cid)
                    candidate = db.get(IssueCandidate, cid)
                    if candidate is None or item["base_version"] != candidate.base_version:
                        raise ValueError("候选或审核基线无效")
                    if args.command == "validate":
                        validate_candidate(db, candidate, item["payload"])
                if args.command == "publish":
                    publish_review_batch(db, data, args.reviewer)
                    db.commit()
                print(f"{args.command}: {len(data)} 条")
            elif args.command == "reject":
                candidate = db.query(IssueCandidate).filter_by(id=args.candidate_id).with_for_update().first()
                if candidate is None or candidate.status != "pending" or not args.reviewer.strip():
                    raise ValueError("候选非待审或审核人为空")
                candidate.status, candidate.reviewed_by, candidate.reviewed_at = "rejected", args.reviewer, datetime.utcnow()
                db.commit()
            elif args.command == "revise":
                revise_issue(db, args.issue_key, json.loads(args.file.read_text(encoding="utf-8")), args.reviewer)
                db.commit()
            else:
                moderate(db, args.command, args.issue_key, args.reviewer,
                    target=getattr(args, "target", None), article_id=getattr(args, "article_id", None))
                db.commit()
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
