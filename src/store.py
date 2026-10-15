"""SQLite-backed price-watch state store (stdlib only)."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now().isoformat()


class PriceWatchStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parent.parent / "data" / "price_watch.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS watches (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    target_price_jpy INTEGER,
                    condition TEXT NOT NULL DEFAULT 'lte',
                    drop_percentage REAL,
                    notification_channel TEXT NOT NULL DEFAULT 'log',
                    notification_destination TEXT,
                    check_interval_minutes INTEGER NOT NULL DEFAULT 60,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_price_jpy INTEGER,
                    initial_price_jpy INTEGER,
                    lowest_price_seen_jpy INTEGER,
                    last_checked_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS price_logs (
                    id TEXT PRIMARY KEY,
                    watch_id TEXT NOT NULL,
                    price_jpy INTEGER NOT NULL,
                    in_stock INTEGER NOT NULL DEFAULT 1,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (watch_id) REFERENCES watches(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_watches_user ON watches(user_id);
                CREATE INDEX IF NOT EXISTS idx_watches_active ON watches(is_active);
                CREATE INDEX IF NOT EXISTS idx_logs_watch ON price_logs(watch_id);
                """
            )

    def create_watch(self, user_id: str, url: str, title: str, platform: str,
                     target_price_jpy: int | None = None, condition: str = "lte",
                     drop_percentage: float | None = None,
                     notification_channel: str = "log",
                     notification_destination: str | None = None,
                     check_interval_minutes: int = 60) -> dict[str, Any]:
        wid = f"pw_{uuid.uuid4().hex[:12]}"
        now = _now()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO watches
                   (id, user_id, url, title, platform, target_price_jpy, condition,
                    drop_percentage, notification_channel, notification_destination,
                    check_interval_minutes, is_active, initial_price_jpy,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (wid, user_id, url, title, platform, target_price_jpy, condition,
                 drop_percentage, notification_channel, notification_destination,
                 check_interval_minutes, 1, None, now, now),
            )
        return self.get_watch(wid)

    def get_watch(self, wid: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM watches WHERE id = ?", (wid,)).fetchone()
            return self._row_to_dict(row) if row else None

    def list_watches(self, user_id: str | None = None, only_active: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM watches WHERE 1=1"
        params: list[Any] = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if only_active:
            query += " AND is_active = 1"
        query += " ORDER BY created_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def update_watch(self, wid: str, **fields: Any) -> dict[str, Any] | None:
        watch = self.get_watch(wid)
        if not watch:
            return None
        allowed = {
            "title", "target_price_jpy", "condition", "drop_percentage",
            "notification_channel", "notification_destination",
            "check_interval_minutes", "is_active",
        }
        sets: list[str] = []
        params: list[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            sets.append(f"{k} = ?")
            params.append(v)
        if not sets:
            return watch
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(wid)
        with self._conn() as conn:
            conn.execute(f"UPDATE watches SET {', '.join(sets)} WHERE id = ?", params)
        return self.get_watch(wid)

    def delete_watch(self, wid: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM watches WHERE id = ?", (wid,))
            return cur.rowcount > 0

    def record_price(self, wid: str, price_jpy: int, in_stock: bool) -> dict[str, Any]:
        watch = self.get_watch(wid)
        if not watch:
            return {}
        now = _now()
        initial = watch["initial_price_jpy"] if watch["initial_price_jpy"] is not None else price_jpy
        lowest = min(watch["lowest_price_seen_jpy"] or price_jpy, price_jpy)
        with self._conn() as conn:
            conn.execute(
                """UPDATE watches
                   SET last_price_jpy = ?, initial_price_jpy = ?,
                       lowest_price_seen_jpy = ?, last_checked_at = ?, updated_at = ?
                   WHERE id = ?""",
                (price_jpy, initial, lowest, now, now, wid),
            )
            lid = f"plog_{uuid.uuid4().hex[:12]}"
            conn.execute(
                "INSERT INTO price_logs (id, watch_id, price_jpy, in_stock, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (lid, wid, price_jpy, 1 if in_stock else 0, now),
            )
        return self.get_watch(wid)

    def get_price_history(self, wid: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM price_logs WHERE watch_id = ? ORDER BY recorded_at DESC LIMIT ?",
                (wid, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)