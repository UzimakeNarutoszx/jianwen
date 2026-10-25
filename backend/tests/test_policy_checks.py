import asyncio
from datetime import date, timedelta
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

import httpx
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.v1.policies import router
from app.db.base import Base
from app.models.policy import ContentPolicyCheck
from app.schemas.policy import PolicyDocument, PolicyEvaluateRequest
from app.services.policy_checks import beijing_today, current_policy, evaluate_policy, import_policy, list_policy_checks, policy_detail, pause_policy


def document():
    today = beijing_today()
    return PolicyDocument.model_validate({
        "policy_key": "test-policy", "title": "合成测试政策", "region": "测试地区", "version": "v1",
        "summary": "仅供自动化测试，不是真实政策。", "verified_at": today.isoformat(),
        "review_expires_at": (today + timedelta(days=30)).isoformat(), "effective_from": today.isoformat(),
        "reviewer": "test", "review_note": "合成测试资料",
        "sources": [{"id": "s1", "title": "合成依据", "org": "测试", "url": "https://www.gov.cn/test", "published_at": today.isoformat()}],
        "application_url": "https://www.gov.cn/test", "article_ids": ["article-test"],
        "questions": [{"id": key, "title": key, "help": "测试必要条件", "source_id": "s1",
                       "options": [{"value": "yes", "label": "符合", "outcome": "met", "reason": "符合条件"},
                                   {"value": "no", "label": "不符合", "outcome": "not_met", "reason": "不符合条件"},
                                   {"value": "unknown", "label": "不确定", "outcome": "unknown", "reason": "需核实"}]}
                      for key in ("region", "education")],
    })


class PolicyCheckTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.db = self.sessions()
        self.doc = document()
        import_policy(self.db, self.doc, publish=True)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def evaluate(self, answers, version="v1", **kwargs):
        return evaluate_policy(self.db, "test-policy", PolicyEvaluateRequest(version=version, answers=answers), **kwargs)

    def test_three_states_and_missing_answers(self):
        self.assertEqual(self.evaluate({"region": "yes", "education": "yes"})["result"], "potentially_eligible")
        self.assertEqual(self.evaluate({"region": "yes", "education": "unknown"})["result"], "insufficient_information")
        self.assertEqual(self.evaluate({})["result"], "insufficient_information")
        result = self.evaluate({"region": "no", "education": "unknown"})
        self.assertEqual(result["result"], "not_eligible")
        self.assertEqual(result["checks"][0]["source_id"], "s1")

    def test_invalid_values_and_versions(self):
        for answers in ({"unexpected": "yes"}, {"region": "unlisted"}):
            with self.assertRaises(HTTPException) as error:
                self.evaluate(answers)
            self.assertEqual(error.exception.status_code, 422)
        with self.assertRaises(HTTPException) as error:
            self.evaluate({}, version="old")
        self.assertEqual(error.exception.status_code, 409)

    def test_date_boundaries_and_pause(self):
        expiry = self.doc.review_expires_at
        self.evaluate({}, today=expiry)
        for day in (expiry + timedelta(days=1), self.doc.effective_from - timedelta(days=1)):
            with self.assertRaises(HTTPException):
                self.evaluate({}, today=day)
        record = current_policy(self.db, "test-policy")
        record.status = "paused"
        self.db.flush()
        detail = policy_detail(record)
        self.assertFalse(detail["available"])
        self.assertEqual(detail["questions"], [])
        self.assertTrue(detail["sources"])
        with self.assertRaises(HTTPException):
            self.evaluate({})

    def test_drafts_private_and_import_immutable(self):
        draft = self.doc.model_copy(update={"policy_key": "private-draft", "verified_at": None})
        import_policy(self.db, draft)
        self.db.commit()
        self.assertEqual(len(list_policy_checks(self.db)), 1)
        with self.assertRaises(HTTPException):
            current_policy(self.db, "private-draft")
        with self.assertRaises(ValueError):
            import_policy(self.db, draft, publish=True)
        with self.assertRaises(ValueError):
            import_policy(self.db, self.doc.model_copy(update={"summary": "changed"}), publish=True)
        newer = self.doc.model_copy(update={"version": "v2"})
        import_policy(self.db, newer, publish=True)
        self.db.commit()
        self.assertEqual(current_policy(self.db, "test-policy").version, "v2")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ContentPolicyCheck)), 3)

    def test_anonymous_http_no_answers_saved(self):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/content")
        def database():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = database
        before = self.db.scalar(select(func.count()).select_from(ContentPolicyCheck))
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                detail = await client.get("/api/v1/content/policy-checks/test-policy")
                self.assertEqual(detail.status_code, 200)
                self.assertNotIn("outcome", detail.json()["questions"][0]["options"][0])
                result = await client.post("/api/v1/content/policy-checks/test-policy/evaluate", json={"version": "v1", "answers": {"region": "yes"}})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.headers["cache-control"], "private, no-store")
                self.assertEqual(result.json()["result"], "insufficient_information")
                invalid = await client.post("/api/v1/content/policy-checks/test-policy/evaluate", json={"version": "v1", "answers": {}, "user_id": 2})
                self.assertEqual(invalid.status_code, 422)
                self.assertEqual(invalid.headers["cache-control"], "private, no-store")
                stale = await client.post("/api/v1/content/policy-checks/test-policy/evaluate", json={"version": "old", "answers": {}})
                self.assertEqual(stale.status_code, 409)
                self.assertEqual(stale.headers["cache-control"], "private, no-store")
        asyncio.run(check())
        self.db.expire_all()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ContentPolicyCheck)), before)
        self.assertEqual(current_policy(self.db, "test-policy").document, self.doc.model_dump(mode="json"))
        self.assertFalse(self.db.new or self.db.dirty)

    def test_dry_run_does_not_import_database_module(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(self.doc.model_dump_json())
            script = Path(__file__).resolve().parents[1] / "scripts" / "policy_checks.py"
            result = subprocess.run([sys.executable, str(script), "import", str(path), "--dry-run"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("未写入数据库", result.stdout)

    def test_pause_targets_current_version_not_previously_loaded_snapshot(self):
        old = current_policy(self.db, "test-policy")
        import_policy(self.db, self.doc.model_copy(update={"version": "v2"}), publish=True)
        self.db.commit()
        paused = pause_policy(self.db, "test-policy")
        self.db.commit()
        self.assertEqual(paused.version, "v2")
        self.assertEqual(old.status, "published")
        self.assertIsNone(old.current_key)
        self.assertFalse(policy_detail(current_policy(self.db, "test-policy"))["available"])

    def test_unverified_dates_or_blank_review_cannot_publish(self):
        for updates in ({"effective_from": None}, {"reviewer": "   "}, {"review_note": "   "}):
            doc = self.doc.model_copy(update={"policy_key": "unverified", **updates})
            with self.assertRaises(ValueError):
                import_policy(self.db, doc, publish=True)

    def test_republish_refreshes_stale_requested_version(self):
        old = current_policy(self.db, "test-policy")
        self.db.rollback()
        # Keep an identity-map snapshot while another editor publishes v2.
        self.db.refresh(old)
        with self.sessions() as editor:
            import_policy(editor, self.doc.model_copy(update={"version": "v2"}), publish=True)
            editor.commit()
        import_policy(self.db, self.doc, publish=True)
        self.db.commit()
        with self.sessions() as reader:
            self.assertEqual(current_policy(reader, "test-policy").version, "v1")
            self.assertEqual(reader.scalar(select(func.count()).select_from(ContentPolicyCheck).where(
                ContentPolicyCheck.current_key == "test-policy")), 1)


if __name__ == "__main__":
    unittest.main()
