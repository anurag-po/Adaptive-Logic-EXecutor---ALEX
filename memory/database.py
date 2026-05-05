"""
ALEX — Memory Database (Phase 2)
SQLite-backed persistent memory with 3 tables:
  - conversations: user/assistant turns with intent + result metadata
  - preferences: learned and explicit user preferences
  - execution_log: every function call with timing and status

Includes 30-day auto-cleanup for conversations and execution logs.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from collections import Counter

import config
from utils.helpers import get_logger

logger = get_logger()


class MemoryDB:
    """
    Persistent memory layer for ALEX.
    Thread-safe via per-call connections (SQLite handles locking).
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path or config.MEMORY_DB_PATH
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_schema()
        self._cleanup_old_records()
        self._exec_count = 0

    # ═══════════════════════════════════════════════════════════════
    # SCHEMA INIT
    # ═══════════════════════════════════════════════════════════════

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    role        TEXT    NOT NULL,
                    content     TEXT    NOT NULL,
                    intent      TEXT,
                    function    TEXT,
                    result      TEXT,
                    session_id  TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    key         TEXT    PRIMARY KEY,
                    value       TEXT    NOT NULL,
                    source      TEXT    DEFAULT 'learned',
                    updated_at  TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS execution_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    function    TEXT    NOT NULL,
                    args        TEXT,
                    status      TEXT    NOT NULL,
                    duration_ms INTEGER,
                    output      TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_conv_session
                    ON conversations(session_id);
                CREATE INDEX IF NOT EXISTS idx_conv_timestamp
                    ON conversations(timestamp);
                CREATE INDEX IF NOT EXISTS idx_exec_function
                    ON execution_log(function);
            """)
        logger.info(f"Memory DB initialized: {self._db_path}")

    # ═══════════════════════════════════════════════════════════════
    # CONVERSATIONS
    # ═══════════════════════════════════════════════════════════════

    def save_turn(
        self,
        role: str,
        content: str,
        session_id: str,
        intent: str = None,
        function: str = None,
        result: str = None,
    ):
        """Save a conversation turn (user or assistant)."""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO conversations
                   (timestamp, role, content, intent, function, result, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    role,
                    content,
                    intent,
                    function,
                    result,
                    session_id,
                ),
            )

    def get_recent_turns(self, session_id: str, limit: int = 10) -> list[dict]:
        """Get the last N turns from the current session."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT role, content, intent, function, result
                   FROM conversations
                   WHERE session_id = ?
                   ORDER BY id DESC
                   LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        # Reverse so oldest first
        return [dict(r) for r in reversed(rows)]

    def get_last_turn(self, session_id: str) -> dict | None:
        """Get the most recent turn from the current session."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT role, content, intent, function, result
                   FROM conversations
                   WHERE session_id = ?
                   ORDER BY id DESC
                   LIMIT 1""",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_last_assistant_turn(self, session_id: str) -> dict | None:
        """Get the most recent assistant turn (for 'recall_last_action')."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT role, content, intent, function, result
                   FROM conversations
                   WHERE session_id = ? AND role = 'assistant'
                   ORDER BY id DESC
                   LIMIT 1""",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    # ═══════════════════════════════════════════════════════════════
    # PREFERENCES
    # ═══════════════════════════════════════════════════════════════

    def set_preference(self, key: str, value: str, source: str = "explicit"):
        """Set or update a user preference."""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO preferences (key, value, source, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(key)
                   DO UPDATE SET value=?, source=?, updated_at=?""",
                (
                    key, value, source, datetime.now().isoformat(),
                    value, source, datetime.now().isoformat(),
                ),
            )
        logger.info(f"Preference set: {key}={value} (source={source})")

    def get_preference(self, key: str) -> str | None:
        """Get a user preference value."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM preferences WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def get_all_preferences(self) -> dict[str, str]:
        """Get all user preferences as a dict."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT key, value FROM preferences"
            ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ═══════════════════════════════════════════════════════════════
    # EXECUTION LOG
    # ═══════════════════════════════════════════════════════════════

    def log_execution(
        self,
        function: str,
        args: dict,
        status: str,
        duration_ms: int = 0,
        output: str = "",
    ):
        """Log a function execution with timing."""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO execution_log
                   (timestamp, function, args, status, duration_ms, output)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    function,
                    json.dumps(args),
                    status,
                    duration_ms,
                    output,
                ),
            )
        self._exec_count += 1

        # Periodically analyze patterns for preference learning
        if self._exec_count % config.PREFERENCE_LEARN_INTERVAL == 0:
            self._analyze_patterns()

    def get_frequently_used(self, limit: int = 5) -> list[tuple[str, int]]:
        """Get the most frequently used functions."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT function, COUNT(*) as cnt
                   FROM execution_log
                   WHERE status = 'success'
                   GROUP BY function
                   ORDER BY cnt DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [(r["function"], r["cnt"]) for r in rows]

    # ═══════════════════════════════════════════════════════════════
    # PREFERENCE LEARNING
    # ═══════════════════════════════════════════════════════════════

    def _analyze_patterns(self):
        """
        Analyze execution history to learn user preferences.
        Runs automatically every PREFERENCE_LEARN_INTERVAL executions.
        """
        logger.debug("Analyzing usage patterns for preference learning...")

        with self._get_conn() as conn:
            # Learn preferred browser from open_app calls
            browser_rows = conn.execute(
                """SELECT args FROM execution_log
                   WHERE function = 'open_app' AND status = 'success'
                   ORDER BY id DESC LIMIT 20"""
            ).fetchall()

            if browser_rows:
                app_names = []
                for r in browser_rows:
                    try:
                        args = json.loads(r["args"])
                        name = args.get("app_name", "").lower()
                        if name in ("chrome", "google chrome", "firefox", "edge",
                                    "microsoft edge", "brave"):
                            app_names.append(name)
                    except (json.JSONDecodeError, KeyError):
                        pass
                if app_names:
                    most_common = Counter(app_names).most_common(1)[0]
                    if most_common[1] >= 3:
                        self.set_preference(
                            "preferred_browser", most_common[0], "learned"
                        )

            # Learn preferred screenshot save path
            ss_rows = conn.execute(
                """SELECT args FROM execution_log
                   WHERE function = 'screenshot_desktop' AND status = 'success'
                   ORDER BY id DESC LIMIT 10"""
            ).fetchall()

            if ss_rows:
                paths = []
                for r in ss_rows:
                    try:
                        args = json.loads(r["args"])
                        p = args.get("save_path", "")
                        if p:
                            paths.append(os.path.dirname(p))
                    except (json.JSONDecodeError, KeyError):
                        pass
                if paths:
                    most_common = Counter(paths).most_common(1)[0]
                    if most_common[1] >= 3:
                        self.set_preference(
                            "screenshot_path", most_common[0], "learned"
                        )

            # Learn most frequent action
            freq = self.get_frequently_used(1)
            if freq and freq[0][1] >= 5:
                self.set_preference(
                    "frequent_action", freq[0][0], "learned"
                )

    # ═══════════════════════════════════════════════════════════════
    # ANALYTICS (Phase 3)
    # ═══════════════════════════════════════════════════════════════

    def get_session_stats(self, session_id: str) -> dict:
        """
        Get aggregate stats for a session.
        Returns: total_commands, success_count, error_count, avg_duration_ms
        """
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT
                       COUNT(*) as total,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                       SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                       AVG(duration_ms) as avg_ms
                   FROM execution_log
                   WHERE timestamp >= (
                       SELECT MIN(timestamp) FROM conversations
                       WHERE session_id = ?
                   )""",
                (session_id,),
            ).fetchone()

        if row and row["total"]:
            return {
                "total_commands": row["total"],
                "success_count": row["success"] or 0,
                "error_count": row["errors"] or 0,
                "avg_duration_ms": row["avg_ms"] or 0,
            }
        return {
            "total_commands": 0,
            "success_count": 0,
            "error_count": 0,
            "avg_duration_ms": 0,
        }

    def get_error_rate(self) -> float:
        """Get the overall error rate as a percentage."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT
                       COUNT(*) as total,
                       SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                   FROM execution_log"""
            ).fetchone()

        if row and row["total"] and row["total"] > 0:
            return (row["errors"] or 0) / row["total"] * 100
        return 0.0

    # ═══════════════════════════════════════════════════════════════
    # CLEANUP
    # ═══════════════════════════════════════════════════════════════

    def _cleanup_old_records(self):
        """Remove records older than MAX_HISTORY_DAYS."""
        cutoff = (
            datetime.now() - timedelta(days=config.MAX_HISTORY_DAYS)
        ).isoformat()

        with self._get_conn() as conn:
            deleted_conv = conn.execute(
                "DELETE FROM conversations WHERE timestamp < ?", (cutoff,)
            ).rowcount
            deleted_exec = conn.execute(
                "DELETE FROM execution_log WHERE timestamp < ?", (cutoff,)
            ).rowcount

        if deleted_conv or deleted_exec:
            logger.info(
                f"Cleanup: removed {deleted_conv} old conversations, "
                f"{deleted_exec} old execution logs "
                f"(older than {config.MAX_HISTORY_DAYS} days)"
            )
