"""Entry point: python -m assistant_22b"""
from __future__ import annotations


def main() -> None:
    from assistant_22b.ui.app import AssistantApp
    app = AssistantApp()
    app.run()


if __name__ == "__main__":
    main()
