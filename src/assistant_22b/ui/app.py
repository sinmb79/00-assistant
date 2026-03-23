"""AssistantApp — wires PipelineExecutor + UI + storage + hotkey."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from assistant_22b.agents.registry import AgentRegistry
from assistant_22b.config import AssistantConfig, ConfigManager
from assistant_22b.hwp.adapter import HwpAdapter
from assistant_22b.pipeline.executor import PipelineExecutor
from assistant_22b.security.auditor import SecurityAuditor
from assistant_22b.storage.conversations import ConversationStore, ConversationTurn
from assistant_22b.storage.tasks import TaskStore

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
        (data / "db").mkdir(exist_ok=True)

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
        self._task_store = TaskStore(
            db_path=data / "db" / "tasks.db",
            key_path=data / ".tasks_key",
        )

        self._hwp = HwpAdapter()
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
    def run_hwp_correction(self, mode: str = "track_changes") -> dict:
        """
        Connect to Hanword and run document correction.
        Posts result to chat window if available.
        Returns {"success": bool, ...}.
        """
        if not self._hwp.is_available():
            return {"success": False, "error": "HWP not available — pywin32 미설치 또는 한글 미실행"}
        if not self._hwp.connect():
            return {"success": False, "error": "한글 COM 연결 실패 — 한글을 먼저 실행하세요"}
        result = self._hwp.run_correction(mode)
        # Post result to chat window from any thread safely
        if self._window and self._window._root:
            msg = "✅ 한글 교정 완료" if result["success"] else f"❌ 교정 실패: {result.get('error', '')}"
            self._window._root.after(0, lambda: self._window._append_message("한글 교정", msg, "assistant"))
        return result

    # ------------------------------------------------------------------
    def _poll_due_tasks(self) -> None:
        """Check for tasks due within 24 h and post a notification if found."""
        try:
            due = self._task_store.query_due_soon(hours=24)
        except Exception:
            return
        if due and self._window and self._window._root:
            titles = ", ".join(t["title"] for t in due[:3])
            suffix = f" 외 {len(due) - 3}건" if len(due) > 3 else ""
            msg = f"⏰ 마감 임박: {titles}{suffix}"
            self._window._root.after(
                0, lambda: self._window._append_message("일정 알림", msg, "assistant")
            )

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the application — tray in daemon thread, chat window on main thread."""
        import tkinter as tk

        from assistant_22b.ui.chat_window import ChatWindow
        from assistant_22b.ui.tray import TrayIcon

        root = tk.Tk()

        interval_ms = self._config_mgr.config.task_check_interval_minutes * 60 * 1000

        def _schedule_poll():
            self._poll_due_tasks()
            root.after(interval_ms, _schedule_poll)

        root.after(interval_ms, _schedule_poll)

        self._window = ChatWindow(on_send=self.process_message)
        self._window.build(root)

        self._tray = TrayIcon(
            on_show=self._window.reveal,
            on_quit=root.quit,
            on_hwp_correct=self.run_hwp_correction if self._hwp.is_available() else None,
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
