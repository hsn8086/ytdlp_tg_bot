import sqlite3
import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, data_dir: Path):
        self.db_path = data_dir / "bot.db"
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_usage (
                    chat_id INTEGER,
                    date TEXT,
                    used_bytes INTEGER,
                    PRIMARY KEY (chat_id, date)
                )
            """)
            conn.commit()

    def get_today_usage(self, chat_id: int) -> int:
        today = datetime.date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT used_bytes FROM daily_usage WHERE chat_id = ? AND date = ?",
                (chat_id, today),
            )
            row = cursor.fetchone()
            return row[0] if row else 0

    def add_usage(self, chat_id: int, size_bytes: int) -> None:
        today = datetime.date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO daily_usage (chat_id, date, used_bytes)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id, date) DO UPDATE SET used_bytes = used_bytes + excluded.used_bytes
            """,
                (chat_id, today, size_bytes),
            )
            conn.commit()
