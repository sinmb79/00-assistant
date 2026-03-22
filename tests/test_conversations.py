"""Tests for ConversationStore."""
from __future__ import annotations
from datetime import datetime
import pytest
from assistant_22b.storage.conversations import ConversationStore, ConversationTurn


@pytest.fixture
def store(tmp_path):
    return ConversationStore(
        db_path=tmp_path / "conv.db",
        key_path=tmp_path / ".conv_key",
    )


def test_append_and_retrieve(store):
    turn = ConversationTurn(role="user", content="안녕하세요", timestamp=datetime.now())
    store.append("session-1", turn)
    turns = store.get_session("session-1")
    assert len(turns) == 1
    assert turns[0].role == "user"
    assert turns[0].content == "안녕하세요"


def test_multiple_turns_ordered(store):
    t1 = ConversationTurn(role="user", content="질문", timestamp=datetime.now())
    t2 = ConversationTurn(role="assistant", content="답변", timestamp=datetime.now())
    store.append("s1", t1)
    store.append("s1", t2)
    turns = store.get_session("s1")
    assert turns[0].role == "user"
    assert turns[1].role == "assistant"


def test_sessions_are_isolated(store):
    store.append("s1", ConversationTurn(role="user", content="s1 msg", timestamp=datetime.now()))
    store.append("s2", ConversationTurn(role="user", content="s2 msg", timestamp=datetime.now()))
    assert len(store.get_session("s1")) == 1
    assert len(store.get_session("s2")) == 1
    assert store.get_session("s1")[0].content == "s1 msg"


def test_empty_session_returns_empty_list(store):
    assert store.get_session("nonexistent") == []


def test_persists_across_instances(tmp_path):
    db = tmp_path / "conv.db"
    key = tmp_path / ".key"
    s1 = ConversationStore(db_path=db, key_path=key)
    s1.append("x", ConversationTurn(role="user", content="hello", timestamp=datetime.now()))

    s2 = ConversationStore(db_path=db, key_path=key)
    turns = s2.get_session("x")
    assert len(turns) == 1
    assert turns[0].content == "hello"


def test_key_created_in_parent_dir(tmp_path):
    key_path = tmp_path / "nested" / ".key"
    store = ConversationStore(db_path=tmp_path / "c.db", key_path=key_path)
    store.append("s", ConversationTurn(role="user", content="x", timestamp=datetime.now()))
    assert key_path.exists()
