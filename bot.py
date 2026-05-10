"""Compatibility launcher for the Botify localhost dashboard.

Run this file if you prefer the old command:

    PYTHONPATH=. python bot.py
"""

from __future__ import annotations

from src.botify.app import run


if __name__ == "__main__":
    run()
