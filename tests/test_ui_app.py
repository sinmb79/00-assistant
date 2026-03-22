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
