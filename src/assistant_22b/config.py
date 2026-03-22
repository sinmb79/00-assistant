"""AssistantConfig and ConfigManager — loads/saves ~/.22b-assistant/config.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class AssistantConfig:
    llm_mode: str = "none"          # "local" | "external" | "none"
    llm_model_path: str = ""        # path to local GGUF model
    llm_provider: str = "claude"    # "claude" | "openai" | "gemini"
    hotkey: str = "ctrl+shift+g"
    theme: str = "light"


class ConfigManager:
    """Loads and persists AssistantConfig as JSON."""

    DEFAULT_PATH: Path = Path.home() / ".22b-assistant" / "config.json"

    def __init__(self, config_path: Path | None = None) -> None:
        self._path = config_path or self.DEFAULT_PATH
        self._config = self._load()

    # ------------------------------------------------------------------
    @property
    def config(self) -> AssistantConfig:
        return self._config

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(asdict(self._config), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    def _load(self) -> AssistantConfig:
        if not self._path.exists():
            return AssistantConfig()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            valid_keys = {f.name for f in fields(AssistantConfig)}
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            return AssistantConfig(**filtered)
        except Exception:
            return AssistantConfig()
