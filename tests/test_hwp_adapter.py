"""Tests for HwpAdapter — all tests use mocks (COM requires Hanword running)."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from assistant_22b.hwp.adapter import HwpAdapter


def test_is_available_true_when_module_importable(monkeypatch):
    monkeypatch.setattr("assistant_22b.hwp.adapter._hwp_controller_class", lambda: MagicMock)
    adapter = HwpAdapter()
    assert adapter.is_available() is True


def test_is_available_false_when_import_fails(monkeypatch):
    monkeypatch.setattr(
        "assistant_22b.hwp.adapter._hwp_controller_class",
        lambda: (_ for _ in ()).throw(ImportError("no pywin32")),
    )
    adapter = HwpAdapter()
    assert adapter.is_available() is False


def test_connect_returns_false_when_import_fails(monkeypatch):
    monkeypatch.setattr(
        "assistant_22b.hwp.adapter._hwp_controller_class",
        lambda: (_ for _ in ()).throw(ImportError("no pywin32")),
    )
    adapter = HwpAdapter()
    assert adapter.connect() is False


def test_run_correction_before_connect_returns_error():
    adapter = HwpAdapter()
    result = adapter.run_correction()
    assert result["success"] is False
    assert "Not connected" in result["error"]


def test_connect_and_run_correction(monkeypatch):
    mock_ctrl = MagicMock()
    mock_bridge = MagicMock()
    mock_bridge.run_correction.return_value = [{"item": "교정"}]

    monkeypatch.setattr("assistant_22b.hwp.adapter._hwp_controller_class", lambda: mock_ctrl.__class__)
    monkeypatch.setattr("assistant_22b.hwp.adapter._hwp_bridge_class", lambda: mock_bridge.__class__)
    monkeypatch.setattr("assistant_22b.hwp.adapter._load_rules_fn", lambda: (lambda: []))

    adapter = HwpAdapter()
    # Inject pre-built bridge directly (simulates successful connect)
    adapter._bridge = mock_bridge

    result = adapter.run_correction("track_changes")
    assert result["success"] is True
    mock_bridge.run_correction.assert_called_once_with("track_changes")


def test_run_correction_returns_error_on_exception(monkeypatch):
    mock_bridge = MagicMock()
    mock_bridge.run_correction.side_effect = RuntimeError("HWP not responding")
    adapter = HwpAdapter()
    adapter._bridge = mock_bridge
    result = adapter.run_correction()
    assert result["success"] is False
    assert "HWP not responding" in result["error"]


def test_disconnect_clears_bridge():
    adapter = HwpAdapter()
    adapter._bridge = MagicMock()
    adapter._controller = MagicMock()
    adapter.disconnect()
    assert adapter._bridge is None
    assert adapter._controller is None
