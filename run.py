"""Cross-platform Botify launcher.

Use this file when shell-specific environment variable syntax is confusing:

    python run.py dashboard
    python run.py backtest --source synthetic --limit 1000
    python run.py smoke
    python run.py test
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_help_text())
        return 0

    command, command_args = args[0].lower(), args[1:]
    if command in {"dashboard", "app", "server"}:
        return _run_dashboard(command_args)
    if command in {"backtest", "bt"}:
        return _run_backtest(command_args)
    if command in {"smoke", "check"}:
        return _run_smoke_check()
    if command in {"test", "tests", "pytest"}:
        return _run_tests(command_args)

    print(f"Unknown command: {command}", file=sys.stderr)
    print(_help_text(), file=sys.stderr)
    return 2


def _run_dashboard(args: list[str]) -> int:
    from botify.app import run

    host = "127.0.0.1"
    port = 5000
    remaining = list(args)
    while remaining:
        option = remaining.pop(0)
        if option == "--host" and remaining:
            host = remaining.pop(0)
        elif option == "--port" and remaining:
            port = int(remaining.pop(0))
        else:
            raise SystemExit(f"Unsupported dashboard option: {option}")
    run(host=host, port=port)
    return 0


def _run_backtest(args: list[str]) -> int:
    from botify.backtest import main as backtest_main

    previous_argv = sys.argv
    sys.argv = ["botify.backtest", *args]
    try:
        backtest_main()
    finally:
        sys.argv = previous_argv
    return 0


def _run_smoke_check() -> int:
    from botify.config import BotConfig
    from botify.engine import GridEngine
    from botify.market import DeterministicPriceFeed

    engine = GridEngine(BotConfig())
    feed = DeterministicPriceFeed()
    for _ in range(30):
        engine.on_price(feed.latest_price())

    snapshot = engine.snapshot()
    print("Botify smoke check passed")
    print(f"Symbol: {snapshot['config']['symbol']}")
    print(f"Ticks: {snapshot['tick_count']}")
    print(f"Mode: {snapshot['mode']}")
    return 0


def _run_tests(args: list[str]) -> int:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) if not existing_pythonpath else f"{SRC}{os.pathsep}{existing_pythonpath}"
    return subprocess.call([sys.executable, "-m", "pytest", *args], cwd=ROOT, env=env)


def _help_text() -> str:
    return """Botify cross-platform launcher

Usage:
  python run.py dashboard [--host 127.0.0.1] [--port 5000]
  python run.py backtest [backtest options]
  python run.py smoke
  python run.py test [pytest options]

Examples:
  python run.py dashboard
  python run.py backtest --source synthetic --limit 1000
  python run.py backtest --source synthetic --trading-bias LONG --limit 1000
  python run.py test -q

PowerShell note:
  The Unix form `PYTHONPATH=src python ...` does not work in PowerShell.
  Use this launcher instead, or set `$env:PYTHONPATH="src"` before running python.
"""


if __name__ == "__main__":
    raise SystemExit(main())
