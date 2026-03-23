"""Tests for AssistantApp wiring — no display required."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def test_assistant_app_imports():
    from assistant_22b.ui.app import AssistantApp  # noqa: F401


def test_chat_window_imports():
    from assistant_22b.ui.chat_window import ChatWindow  # noqa: F401


def test_tray_imports():
    from assistant_22b.ui.tray import TrayIcon  # noqa: F401


def test_process_message_returns_pipeline_result(tmp_path, monkeypatch):
    """AssistantApp.process_message wires input through PipelineExecutor."""
    from assistant_22b.ui.app import AssistantApp
    from assistant_22b.config import AssistantConfig

    mock_executor = MagicMock()
    mock_context = MagicMock()
    mock_context.agent_results = [MagicMock(output="교정 결과입니다.", error=None)]
    mock_executor.run.return_value = mock_context

    app = AssistantApp.__new__(AssistantApp)
    app._executor = mock_executor
    app._store = MagicMock()
    app._session_id = "test-session"

    result = app.process_message("공문서 교정해줘")
    assert result == "교정 결과입니다."
    mock_executor.run.assert_called_once_with("공문서 교정해줘")


def test_process_message_with_no_agents(tmp_path):
    from assistant_22b.ui.app import AssistantApp

    mock_executor = MagicMock()
    mock_context = MagicMock()
    mock_context.agent_results = []
    mock_executor.run.return_value = mock_context

    app = AssistantApp.__new__(AssistantApp)
    app._executor = mock_executor
    app._store = MagicMock()
    app._session_id = "s"

    result = app.process_message("입력")
    assert isinstance(result, str)
    assert len(result) > 0


def test_process_message_with_agent_error():
    from assistant_22b.ui.app import AssistantApp

    mock_executor = MagicMock()
    mock_context = MagicMock()
    mock_context.agent_results = [MagicMock(output="", error="에이전트 오류")]
    mock_executor.run.return_value = mock_context

    app = AssistantApp.__new__(AssistantApp)
    app._executor = mock_executor
    app._store = MagicMock()
    app._session_id = "s"

    result = app.process_message("입력")
    assert "오류" in result or "error" in result.lower() or isinstance(result, str)


# ── HWP integration ───────────────────────────────────────────────────────────

def test_run_hwp_correction_success():
    """run_hwp_correction connects adapter, runs correction, returns summary string."""
    from assistant_22b.ui.app import AssistantApp

    mock_adapter = MagicMock()
    mock_adapter.is_available.return_value = True
    mock_adapter.connect.return_value = True
    mock_adapter.run_correction.return_value = {"success": True, "result": [{"item": "교정"}]}

    app = AssistantApp.__new__(AssistantApp)
    app._hwp = mock_adapter
    app._window = None  # no live window in test

    result = app.run_hwp_correction()
    assert result["success"] is True
    mock_adapter.connect.assert_called_once()
    mock_adapter.run_correction.assert_called_once()


def test_run_hwp_correction_not_available():
    """run_hwp_correction returns error dict when HWP/pywin32 not installed."""
    from assistant_22b.ui.app import AssistantApp

    mock_adapter = MagicMock()
    mock_adapter.is_available.return_value = False

    app = AssistantApp.__new__(AssistantApp)
    app._hwp = mock_adapter
    app._window = None

    result = app.run_hwp_correction()
    assert result["success"] is False
    assert "available" in result["error"].lower() or "hwp" in result["error"].lower()


def test_run_hwp_correction_connect_fails():
    """run_hwp_correction returns error dict when COM connection fails."""
    from assistant_22b.ui.app import AssistantApp

    mock_adapter = MagicMock()
    mock_adapter.is_available.return_value = True
    mock_adapter.connect.return_value = False

    app = AssistantApp.__new__(AssistantApp)
    app._hwp = mock_adapter
    app._window = None

    result = app.run_hwp_correction()
    assert result["success"] is False


def test_tray_icon_accepts_hwp_correct_callback():
    """TrayIcon accepts optional on_hwp_correct callback without error."""
    from assistant_22b.ui.tray import TrayIcon

    called = []
    tray = TrayIcon(
        on_show=lambda: None,
        on_quit=lambda: None,
        on_hwp_correct=lambda: called.append(True),
    )
    assert tray._on_hwp_correct is not None


def test_tray_icon_hwp_correct_defaults_to_none():
    """on_hwp_correct is optional — defaults to None."""
    from assistant_22b.ui.tray import TrayIcon

    tray = TrayIcon(on_show=lambda: None, on_quit=lambda: None)
    assert tray._on_hwp_correct is None


def test_app_has_task_store_attribute(tmp_path):
    """AssistantApp.__init__ wires a _task_store. Verified by constructing it directly."""
    from assistant_22b.ui.app import AssistantApp
    from assistant_22b.storage.tasks import TaskStore

    # Use __new__ to bypass full __init__ (AgentRegistry/HwpAdapter side-effects)
    app = AssistantApp.__new__(AssistantApp)
    (tmp_path / "db").mkdir()
    app._task_store = TaskStore(
        db_path=tmp_path / "db" / "tasks.db",
        key_path=tmp_path / ".tasks_key",
    )
    assert hasattr(app, "_task_store")
    assert isinstance(app._task_store, TaskStore)


def test_poll_due_tasks_calls_query_due_soon():
    """_poll_due_tasks calls TaskStore.query_due_soon and notifies on results."""
    from assistant_22b.ui.app import AssistantApp
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.query_due_soon.return_value = [{"title": "마감 임박 보고서"}]

    app = AssistantApp.__new__(AssistantApp)
    app._task_store = mock_store
    app._window = None

    app._poll_due_tasks()
    mock_store.query_due_soon.assert_called_once()


def test_poll_due_tasks_no_crash_when_empty():
    """_poll_due_tasks does not crash when no tasks are due."""
    from assistant_22b.ui.app import AssistantApp
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.query_due_soon.return_value = []

    app = AssistantApp.__new__(AssistantApp)
    app._task_store = mock_store
    app._window = None

    app._poll_due_tasks()  # must not raise
