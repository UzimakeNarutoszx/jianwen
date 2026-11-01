import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.deps import get_db
from app.api.v1 import weekly, profile
from app.core.security import create_access_token
from app.db.base import Base
from app.models.content import ContentArticle, ContentCategory, ClassicBook, ClassicBookChapter
from app.models.profile import UserAiUsageRecord, UserBrowsingHistory, UserReadingPosition
from app.models.reading import ArticleReadingDay, ReadingInterval
from app.models.user import User
from app.schemas.weekly import ReadingActivityRequest
from app.services.weekly_report import BEIJING, build_report, record_activity


class WeeklyReportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.users = [User(phone=f'1380000000{i}', nickname=f'读者{i}', password_hash='hash') for i in range(2)]
        self.db.add_all(self.users + [ContentArticle(article_id='a', title='文章甲', category='科技'),
            ContentArticle(article_id='b', title='文章乙', category='社会'),
            ContentCategory(name='科技'), ContentCategory(name='社会'), ClassicBook(book_id='book', title='测试名著')])
        self.db.flush()
        self.chapter = ClassicBookChapter(book_id='book', title='第一章', chapter_order=1, content='正文')
        self.db.add(self.chapter); self.db.commit()
        self.today = datetime.now(BEIJING).date()
        self.monday = self.today - timedelta(days=self.today.weekday())
        self.origin = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=20)
        app = FastAPI()
        app.include_router(weekly.router, prefix='/profile')
        app.include_router(profile.router, prefix='/profile')
        def database():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.headers = [{'Authorization': f'Bearer {create_access_token(u.id)}'} for u in self.users]

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def payload(self, offset=0, seconds=15, **kwargs):
        return ReadingActivityRequest(batch_id=str(uuid4()), kind='article', content_id='a',
            started_at=self.origin + timedelta(seconds=offset), ended_at=self.origin + timedelta(seconds=offset+seconds), **kwargs)

    def add(self, offset=0, seconds=15, user=0, **kwargs):
        payload = self.payload(offset, seconds, **kwargs)
        return record_activity(self.db, self.users[user], payload)

    def report(self, user=0, week=None):
        return build_report(self.db, self.users[user], week or self.monday)

    def test_article_reads_count_without_30_seconds_and_keep_measured_duration(self):
        self.add(seconds=14)
        self.assertEqual(self.report()['summary']['articles'], 1)
        self.add(offset=14, seconds=16)
        self.assertEqual(self.report()['summary']['articles'], 1)
        self.add(offset=30)
        report = self.report()
        self.assertEqual(report['summary']['articles'], 1)
        self.assertEqual(report['summary']['reading_seconds'], 45)
        self.assertEqual(sum(d['articles'] for d in report['days']), 1)

    def test_retry_and_cross_content_overlap_are_not_counted_twice(self):
        payload = self.payload()
        record_activity(self.db, self.users[0], payload)
        self.assertTrue(record_activity(self.db, self.users[0], payload)['duplicate'])
        other = self.payload(offset=10).model_copy(update={'content_id': 'b'})
        self.assertEqual(record_activity(self.db, self.users[0], other)['accepted_seconds'], 10)
        self.assertEqual(self.report()['summary']['reading_seconds'], 25)
        self.assertEqual(self.add(user=1)['accepted_seconds'], 15)

    def test_api_isolation_cache_headers_and_auth(self):
        for i in range(2):
            self.add(offset=15*i, user=0)
        self.db.add(UserAiUsageRecord(user_id=self.users[0].id, question='仅甲可见', sources='AI 问问'))
        self.db.commit()
        first = self.client.get('/profile/weekly-report', headers=self.headers[0])
        second = self.client.get(f'/profile/weekly-report?user_id={self.users[0].id}', headers=self.headers[1])
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers['cache-control'], 'private, no-store')
        self.assertEqual(first.headers['vary'], 'Authorization')
        self.assertEqual(first.json()['summary']['articles'], 1)
        self.assertEqual(second.json()['summary']['articles'], 0)
        self.assertNotIn('仅甲可见', second.text)
        self.assertEqual(self.client.get('/profile/weekly-report').status_code, 401)
        body = self.payload(offset=40).model_dump(mode='json')
        body['user_id'] = self.users[0].id
        self.assertEqual(self.client.post('/profile/reading-activity', json=body, headers=self.headers[1]).status_code, 422)

    def test_question_channels_and_no_80_record_limit(self):
        self.db.add_all([UserAiUsageRecord(user_id=self.users[0].id, question=f'问题{i}', sources='阿烬对话' if i % 2 else '见闻') for i in range(104)])
        self.db.add(UserAiUsageRecord(user_id=self.users[1].id, question='其他用户'))
        self.db.commit()
        report = self.report()
        self.assertEqual(len(report['questions']), 104)
        self.assertEqual(report['summary']['ask'], 52)
        self.assertEqual(report['summary']['ajin'], 52)
        self.assertNotIn('answer', report['questions'][0])

    def test_midnight_split_and_daily_vs_weekly_dedup(self):
        # Freeze only the ledger clock so this test works on any day of the week.
        origin = datetime.combine(self.monday + timedelta(days=1), datetime.min.time(), BEIJING) - timedelta(seconds=15)
        with patch('app.services.weekly_report.datetime') as clock:
            clock.now.return_value = origin + timedelta(days=1)
            clock.combine = datetime.combine
            for i in range(4):
                p = self.payload().model_copy(update={'started_at':origin+timedelta(seconds=15*i), 'ended_at':origin+timedelta(seconds=15*(i+1))})
                record_activity(self.db, self.users[0], p)
        report = self.report()
        self.assertEqual(report['days'][0]['reading_seconds'], 15)
        self.assertEqual(report['days'][1]['reading_seconds'], 45)
        self.assertEqual(report['summary']['articles'], 1)
        self.assertEqual(report['days'][0]['articles'], 1)
        self.assertEqual(report['days'][1]['articles'], 1)

    def test_existing_articles_merge_and_classic_progress_is_separate(self):
        self.db.add(UserBrowsingHistory(user_id=self.users[0].id, article_id='b', title='旧文章', visited_at=datetime.now()))
        self.db.add(UserReadingPosition(user_id=self.users[0].id, book_id='book', chapter_id=self.chapter.id, scroll_progress=80, updated_at=datetime.now()))
        self.db.commit()
        report = self.report()
        self.assertEqual(len(report['legacy']), 1)
        self.assertEqual(report['summary']['articles'], 1)
        self.assertEqual(report['articles'][0]['seconds'], 0)
        for i in range(2):
            p = self.payload(offset=i*15).model_copy(update={'kind':'classic','content_id':str(self.chapter.id),'book_id':'book','scroll_progress':40+i*10})
            record_activity(self.db, self.users[0], p)
        report = self.report()
        self.assertEqual(report['summary']['chapters'], 1)
        self.assertEqual(report['classics'][0]['scroll_progress'], 50)
        self.assertEqual(len(report['legacy']), 0)

    def test_clear_history_updates_only_current_users_report(self):
        self.add(user=0); self.add(user=1)
        response = self.client.delete('/profile/history', headers=self.headers[0])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.report()['summary']['reading_seconds'], 0)
        self.assertEqual(self.report(1)['summary']['reading_seconds'], 15)

    def test_history_and_measured_read_merge_once_in_charts_and_daily_counts(self):
        self.add(seconds=5)
        self.db.add_all([
            UserBrowsingHistory(user_id=self.users[0].id, article_id='a', title='文章甲', topic='科技', visited_at=datetime.now()),
            UserBrowsingHistory(user_id=self.users[0].id, article_id='b', title='文章乙', topic='社会', visited_at=datetime.now()),
            UserBrowsingHistory(user_id=self.users[1].id, article_id='private', title='其他人的记录', visited_at=datetime.now())])
        self.db.commit()
        report = self.report()
        self.assertEqual(report['summary']['articles'], 2)
        self.assertEqual(sum(d['articles'] for d in report['days']), 2)
        self.assertEqual(sum(t['count'] for t in report['topics']), 2)
        self.assertEqual(report['summary']['reading_seconds'], 5)
        self.assertEqual(report['legacy'], [])
        self.assertNotIn('其他人的记录', str(report))

    def test_history_writes_daily_records_and_keeps_prior_weeks_on_revisit(self):
        previous = self.monday - timedelta(days=7)
        self.db.add(ArticleReadingDay(user_id=self.users[0].id, article_id='a', content_date=previous, title='文章甲', topic='科技'))
        self.db.commit()
        for _ in range(2):
            response = self.client.post('/profile/history', headers=self.headers[0], json={'article_id':'a'})
            self.assertEqual(response.status_code, 201)
        self.db.expire_all()
        self.assertEqual(self.db.query(ArticleReadingDay).filter_by(user_id=self.users[0].id).count(), 2)
        self.assertEqual(self.report(week=previous)['summary']['articles'], 1)
        self.assertEqual(self.report()['summary']['articles'], 1)
        self.assertEqual(self.report()['summary']['reading_seconds'], 0)
        self.client.delete('/profile/history', headers=self.headers[0])
        self.assertEqual(self.report(week=previous)['summary']['articles'], 0)
        self.assertEqual(self.report()['summary']['articles'], 0)

    def test_invalid_and_deleted_content(self):
        for update in [{'content_id':'missing'}, {'kind':'classic','book_id':'other','content_id':str(self.chapter.id)},
                       {'kind':'classic','book_id':'book','content_id':'not-an-id'}]:
            body = self.payload().model_copy(update=update).model_dump(mode='json')
            self.assertIn(self.client.post('/profile/reading-activity', json=body, headers=self.headers[0]).status_code, [404,422])
        body = self.payload().model_dump(mode='json')
        body['ended_at'] = (self.origin+timedelta(seconds=60)).isoformat()
        self.assertEqual(self.client.post('/profile/reading-activity', json=body, headers=self.headers[0]).status_code,422)
        body['ended_at'] = self.origin.isoformat()
        self.assertEqual(self.client.post('/profile/reading-activity', json=body, headers=self.headers[0]).status_code,422)
        body = self.payload().model_dump(mode='json'); body['started_at']='2026-10-17T00:00:00'
        self.assertEqual(self.client.post('/profile/reading-activity', json=body, headers=self.headers[0]).status_code,422)

    def test_week_validation_and_year_boundary(self):
        self.assertEqual(self.client.get('/profile/weekly-report?week_start=2025-12-29', headers=self.headers[0]).json()['week_end'], '2026-01-04')
        for value in ['2026-01-01','2099-01-05','invalid','1999-12-27']:
            self.assertEqual(self.client.get(f'/profile/weekly-report?week_start={value}',headers=self.headers[0]).status_code,422)
        empty = self.report(week=date(2025,12,29))
        self.assertEqual(len(empty['days']),7)
        self.assertEqual(empty['summary']['reading_seconds'],0)


if __name__ == '__main__':
    unittest.main()
