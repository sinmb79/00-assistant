"""Tkinter chat window for 22B Assistant."""
from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext
from typing import Callable


class ChatWindow:
    """
    Simple tkinter chat window.

    Args:
        on_send: Callback(user_text: str) -> str  — processes user input and
                 returns the assistant's response string.
        title: Window title.
    """

    WINDOW_WIDTH = 600
    WINDOW_HEIGHT = 700

    def __init__(self, on_send: Callable[[str], str], title: str = "22B Assistant") -> None:
        self._on_send = on_send
        self._root: tk.Tk | None = None
        self._title = title

    # ------------------------------------------------------------------
    def build(self, root: tk.Tk) -> None:
        """Build widgets into *root* (allows embedding in existing Tk loop)."""
        self._root = root
        root.title(self._title)
        root.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        root.resizable(True, True)

        # Chat display
        self._chat_display = scrolledtext.ScrolledText(
            root, state="disabled", wrap="word", font=("Malgun Gothic", 11)
        )
        self._chat_display.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        # Input area
        input_frame = tk.Frame(root)
        input_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._input_box = tk.Text(input_frame, height=3, font=("Malgun Gothic", 11), wrap="word")
        self._input_box.pack(side="left", fill="x", expand=True)
        self._input_box.bind("<Return>", self._on_return)
        self._input_box.bind("<Shift-Return>", lambda e: None)  # allow newline with Shift+Enter

        send_btn = tk.Button(input_frame, text="전송", command=self._send, width=8)
        send_btn.pack(side="right", padx=(4, 0))

        # Tag styles
        self._chat_display.tag_config("user", foreground="#1565C0", font=("Malgun Gothic", 11, "bold"))
        self._chat_display.tag_config("assistant", foreground="#1B5E20")
        self._chat_display.tag_config("error", foreground="#B71C1C")

    def show(self) -> None:
        """Create Tk root and start the event loop (blocking)."""
        root = tk.Tk()
        self.build(root)
        root.mainloop()

    def hide(self) -> None:
        if self._root:
            self._root.withdraw()

    def reveal(self) -> None:
        if self._root:
            self._root.deiconify()
            self._root.lift()

    # ------------------------------------------------------------------
    def _on_return(self, event: tk.Event) -> str:
        if not event.state & 0x1:  # Shift not held → send
            self._send()
            return "break"
        return ""

    def _send(self) -> None:
        text = self._input_box.get("1.0", "end-1c").strip()
        if not text:
            return
        self._input_box.delete("1.0", "end")
        self._append_message("사용자", text, "user")
        try:
            response = self._on_send(text)
            self._append_message("AI", response, "assistant")
        except Exception as exc:
            self._append_message("오류", str(exc), "error")

    def _append_message(self, sender: str, text: str, tag: str) -> None:
        self._chat_display.config(state="normal")
        self._chat_display.insert("end", f"\n[{sender}]\n", tag)
        self._chat_display.insert("end", text + "\n")
        self._chat_display.config(state="disabled")
        self._chat_display.see("end")
