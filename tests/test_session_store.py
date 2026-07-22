"""agent/session_store.py: in-memory by default, sqlite only when asked.

The shipped agent kept conversations in a module-level dict. build_store() has to
preserve that exactly when SESSION_STORE is unset, or the baseline stops being a
baseline. SESSION_STORE=sqlite is the opt-in durability path.

Every sqlite test writes to tmp_path. Nothing here touches the repo's
sessions.db, and the default-path test asserts the wiring without opening a
connection at all.
"""

import json

import pytest

from agent import session_store
from agent.session_store import DictStore, SqliteStore, build_store

MESSAGES = [
    {"role": "user", "content": "I need a hotel in Paris."},
    {"role": "assistant", "content": "Which dates?"},
]


class FakeContentBlock:
    """Stands in for an anthropic SDK content block: a pydantic-style object with
    model_dump(). The store must serialize these, since run_agent appends raw SDK
    blocks to the history."""

    def __init__(self, text: str):
        self._text = text

    def model_dump(self) -> dict:
        return {"type": "text", "text": self._text}


# --------------------------------------------------------------------------- #
# Backend selection
# --------------------------------------------------------------------------- #
class TestBuildStore:
    def test_default_is_the_in_memory_dict_store(self):
        assert isinstance(build_store(), DictStore)

    @pytest.mark.parametrize("value", ["", "0", "SQLITE", "sqlite3", "postgres", "true"])
    def test_only_the_exact_string_sqlite_opts_in(self, monkeypatch, value):
        """Anything else falls back to the shipped in-memory behavior rather
        than silently creating a database file."""
        monkeypatch.setenv("SESSION_STORE", value)
        assert isinstance(build_store(), DictStore)

    def test_sqlite_is_selected_and_honors_the_configured_path(
        self, monkeypatch, tmp_path
    ):
        db = tmp_path / "nested" / "sessions.db"
        monkeypatch.setenv("SESSION_STORE", "sqlite")
        monkeypatch.setenv("SESSION_DB_PATH", str(db))
        store = build_store()
        assert isinstance(store, SqliteStore)
        assert db.exists()  # parent directory is created on demand

    def test_default_sqlite_path_is_inside_the_repo(self, monkeypatch):
        """Asserted through a recorder instead of a real connection, so running
        the suite never leaves a sessions.db behind."""
        recorded = {}

        class Recorder:
            def __init__(self, path):
                recorded["path"] = path

        monkeypatch.setenv("SESSION_STORE", "sqlite")
        monkeypatch.setattr(session_store, "SqliteStore", Recorder)
        build_store()
        assert recorded["path"] == str(session_store._REPO_ROOT / "sessions.db")


# --------------------------------------------------------------------------- #
# Shared behavior
# --------------------------------------------------------------------------- #
@pytest.fixture(params=["dict", "sqlite"])
def store(request, tmp_path):
    if request.param == "dict":
        return DictStore()
    return SqliteStore(str(tmp_path / "sessions.db"))


class TestSharedContract:
    def test_unknown_conversation_returns_an_empty_list(self, store):
        assert store.get("never-seen") == []

    def test_put_then_get_round_trips(self, store):
        store.put("c1", MESSAGES)
        assert store.get("c1") == MESSAGES

    def test_put_overwrites_rather_than_appends(self, store):
        store.put("c1", MESSAGES)
        store.put("c1", [{"role": "user", "content": "different"}])
        assert store.get("c1") == [{"role": "user", "content": "different"}]

    def test_conversations_are_isolated_from_each_other(self, store):
        store.put("c1", MESSAGES)
        store.put("c2", [{"role": "user", "content": "other"}])
        assert store.get("c1") == MESSAGES
        assert len(store.get("c2")) == 1


# --------------------------------------------------------------------------- #
# DictStore
# --------------------------------------------------------------------------- #
class TestDictStore:
    def test_instances_do_not_share_state(self):
        a, b = DictStore(), DictStore()
        a.put("c1", MESSAGES)
        assert b.get("c1") == []

    def test_state_is_lost_on_a_new_instance(self):
        """In-process only. This is the shipped behavior and the reason
        SESSION_STORE=sqlite exists."""
        DictStore().put("c1", MESSAGES)
        assert DictStore().get("c1") == []

    def test_stored_list_is_the_callers_object_not_a_copy(self):
        """PINNED BEHAVIOR, and a divergence from SqliteStore: DictStore stores
        the caller's list by reference, so a later mutation of that list is
        visible through get() without a put(). SqliteStore serializes and cannot
        do this. See the handoff note."""
        store = DictStore()
        messages = list(MESSAGES)
        store.put("c1", messages)
        messages.append({"role": "user", "content": "appended after put"})
        assert len(store.get("c1")) == 3

    def test_sqlite_does_not_share_that_aliasing(self, tmp_path):
        store = SqliteStore(str(tmp_path / "sessions.db"))
        messages = list(MESSAGES)
        store.put("c1", messages)
        messages.append({"role": "user", "content": "appended after put"})
        assert len(store.get("c1")) == 2


# --------------------------------------------------------------------------- #
# SqliteStore
# --------------------------------------------------------------------------- #
class TestSqliteStore:
    def test_state_survives_a_new_connection_to_the_same_file(self, tmp_path):
        path = str(tmp_path / "sessions.db")
        SqliteStore(path).put("c1", MESSAGES)
        assert SqliteStore(path).get("c1") == MESSAGES

    def test_repeated_put_upserts_on_the_primary_key(self, tmp_path):
        path = str(tmp_path / "sessions.db")
        store = SqliteStore(path)
        for i in range(3):
            store.put("c1", [{"role": "user", "content": f"turn {i}"}])
        rows = store._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        assert rows[0] == 1
        assert store.get("c1") == [{"role": "user", "content": "turn 2"}]

    def test_sdk_content_blocks_are_serialized_via_model_dump(self, tmp_path):
        """run_agent appends `{"role": "assistant", "content": response.content}`
        where content is a list of SDK blocks. The dict form round-trips as valid
        Messages API input, so persistence is behavior-preserving."""
        store = SqliteStore(str(tmp_path / "sessions.db"))
        store.put(
            "c1",
            [{"role": "assistant", "content": [FakeContentBlock("hello")]}],
        )
        assert store.get("c1") == [
            {"role": "assistant", "content": [{"type": "text", "text": "hello"}]}
        ]

    def test_a_value_with_no_model_dump_fails_loudly(self, tmp_path):
        """Silently dropping an unserializable message would corrupt the session
        history. A TypeError naming the type is the correct failure."""
        store = SqliteStore(str(tmp_path / "sessions.db"))
        with pytest.raises(TypeError, match="not JSON-serializable: object"):
            store.put("c1", [{"role": "user", "content": object()}])

    def test_stored_payload_is_plain_json(self, tmp_path):
        store = SqliteStore(str(tmp_path / "sessions.db"))
        store.put("c1", MESSAGES)
        raw = store._conn.execute(
            "SELECT messages FROM sessions WHERE id = ?", ("c1",)
        ).fetchone()[0]
        assert json.loads(raw) == MESSAGES

    def test_unicode_survives_the_round_trip(self, tmp_path):
        """Fixture hotel names carry diacritics, and E1's accent folding depends
        on them arriving intact."""
        store = SqliteStore(str(tmp_path / "sessions.db"))
        store.put("c1", [{"role": "assistant", "content": "Hotel Lumière"}])
        assert store.get("c1")[0]["content"] == "Hotel Lumière"
