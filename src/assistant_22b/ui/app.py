"""AssistantApp — wires PipelineExecutor + UI + storage + hotkey."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from assistant_22b.agents.registry import AgentRegistry
from assistant_22b.config import AssistantConfig, ConfigManager
from assistant_22b.pipeline.executor import PipelineExecutor
from assistant_22b.security.auditor import SecurityAuditor
from assistant_22b.storage.conversations import ConversationStore, ConversationTurn

# Lazy UI imports to avoid Tk startup in headless environments
from datetime import datetime


_DATA_DIR = Path.home() / ".22b-assistant"
_AGENTS_DIR = Path(__file__).parent.parent / "agents"


class AssistantApp:
    """
    Main application controller.

    Lifecycle:
        app = AssistantApp()
        app.run()   # blocking — starts tray + chat window
    """

    def __init__(
        self,
        config_path: Path | None = None,
        agents_dir: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        data = data_dir or _DATA_DIR
        data.mkdir(parents=True, exist_ok=True)

        self._config_mgr = ConfigManager(config_path=config_path)
        self._session_id = str(uuid.uuid4())

        auditor = SecurityAuditor(
            db_path=data / "audit.db",
            key_path=data / ".audit_key",
        )
        registry = AgentRegistry(agents_dir=agents_dir or _AGENTS_DIR)
        self._executor = PipelineExecutor(auditor=auditor, registry=registry)
        self._store = ConversationStore(
            db_path=data / "conversations.db",
            key_path=data / ".conv_key",
        )

        self._window = None  # built lazily in run()
        self._tray = None

    # ------------------------------------------------------------------
    def process_message(self, text: str) -> str:
        """Run pipeline and return formatted response string."""
        from assistant_22b.storage.conversations import ConversationTurn

        # Persist user turn
        self._store.append(
            self._session_id,
            ConversationTurn(role="user", content=text, timestamp=datetime.now()),
        )

        context = self._executor.run(text)

        # Collect output from all agent results
        if not context.agent_results:
            response = "처리할 수 있는 에이전트가 없습니다."
        else:
            parts = []
            for result in context.agent_results:
                if result.error:
                    parts.append(f"[오류] {result.error}")
                elif result.output:
                    parts.append(result.output)
            response = "\n\n".join(parts) if parts else "결과가 없습니다."

        # Persist assistant turn
        self._store.append(
            self._session_id,
            ConversationTurn(role="assistant", content=response, timestamp=datetime.now()),
        )
        return response

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the application — tray in daemon thread, chat window on main thread."""
        import tkinter as tk

        from assistant_22b.ui.chat_window import ChatWindow
        from assistant_22b.ui.tray import TrayIcon

        root = tk.Tk()

        self._window = ChatWindow(on_send=self.process_message)
        self._window.build(root)

        self._tray = TrayIcon(
            on_show=self._window.reveal,
            on_quit=root.quit,
        )
        self._tray.start_in_thread()

        # Register global hotkey (ctrl+shift+g) to toggle window
        try:
            import keyboard
            hotkey = self._config_mgr.config.hotkey
            keyboard.add_hotkey(hotkey, self._toggle_window)
        except Exception:
            pass  # hotkey is best-effort

        root.protocol("WM_DELETE_WINDOW", self._window.hide)  # hide instead of close
        root.mainloop()

        # Cleanup
        if self._tray:
            self._tray.stop()

    def _toggle_window(self) -> None:
        if self._window and self._window._root:
            if self._window._root.state() == "withdrawn":
                self._window.reveal()
            else:
                self._window.hide()
