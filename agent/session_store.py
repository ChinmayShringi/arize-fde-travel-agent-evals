"""Session persistence behind a two-method interface (get/put).

Default: in-process dict, semantically identical to the shipped module-level
CONVERSATIONS dict. Set SESSION_STORE=sqlite to persist conversations across
restarts (the mock database the panel approved in Interview 1: "would you be
okay if I add a database?" / "Absolutely"). SQLite covers durability for the
demo; sharing sessions across multiple workers still needs a real database,
which stays in PRODUCTION_READINESS.md (D-11).

Messages may contain anthropic SDK content blocks (pydantic models). They are
serialized via model_dump(); the dict form is valid Messages API input, so a
round-trip through the store is behavior-preserving.
"""

import json
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _to_jsonable(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"not JSON-serializable: {type(obj).__name__}")


class DictStore:
    def __init__(self):
        self._sessions: dict[str, list] = {}

    def get(self, conversation_id: str) -> list:
        """Return a new list, never the stored one.

        SqliteStore.get deserializes a fresh list on every call. Handing out the
        internal list here would give the two backends different semantics for
        identical calling code: agent/api.py gets the history, appends the user
        message, and only persists via put(). Under the aliased version that
        append committed to the store before put(), so a failure mid-turn left a
        partial history behind on dict but not on sqlite.

        Shallow by design. Callers append whole messages and never mutate a
        message in place, so copying the list is enough to break the aliasing
        without deep-copying SDK content blocks on every turn.
        """
        return list(self._sessions.get(conversation_id, []))

    def put(self, conversation_id: str, messages: list) -> None:
        self._sessions[conversation_id] = messages


class SqliteStore:
    def __init__(self, path: str):
        import sqlite3

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, messages TEXT NOT NULL)"
        )
        self._conn.commit()

    def get(self, conversation_id: str) -> list:
        row = self._conn.execute(
            "SELECT messages FROM sessions WHERE id = ?", (conversation_id,)
        ).fetchone()
        return json.loads(row[0]) if row else []

    def put(self, conversation_id: str, messages: list) -> None:
        payload = json.dumps(messages, default=_to_jsonable)
        self._conn.execute(
            "INSERT INTO sessions (id, messages) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET messages = excluded.messages",
            (conversation_id, payload),
        )
        self._conn.commit()


def build_store():
    if os.getenv("SESSION_STORE") == "sqlite":
        path = os.getenv("SESSION_DB_PATH", str(_REPO_ROOT / "sessions.db"))
        return SqliteStore(path)
    return DictStore()
