"""
Хранилище заказов и покупателей (SQLite, без внешних зависимостей).
Одна таблица заказов + таблица покупателей для быстрого доступа «мои покупки».
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import config

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    username        TEXT,
    full_name       TEXT,
    telegram_charge TEXT,             -- telegram_payment_charge_id (для возвратов)
    stars           INTEGER NOT NULL,
    status          TEXT NOT NULL,    -- paid | pending | demo
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);

CREATE TABLE IF NOT EXISTS buyers (
    user_id    INTEGER PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    starts     INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or config.db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ---------- покупатели ----------
    def touch_user(self, user_id: int) -> None:
        now = _now()
        self._conn.execute(
            """INSERT INTO buyers(user_id, first_seen, last_seen, starts) VALUES(?,?,?,1)
               ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen, starts=starts+1""",
            (user_id, now, now),
        )
        self._conn.commit()

    # ---------- заказы ----------
    def add_order(
        self,
        user_id: int,
        stars: int,
        status: str,
        telegram_charge: str | None = None,
        username: str | None = None,
        full_name: str | None = None,
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO orders(user_id, username, full_name, telegram_charge, stars, status, created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (user_id, username, full_name, telegram_charge, stars, status, _now()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def has_access(self, user_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM orders WHERE user_id=? AND status IN ('paid','demo','granted','free') LIMIT 1",
            (user_id,),
        ).fetchone()
        return row is not None

    def last_paid_charge(self, user_id: int) -> str | None:
        row = self._conn.execute(
            "SELECT telegram_charge FROM orders WHERE user_id=? AND status='paid' ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return row["telegram_charge"] if row else None

    def grant(self, user_id: int, stars: int = 0) -> int:
        return self.add_order(user_id, stars, "granted")

    def grant_free(self, user_id: int, username: str | None = None, full_name: str | None = None) -> int:
        """Бесплатный доступ для своих — без списания звёзд."""
        return self.add_order(user_id, 0, "free", username=username, full_name=full_name)

    # ---------- статистика ----------
    def stats(self) -> dict:
        c = self._conn
        paid = c.execute("SELECT COUNT(*) n, COALESCE(SUM(stars),0) s FROM orders WHERE status='paid'").fetchone()
        demo = c.execute("SELECT COUNT(*) n FROM orders WHERE status='demo'").fetchone()
        granted = c.execute("SELECT COUNT(*) n FROM orders WHERE status='granted'").fetchone()
        free = c.execute("SELECT COUNT(*) n FROM orders WHERE status='free'").fetchone()
        users = c.execute("SELECT COUNT(*) n FROM buyers").fetchone()
        today = c.execute(
            "SELECT COUNT(*) n FROM orders WHERE substr(created_at,1,10)=date('now') AND status='paid'"
        ).fetchone()
        return {
            "users": users["n"],
            "paid_orders": paid["n"],
            "stars": paid["s"],
            "demo_orders": demo["n"],
            "granted": granted["n"],
            "free_orders": free["n"],
            "paid_today": today["n"],
        }

    def recent(self, limit: int = 10) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def close(self) -> None:
        self._conn.close()


storage = Storage()
