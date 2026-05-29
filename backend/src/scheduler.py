# -*- coding: utf-8 -*-
"""OdailySeer scheduler for Polymarket data pipelines."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from packages.common.paths import LOG_DIR, ensure_runtime_dirs

PIPELINES = [
    ("Anomaly", "anomaly", "anomaly.log", 600),
    ("NewMarkets", "new-markets", "new_markets.log", 600),
    ("LateMarkets", "late-markets", "late_markets.log", 600),
    ("Whale", "whale", "whale.log", 5400),
]

MAX_RETRIES = 1
SCHEDULE_HOURS_BJ = [8, 10, 12, 14, 16, 18, 20, 22, 0]
WHALE_TRADES_INTERVAL = 20 * 60
WHALE_TRADES_PIPELINE = ("WhaleTrades", "whale-trades", "whale_trades.log", 120)


def run_subprocess(name: str, command: str, log_file: str, timeout: int, once: bool = False) -> bool:
    """Run a sub-pipeline as a separate Python process."""
    ensure_runtime_dirs()
    cmd = [sys.executable, "-m", "src.main", command]
    if once:
        cmd.append("--once")

    log_path = LOG_DIR / log_file
    print(f"  [{name}] Starting -> {log_path}")

    try:
        with log_path.open("a", encoding="utf-8") as lf:
            lf.write(f"\n{'=' * 50}\n[{datetime.now().isoformat()}] Run started\n{'=' * 50}\n")
            lf.flush()
            proc = subprocess.run(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                cwd=str(LOG_DIR.parents[2] / "backend"),
            )
        if proc.returncode == 0:
            print(f"  [{name}] Done (exit 0)")
            return True
        print(f"  [{name}] Failed (exit {proc.returncode})")
        return False
    except subprocess.TimeoutExpired:
        print(f"  [{name}] Timeout after {timeout}s")
        return False
    except Exception as exc:
        print(f"  [{name}] Error: {exc}")
        return False


def run_all(once: bool = False) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 50}")
    print(f"=== Scheduler run at {ts} ===\n")

    for name, command, log_file, timeout in PIPELINES:
        success = run_subprocess(name, command, log_file, timeout, once)
        if not success:
            for attempt in range(1, MAX_RETRIES + 1):
                print(f"  [{name}] Retry {attempt}/{MAX_RETRIES}...")
                time.sleep(5)
                success = run_subprocess(name, command, log_file, timeout, once)
                if success:
                    break
            if not success:
                print(f"  [{name}] Gave up after {MAX_RETRIES} retries")

    print("\n=== Scheduler run complete ===")


def _next_run_time(schedule_hours: list[int]) -> datetime:
    utc_now = datetime.now(timezone.utc)
    bj_tz = timezone(timedelta(hours=8))
    bj_now = utc_now.astimezone(bj_tz)

    for hour in sorted(schedule_hours):
        candidate = bj_now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > bj_now:
            return candidate.astimezone(None).replace(tzinfo=None)

    tomorrow = bj_now + timedelta(days=1)
    candidate = tomorrow.replace(hour=sorted(schedule_hours)[0], minute=0, second=0, microsecond=0)
    return candidate.astimezone(None).replace(tzinfo=None)


def _whale_trades_loop() -> None:
    name, command, log_file, timeout = WHALE_TRADES_PIPELINE
    while True:
        success = run_subprocess(name, command, log_file, timeout)
        if not success:
            time.sleep(5)
            run_subprocess(name, command, log_file, timeout)
        time.sleep(WHALE_TRADES_INTERVAL)


def run_scheduler(*, once: bool = False, loop: bool = False) -> None:
    if not loop:
        run_all(once=once)
        name, command, log_file, timeout = WHALE_TRADES_PIPELINE
        run_subprocess(name, command, log_file, timeout)
        return

    print(f"=== Schedule mode: Beijing time {SCHEDULE_HOURS_BJ} ===")
    print(f"=== Whale trades: every {WHALE_TRADES_INTERVAL // 60} min ===")

    thread = threading.Thread(target=_whale_trades_loop, daemon=True)
    thread.start()

    print("Running main pipelines immediately on startup...\n")
    run_all(once=once)

    while True:
        next_t = _next_run_time(SCHEDULE_HOURS_BJ)
        wait_secs = (next_t - datetime.now()).total_seconds()
        if wait_secs > 0:
            print(f"\nNext run at {next_t.strftime('%Y-%m-%d %H:%M')} (in {wait_secs / 3600:.1f}h)")
            time.sleep(wait_secs)
        run_all(once=once)
