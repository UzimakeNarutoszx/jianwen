from datetime import date, datetime, timedelta
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import content, issues
from app.api.deps import get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.models.content import ContentArticle, DailyArticleSet
from app.models.issue import ContentIssue, ContentIssueEvent, IssueCandidate, IssueCandidateJob, IssueRevision, UserIssueFollow
from app.models.user import User
from app.schemas.issue import IssueSeenRequest
from app.services import daily_articles, issue_candidates as jobs, issue_threads as service
from services.ai import AIClientError


class IssueTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.db = self.factory()
        self.user = User(phone="13800000001", nickname="读者", password_hash="not-a-real-password")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def candidate(self, day=date(2026, 10, 20), article_id="ai-daily-20261020-1", issue=None):
        if not self.db.query(ContentArticle).filter_by(article_id=article_id).first():
            self.db.add(ContentArticle(article_id=article_id, title="官方政策进展", references=[{"url": "https://www.gov.cn/test"}]))
        job = self.db.query(IssueCandidateJob).filter_by(content_date=day).first()
        if job is None:
            job = IssueCandidateJob(content_date=day, article_ids=[article_id], status="completed", available_at=datetime.utcnow())
            self.db.add(job)
            self.db.flush()
        payload = {"article_id": article_id, "action": "join" if issue else "new", "title": "某项公共政策",
            "stage": "published", "status_line": "正式发布，仍需核对地方实施安排", "delta_summary": "政策公布了新的执行安排，明确申领流程和需要核对的材料；申请时间仍需以官方发布的实施细则为准。", "confidence": 85}
        if issue:
            payload["issue_key"] = issue.issue_key
        candidate = IssueCandidate(job_id=job.id, article_id=article_id, payload=payload,
            base_version=issue.published_version if issue else 0, status="pending")
        self.db.add(candidate)
        self.db.commit()
        return candidate

    def publish(self, candidate=None):
        candidate = candidate or self.candidate()
        issue = service.publish_candidate(self.db, candidate.id, None, "测试审核人")
        self.db.commit()
        return issue

    def test_candidate_never_public_until_explicit_approval(self):
        candidate = self.candidate()
        self.assertEqual(issues.list_issues(20, self.db), [])
        issue = self.publish(candidate)
        self.assertEqual(issue.event_count, 1)
        self.assertEqual(service.article_issue(self.db, candidate.article_id)["published_version"], 1)
        self.assertEqual(service.detail(self.db, issue)["events"][0]["references"][0]["url"], "https://www.gov.cn/test")
        self.assertEqual(self.db.query(IssueRevision).count(), 1)

    def test_publish_idempotent_and_single_primary_issue(self):
        candidate = self.candidate()
        first = self.publish(candidate)
        self.assertEqual(self.publish(candidate).id, first.id)
        self.assertEqual(self.db.query(ContentIssueEvent).count(), 1)
        other = self.candidate(day=date(2026, 10, 21), article_id=candidate.article_id)
        with self.assertRaises(ValueError):
            self.publish(other)
        self.db.rollback()
        self.assertEqual(self.db.query(ContentIssue).count(), 1)

    def test_backfill_sorts_by_event_date_but_notifies_by_publication_version(self):
        issue = self.publish()
        issues.follow_issue(issue.issue_key, self.user, self.db)
        issues.seen_issue(issue.issue_key, IssueSeenRequest(published_version=1), self.user, self.db)
        older = self.candidate(date(2026, 10, 19), "ai-daily-20261019-1", issue)
        self.publish(older)
        events = service.issue_events(self.db, issue)
        self.assertEqual([e.position for e in events], [1, 2])
        self.assertEqual(events[0].article_id, older.article_id)
        updates = service.followed_updates(self.db, self.user.id)
        self.assertEqual(updates[0]["new_events"], 1)
        self.assertEqual(updates[0]["events"][0]["updated_version"], 2)

    def test_seen_does_not_swallow_concurrent_publish_or_regress(self):
        issue = self.publish()
        issues.follow_issue(issue.issue_key, self.user, self.db)
        self.publish(self.candidate(date(2026, 10, 21), "ai-daily-20261021-1", issue))
        issues.seen_issue(issue.issue_key, IssueSeenRequest(published_version=1), self.user, self.db)
        self.assertEqual(service.followed_updates(self.db, self.user.id)[0]["new_events"], 1)
        issues.seen_issue(issue.issue_key, IssueSeenRequest(published_version=0), self.user, self.db)
        self.assertEqual(self.db.query(UserIssueFollow).one().last_seen_version, 1)
        with self.assertRaises(HTTPException) as raised:
            issues.seen_issue(issue.issue_key, IssueSeenRequest(published_version=999), self.user, self.db)
        self.assertEqual(raised.exception.status_code, 422)

    def test_revision_of_read_event_is_unread_and_audited(self):
        issue = self.publish()
        issues.follow_issue(issue.issue_key, self.user, self.db)
        issues.seen_issue(issue.issue_key, IssueSeenRequest(published_version=1), self.user, self.db)
        service.revise_issue(self.db, issue.issue_key, {"published_version": 1, "events": [{
            "article_id": "ai-daily-20261020-1", "delta_summary": "修订后的政策摘要补充了官方来源和具体执行条件，原先没有明确的申领日期目前仍待地方主管部门核实。"}]}, "审核人")
        self.db.commit()
        self.assertEqual(service.followed_updates(self.db, self.user.id)[0]["new_events"], 1)
        self.assertEqual(self.db.query(IssueRevision).count(), 2)

    def test_stale_candidate_rejected(self):
        issue = self.publish()
        stale = self.candidate(date(2026, 10, 21), "ai-daily-20261021-1", issue)
        service.revise_issue(self.db, issue.issue_key, {"published_version": 1, "status_line": "人工已修订现状"}, "审核人")
        self.db.commit()
        with self.assertRaises(ValueError):
            self.publish(stale)

    def test_invalid_payload_and_low_confidence_not_publishable(self):
        candidate = self.candidate()
        for change in ({"confidence": 30}, {"article_id": "unknown"}, {"stage": "bad"}, {"delta_summary": "短"}, {"confidence": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                service.validate_candidate(self.db, candidate, {**candidate.payload, **change})

    def test_hide_excluded_from_article_context_list_and_updates(self):
        issue = self.publish()
        issues.follow_issue(issue.issue_key, self.user, self.db)
        service.moderate(self.db, "hide", issue.issue_key, "审核人")
        self.db.commit()
        self.assertIsNone(service.article_issue(self.db, "ai-daily-20261020-1"))
        self.assertEqual(issues.list_issues(20, self.db), [])
        self.assertEqual(service.followed_updates(self.db, self.user.id), [])
        with self.assertRaises(HTTPException):
            service.published_context(self.db, issue.issue_key)

    def test_merge_moves_followers_events_and_detach_reindexes(self):
        source = self.publish()
        target = self.publish(self.candidate(date(2026, 10, 21), "ai-daily-20261021-1"))
        issues.follow_issue(source.issue_key, self.user, self.db)
        service.moderate(self.db, "merge", source.issue_key, "审核人", target=target.issue_key)
        self.db.commit()
        self.assertEqual(target.event_count, 2)
        self.assertEqual(source.event_count, 0)
        self.assertEqual(service.visible_issue(self.db, source.issue_key).issue_key, target.issue_key)
        self.assertEqual(self.db.query(UserIssueFollow).one().issue_id, target.id)
        service.moderate(self.db, "detach", target.issue_key, "审核人", article_id="ai-daily-20261020-1")
        self.db.commit()
        self.assertEqual(target.event_count, 1)
        self.assertEqual(service.issue_events(self.db, target)[0].position, 1)

    def test_seen_rejects_merged_alias_but_canonical_key_can_acknowledge(self):
        source = self.publish()
        source_follow = issues.follow_issue(source.issue_key, self.user, self.db)
        # Make source version 2 before merging; target remains version 1.
        source_update = self.candidate(date(2026, 10, 21), "ai-daily-20261021-1", source)
        self.publish(source_update)
        target = self.publish(self.candidate(date(2026, 10, 22), "ai-daily-20261022-1"))
        service.moderate(self.db, "merge", source.issue_key, "审核人", target=target.issue_key)
        self.db.commit()
        self.assertEqual(target.published_version, 2)
        with self.assertRaises(HTTPException) as raised:
            issues.seen_issue(source.issue_key, IssueSeenRequest(published_version=2), self.user, self.db)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(service.followed_updates(self.db, self.user.id)[0]["new_events"], 3)
        result = issues.seen_issue(target.issue_key, IssueSeenRequest(published_version=2), self.user, self.db)
        self.assertEqual(result["last_seen_version"], 2)
        self.assertEqual(service.followed_updates(self.db, self.user.id), [])

    def test_unfollow_resolves_and_locks_issue_before_merge_follow_migration(self):
        issue = self.publish()
        captured = {}
        original = issues.visible_issue

        def locked_lookup(db, key, *, lock=False):
            captured["lock"] = lock
            return original(db, key, lock=lock)

        with patch.object(issues, "visible_issue", side_effect=locked_lookup):
            issues.unfollow_issue(issue.issue_key, self.user, self.db)
        self.assertTrue(captured["lock"])

    def test_weekly_uses_publish_time_instead_of_historical_event_date(self):
        issue = self.publish(self.candidate(date(2025, 1, 1), "ai-daily-20250101-1"))
        issues.follow_issue(issue.issue_key, self.user, self.db)
        now = datetime.utcnow()
        output = service.weekly_issues(self.db, self.user.id, now - timedelta(hours=1), now + timedelta(hours=1))
        self.assertEqual(output[0]["new_events"], 1)
        self.assertEqual(output[0]["events"][0]["event_date"], "2025-01-01")
        self.assertTrue(output[0]["events"][0]["historical"])

    def test_historical_flag_is_persisted_from_content_date_and_normal_event_is_false(self):
        historical_issue = self.publish(self.candidate(date(2025, 1, 1), "ai-daily-20250101-1"))
        normal_issue = self.publish(self.candidate(datetime.now().date(), "ai-daily-" + datetime.now().strftime("%Y%m%d") + "-2"))
        historical_event = service.issue_events(self.db, historical_issue)[0]
        normal_event = service.issue_events(self.db, normal_issue)[0]
        self.assertTrue(historical_event.historical)
        self.assertFalse(normal_event.historical)
        self.assertTrue(service.detail(self.db, historical_issue)["events"][0]["historical"])
        # Revision timestamp changes do not alter the persisted classification.
        service.revise_issue(self.db, historical_issue.issue_key, {
            "published_version": historical_issue.published_version,
            "events": [{"article_id": historical_event.article_id,
                         "delta_summary": "修订后的历史节点补充了官方来源和具体执行条件，当前仍需以主管部门公布的实施细则为准。"}],
        }, "审核人")
        self.db.commit()
        self.assertTrue(service.issue_events(self.db, historical_issue)[0].historical)

    def test_queue_is_idempotent_skips_seed_and_dry_run_does_not_write(self):
        article = ContentArticle(article_id="ai-daily-20261020-1", title="政策")
        self.db.add(article)
        self.db.flush()
        self.db.add(DailyArticleSet(content_date=date(2026, 10, 20), article_id=article.article_id, position=1))
        self.db.commit()
        self.assertEqual(len(jobs.backfill(self.db, date(2026, 1, 1), dry_run=True)), 1)
        self.assertEqual(self.db.query(IssueCandidateJob).count(), 0)
        self.assertTrue(jobs.enqueue_daily(self.db, date(2026, 10, 20), [article]))
        self.db.commit()
        self.assertFalse(jobs.enqueue_daily(self.db, date(2026, 10, 20), [article]))
        self.assertFalse(jobs.enqueue_daily(self.db, date(2026, 10, 21), [ContentArticle(article_id="seed", title="种子")]))

    def queued_job(self):
        article = ContentArticle(article_id="ai-daily-20261020-1", title="政策")
        self.db.add(article)
        self.db.commit()
        jobs.enqueue_daily(self.db, date(2026, 10, 20), [article])
        self.db.commit()
        return self.db.query(IssueCandidateJob).one()

    def test_worker_generates_only_candidates(self):
        self.queued_job()
        payload = {"article_id": "ai-daily-20261020-1", "action": "new", "title": "候选"}
        with patch.object(jobs, "ask_ai", return_value=SimpleNamespace(text=json.dumps([payload]))):
            self.assertTrue(jobs.process_one(self.db))
        self.assertEqual(self.db.query(IssueCandidate).count(), 1)
        self.assertEqual(self.db.query(ContentIssue).count(), 0)
        self.assertEqual(self.db.query(IssueCandidateJob).one().status, "completed")
        self.assertFalse(jobs.process_one(self.db))

    def test_worker_ai_and_json_failures_are_durable_and_not_raised(self):
        job = self.queued_job()
        for outcome in (AIClientError("offline"), SimpleNamespace(text="invalid"),
                        SimpleNamespace(text='[{"article_id":"unknown","action":"new"}]')):
            job.available_at = datetime.utcnow() - timedelta(seconds=1)
            self.db.commit()
            kwargs = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
            with patch.object(jobs, "ask_ai", **kwargs):
                self.assertTrue(jobs.process_one(self.db))
            self.db.refresh(job)
        self.assertEqual(job.status, "failed")
        self.assertEqual(self.db.query(IssueCandidate).count(), 0)

    def test_daily_return_survives_enqueue_failure_without_calling_candidate_ai(self):
        day = date(2026, 10, 20)
        for index in range(5):
            article = ContentArticle(article_id=f"ai-daily-20261020-{index}", title="政策")
            self.db.add(article)
            self.db.flush()
            self.db.add(DailyArticleSet(content_date=day, article_id=article.article_id, position=index))
        self.db.commit()
        with patch.object(jobs, "enqueue_daily", side_effect=RuntimeError("queue failed")), patch.object(jobs, "ask_ai") as ai:
            self.assertEqual(len(daily_articles.ensure_daily_articles(self.db, day)), 5)
            ai.assert_not_called()
        self.assertEqual(self.db.query(DailyArticleSet).count(), 5)

    def test_batch_approval_allows_shared_baseline_but_rejects_stale_file(self):
        issue = self.publish()
        candidates = [self.candidate(date(2026, 10, 21), f"ai-daily-20261021-{i}", issue) for i in (1, 2)]
        documents = [{"candidate_id": c.id, "base_version": c.base_version, "payload": c.payload} for c in candidates]
        service.publish_review_batch(self.db, documents, "审核人")
        self.db.commit()
        self.assertEqual(issue.event_count, 3)
        self.assertEqual(issue.published_version, 3)
        self.assertEqual([c.base_version for c in candidates], [1, 1])
        service.publish_review_batch(self.db, documents, "审核人")
        self.db.commit()
        self.assertEqual(issue.published_version, 3)

    def test_expired_job_lease_recovers_and_final_attempt_becomes_failed(self):
        job = self.queued_job()
        job.status, job.attempts, job.lease_until = "running", 1, datetime.utcnow() - timedelta(seconds=1)
        self.db.commit()
        with patch.object(jobs, "ask_ai", return_value=SimpleNamespace(text="[]")):
            jobs.process_one(self.db)
        self.db.refresh(job)
        self.assertEqual(job.status, "completed")
        job.status, job.attempts, job.lease_until = "running", 3, datetime.utcnow() - timedelta(seconds=1)
        self.db.commit()
        self.assertFalse(jobs.process_one(self.db))
        self.db.refresh(job)
        self.assertEqual(job.status, "failed")

    def test_http_auth_follow_seen_and_unfollow_contract(self):
        issue = self.publish()
        app = FastAPI()
        app.include_router(issues.router)
        app.dependency_overrides[get_db] = lambda: self.db
        headers = {"Authorization": "Bearer " + create_access_token(self.user.id)}
        with TestClient(app) as client:
            for method, path, body in (("get", "/profile/issues", None), ("get", "/profile/issues/updates", None),
                ("post", f"/profile/issues/{issue.issue_key}/follow", None),
                ("delete", f"/profile/issues/{issue.issue_key}/follow", None),
                ("post", f"/profile/issues/{issue.issue_key}/seen", {"published_version": 1})):
                kwargs = {"json": body} if body else {}
                self.assertEqual(getattr(client, method)(path, **kwargs).status_code, 401)
            self.assertEqual(client.post(f"/profile/issues/{issue.issue_key}/follow", headers=headers).json(), {"is_following": True})
            self.assertEqual(client.get(f"/content/issues/{issue.issue_key}", headers=headers).json()["last_seen_version"], 1)
            # Following starts at the current published version; only later publications notify.
            self.assertEqual(client.get("/profile/issues/updates", headers=headers).json(), [])
            self.assertEqual(client.post(f"/profile/issues/{issue.issue_key}/seen", headers=headers,
                json={"published_version": 1}).json()["last_seen_version"], 1)
            self.assertEqual(client.get("/profile/issues/updates", headers=headers).json(), [])
            self.assertEqual(client.delete(f"/profile/issues/{issue.issue_key}/follow", headers=headers).status_code, 200)
            self.assertEqual(client.get("/content/issues?limit=51").status_code, 422)

    def test_article_detail_and_both_ask_routes_use_published_context_only(self):
        issue = self.publish()
        response = content.get_article("ai-daily-20261020-1", self.db)
        self.assertEqual(response.issue.issue_key, issue.issue_key)
        self.assertEqual(response.policy_checks, [])
        context = content._build_ask_context(self.db, issue_key=issue.issue_key)
        self.assertEqual(context["关联议题时间线"]["events"][0]["article_id"], "ai-daily-20261020-1")
        from app.schemas.content import AiAnswerRequest
        request = AiAnswerRequest(question="发生什么变化", issue_key=issue.issue_key)
        with patch.object(content, "ask_ai", return_value=SimpleNamespace(text="测试回答")) as ai:
            content.answer_question(request, self.db, self.user)
            self.assertEqual(ai.call_args.kwargs["context"]["关联议题时间线"]["issue_key"], issue.issue_key)
        with patch.object(content, "stream_ask", return_value=iter(["测试流式回答"])) as stream:
            content.stream_answer_question(request, self.db, self.user)
            self.assertEqual(stream.call_args.kwargs["context"]["关联议题时间线"]["issue_key"], issue.issue_key)
        for kwargs in ({"issue_key": "unknown"}, {"article_id": "unknown"}, {"policy_key": "unknown"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(HTTPException) as error:
                content._build_ask_context(self.db, **kwargs)
            self.assertEqual(error.exception.status_code, 404)

    def test_new_daily_set_commit_survives_queue_failure(self):
        day = date(2026, 10, 20)
        def generated(db, selected_date):
            articles = [ContentArticle(article_id=f"ai-daily-20261020-{i}", title="政策") for i in range(5)]
            db.add_all(articles)
            db.flush()
            return articles
        with patch.object(daily_articles, "_generate_ai_articles", side_effect=generated), patch.object(
            jobs, "enqueue_daily", side_effect=RuntimeError("queue failed")), patch.object(jobs, "ask_ai") as ai:
            self.assertEqual(len(daily_articles.ensure_daily_articles(self.db, day)), 5)
            ai.assert_not_called()
        with self.factory() as independent:
            self.assertEqual(independent.query(DailyArticleSet).count(), 5)

    def test_cli_exports_sources_validates_publishes_and_dry_run_never_invokes_ai(self):
        from scripts import issue_threads as cli
        candidate = self.candidate()
        with tempfile.TemporaryDirectory() as directory, patch.object(cli, "SessionLocal", self.factory), patch("builtins.print"):
            path = Path(directory) / "review.json"
            cli.main(["export", "--output", str(path)])
            document = json.loads(path.read_text())
            self.assertEqual(document[0]["source_article"]["references"][0]["url"], "https://www.gov.cn/test")
            cli.main(["validate", "--file", str(path)])
            cli.main(["publish", "--file", str(path), "--reviewer", "人工审核人"])
            cli.main(["publish", "--file", str(path), "--reviewer", "人工审核人"])
            with self.assertRaises(FileExistsError):
                cli.main(["export", "--output", str(path)])
            with patch.object(jobs, "ask_ai") as ai:
                cli.main(["backfill", "--since", "2026-01-01", "--dry-run"])
                ai.assert_not_called()
        self.db.expire_all()
        self.assertEqual(self.db.get(IssueCandidate, candidate.id).status, "published")
        self.assertEqual(self.db.query(ContentIssue).count(), 1)


if __name__ == "__main__":
    unittest.main()
