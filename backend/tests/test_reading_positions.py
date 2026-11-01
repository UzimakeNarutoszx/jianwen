import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.profile import get_reading_position, save_reading_position
from app.db.base import Base
from app.models.content import ClassicBook, ClassicBookChapter
from app.models.profile import UserReadingPosition
from app.models.user import User
from app.schemas.profile import ReadingPositionRequest


class ReadingPositionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.users = [User(phone=f"1380000000{i}", nickname=f"Reader {i}", password_hash="hash") for i in range(2)]
        self.db.add_all(self.users + [ClassicBook(book_id="one", title="One"), ClassicBook(book_id="two", title="Two")])
        self.db.flush()
        self.chapters = [ClassicBookChapter(book_id="one", title="One", chapter_order=1), ClassicBookChapter(book_id="two", title="Two", chapter_order=1)]
        self.db.add_all(self.chapters)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_position_is_per_user_and_per_book_and_updates_one_record(self):
        first, second = self.users
        one, two = self.chapters
        self.assertIsNone(get_reading_position("one", first, self.db))
        save_reading_position("one", ReadingPositionRequest(chapter_id=one.id, scroll_progress=25), first, self.db)
        save_reading_position("two", ReadingPositionRequest(chapter_id=two.id, scroll_progress=50), first, self.db)
        save_reading_position("one", ReadingPositionRequest(chapter_id=one.id, scroll_progress=80), first, self.db)
        self.assertEqual(get_reading_position("one", first, self.db).scroll_progress, 80)
        self.assertEqual(get_reading_position("two", first, self.db).scroll_progress, 50)
        self.assertIsNone(get_reading_position("one", second, self.db))
        self.assertEqual(self.db.query(UserReadingPosition).count(), 2)

    def test_cannot_save_a_chapter_from_another_book(self):
        with self.assertRaises(HTTPException) as raised:
            save_reading_position("one", ReadingPositionRequest(chapter_id=self.chapters[1].id), self.users[0], self.db)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(self.db.query(UserReadingPosition).count(), 0)

    def test_unknown_book_is_404_and_progress_bounds_are_validated(self):
        with self.assertRaises(HTTPException) as raised:
            get_reading_position("missing", self.users[0], self.db)
        self.assertEqual(raised.exception.status_code, 404)
        for progress in (-1, 101):
            with self.assertRaises(ValidationError):
                ReadingPositionRequest(chapter_id=1, scroll_progress=progress)


if __name__ == "__main__":
    unittest.main()
