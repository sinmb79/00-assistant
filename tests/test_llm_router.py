"""Tests for LLMRouter."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from assistant_22b.llm.router import LLMRouter


def test_mode_none_returns_empty_string():
    router = LLMRouter(mode="none")
    assert router.generate("hello") == ""


def test_unknown_mode_returns_empty_string():
    router = LLMRouter(mode="invalid")
    assert router.generate("hello") == ""


def test_external_mode_calls_cloud_runtime(monkeypatch):
    mock_runtime = MagicMock()
    mock_runtime.generate.return_value = "외부 LLM 응답"

    monkeypatch.setattr(
        "assistant_22b.llm.router.CloudLLMRuntime",
        lambda provider: mock_runtime,
    )
    router = LLMRouter(mode="external", provider="claude")
    result = router.generate("프롬프트")
    assert result == "외부 LLM 응답"
    mock_runtime.generate.assert_called_once()


def test_external_mode_returns_empty_on_import_error(monkeypatch):
    monkeypatch.setattr(
        "assistant_22b.llm.router._import_cloud_runtime",
        lambda: (_ for _ in ()).throw(ImportError("no module")),
    )
    router = LLMRouter(mode="external")
    assert router.generate("hello") == ""


def test_external_mode_returns_empty_on_exception(monkeypatch):
    mock_runtime = MagicMock()
    mock_runtime.generate.side_effect = RuntimeError("API error")
    monkeypatch.setattr(
        "assistant_22b.llm.router.CloudLLMRuntime",
        lambda provider: mock_runtime,
    )
    router = LLMRouter(mode="external")
    assert router.generate("hello") == ""


def test_local_mode_returns_empty_when_llama_not_installed(monkeypatch):
    # llama_cpp is not installed in test env — should degrade gracefully
    router = LLMRouter(mode="local", model_path="/nonexistent/model.gguf")
    assert router.generate("hello") == ""


def test_router_caches_cloud_runtime(monkeypatch):
    call_count = 0

    def make_runtime(provider):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        m.generate.return_value = "ok"
        return m

    monkeypatch.setattr("assistant_22b.llm.router.CloudLLMRuntime", make_runtime)
    router = LLMRouter(mode="external", provider="claude")
    router.generate("a")
    router.generate("b")
    assert call_count == 1
