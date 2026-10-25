"""Validate/import reviewed policy files without starting the application."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.policy import PolicyDocument


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "import", "pause"))
    parser.add_argument("target", help="资料 JSON 路径；pause 时为 policy_key")
    parser.add_argument("--publish", action="store_true", help="明确审核完成后发布新版本")
    parser.add_argument("--dry-run", action="store_true", help="只做本地资料校验，不连接数据库、不调用 AI")
    args = parser.parse_args()
    if args.command == "pause":
        if args.dry_run:
            print(f"将暂停 {args.target}；未连接数据库")
            return
        from app.db.session import SessionLocal
        from app.services.policy_checks import pause_policy
        with SessionLocal() as db:
            pause_policy(db, args.target)
            db.commit()
        print("已暂停")
        return
    doc = PolicyDocument.model_validate(json.loads(Path(args.target).read_text(encoding="utf-8")))
    if args.command == "validate" or args.dry_run:
        print(f"资料结构有效：{doc.policy_key} / {doc.version} / {len(doc.questions)} 个条件；未写入数据库")
        return
    from app.db.session import SessionLocal
    from app.services.policy_checks import import_policy
    with SessionLocal() as db:
        record = import_policy(db, doc, publish=args.publish)
        db.commit()
        print(f"已导入 {record.policy_key} / {record.version} / {record.status}")


if __name__ == "__main__":
    main()
