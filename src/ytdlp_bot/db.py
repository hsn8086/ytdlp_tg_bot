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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    call_count INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_ad_stats (
                    date TEXT,
                    ad_title TEXT,
                    trigger_count INTEGER DEFAULT 0,
                    PRIMARY KEY (date, ad_title)
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

    def increment_call_count(self) -> None:
        today = datetime.date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO daily_stats (date, call_count) VALUES (?, 1)
                ON CONFLICT(date) DO UPDATE SET call_count = call_count + 1
                """,
                (today,),
            )
            conn.commit()

    def increment_ad_trigger(self, ad_title: str) -> None:
        today = datetime.date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO daily_ad_stats (date, ad_title, trigger_count) VALUES (?, ?, 1)
                ON CONFLICT(date, ad_title) DO UPDATE SET trigger_count = trigger_count + 1
                """,
                (today, ad_title),
            )
            conn.commit()

    def get_daily_report(self, date: str | None = None) -> dict:
        if date is None:
            date = datetime.date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT call_count FROM daily_stats WHERE date = ?", (date,)
            )
            row = cursor.fetchone()
            call_count = row[0] if row else 0

            cursor.execute(
                "SELECT ad_title, trigger_count FROM daily_ad_stats WHERE date = ? ORDER BY trigger_count DESC",
                (date,),
            )
            ad_stats = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(DISTINCT chat_id), COALESCE(SUM(used_bytes), 0) FROM daily_usage WHERE date = ?",
                (date,),
            )
            usage_row = cursor.fetchone()
            unique_users = usage_row[0] if usage_row else 0
            total_bytes = usage_row[1] if usage_row else 0

        return {
            "date": date,
            "call_count": call_count,
            "unique_users": unique_users,
            "total_bytes": total_bytes,
            "ad_stats": ad_stats,
        }
