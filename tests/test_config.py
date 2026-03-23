"""Tests for ConfigManager."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from assistant_22b.config import AssistantConfig, ConfigManager


def test_default_config_has_expected_values(tmp_path):
    cfg = ConfigManager(config_path=tmp_path / "config.json")
    assert cfg.config.llm_mode == "none"
    assert cfg.config.hotkey == "ctrl+shift+g"
    assert cfg.config.llm_provider == "claude"


def test_save_creates_file(tmp_path):
    path = tmp_path / "config.json"
    cfg = ConfigManager(config_path=path)
    cfg.save()
    assert path.exists()


def test_save_and_reload(tmp_path):
    path = tmp_path / "config.json"
    cfg = ConfigManager(config_path=path)
    cfg.config.llm_mode = "external"
    cfg.config.llm_provider = "openai"
    cfg.save()

    cfg2 = ConfigManager(config_path=path)
    assert cfg2.config.llm_mode == "external"
    assert cfg2.config.llm_provider == "openai"


def test_partial_json_uses_defaults(tmp_path):
    """Unknown keys are ignored; missing keys use defaults."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"llm_mode": "local", "unknown_key": "x"}), encoding="utf-8")
    cfg = ConfigManager(config_path=path)
    assert cfg.config.llm_mode == "local"
    assert cfg.config.hotkey == "ctrl+shift+g"


def test_save_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "dir" / "config.json"
    cfg = ConfigManager(config_path=path)
    cfg.save()
    assert path.exists()


def test_update_config_field(tmp_path):
    cfg = ConfigManager(config_path=tmp_path / "config.json")
    cfg.config.llm_model_path = "/models/llama.gguf"
    assert cfg.config.llm_model_path == "/models/llama.gguf"


def test_task_check_interval_minutes_default(tmp_path):
    cfg = ConfigManager(config_path=tmp_path / "config.json")
    assert cfg.config.task_check_interval_minutes == 60


def test_task_check_interval_minutes_loads_from_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"task_check_interval_minutes": 30}', encoding="utf-8")
    cfg = ConfigManager(config_path=path)
    assert cfg.config.task_check_interval_minutes == 30
