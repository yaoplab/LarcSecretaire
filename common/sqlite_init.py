import sqlite3
import os
from typing import Optional
from .logger import log

_DB_FILENAME = "larcsecretaire.db"
_DB_PATH = None


def _resolve_db_path() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _DB_FILENAME)
        _DB_PATH = os.path.normpath(_DB_PATH)
    return _DB_PATH


_DDL = """
CREATE TABLE IF NOT EXISTS module_config (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class SQLiteInit:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def init(self) -> str:
        path = _resolve_db_path()
        log(f"SQLiteInit: {path}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_DDL)
            conn.commit()
            log("SQLiteInit: DDL ok")
        except Exception as e:
            log(f"SQLiteInit ERROR: {e}")
            raise
        finally:
            conn.close()
        return path

    def verify_tables(self) -> bool:
        path = _resolve_db_path()
        if not os.path.exists(path):
            log("SQLiteInit: db not found")
            return False
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        expected = ["module_config"]
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {r[0] for r in cur.fetchall()}
        conn.close()
        missing = [t for t in expected if t not in existing]
        if missing:
            log(f"SQLiteInit: missing tables: {missing}")
            return False
        return True

    def get_module_config(self, key: str) -> Optional[str]:
        path = _resolve_db_path()
        conn = sqlite3.connect(path)
        try:
            cur = conn.execute("SELECT value FROM module_config WHERE key = ?", (key,))
            r = cur.fetchone()
            return r[0] if r else None
        finally:
            conn.close()

    def set_module_config(self, key: str, value: str) -> None:
        path = _resolve_db_path()
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO module_config (key, value) VALUES (?, ?)",
                        (key, value))
            conn.commit()
        finally:
            conn.close()


sqlite_init = SQLiteInit()
