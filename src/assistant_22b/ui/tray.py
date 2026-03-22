"""System tray icon for 22B Assistant (pystray)."""
from __future__ import annotations

import threading
from typing import Callable

import pystray
from PIL import Image, ImageDraw


def _make_icon_image(size: int = 64) -> Image.Image:
    """Generate a simple 22B icon image."""
    img = Image.new("RGB", (size, size), color=(30, 136, 229))
    draw = ImageDraw.Draw(img)
    # Draw a white "22" text-like mark
    margin = size // 8
    draw.rectangle([margin, margin, size - margin, size - margin], outline="white", width=3)
    return img


class TrayIcon:
    """
    System tray icon with show/hide/quit menu.

    Args:
        on_show: Callback invoked when user clicks "열기" (show window).
        on_quit: Callback invoked when user clicks "종료".
        tooltip: Tooltip text for the tray icon.
    """

    def __init__(
        self,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        tooltip: str = "22B Assistant",
    ) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._tooltip = tooltip
        self._icon: pystray.Icon | None = None

    def start(self) -> None:
        """Build and run the tray icon (blocking — run in a daemon thread)."""
        image = _make_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("열기", self._handle_show, default=True),
            pystray.MenuItem("종료", self._handle_quit),
        )
        self._icon = pystray.Icon("22b-assistant", image, self._tooltip, menu)
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def start_in_thread(self) -> threading.Thread:
        """Start tray icon in a daemon thread. Returns the thread."""
        t = threading.Thread(target=self.start, daemon=True, name="tray-thread")
        t.start()
        return t

    # ------------------------------------------------------------------
    def _handle_show(self, icon, item) -> None:  # noqa: ANN001
        self._on_show()

    def _handle_quit(self, icon, item) -> None:  # noqa: ANN001
        self.stop()
        self._on_quit()
