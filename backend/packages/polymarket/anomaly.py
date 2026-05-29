#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone runner: Anomaly Detection pipeline."""

import math
import json
import time
from datetime import datetime, timedelta
from typing import Any

import requests

from packages.common.supabase_client import SupabaseClient

CATEGORIES = ["politics", "world", "sports", "crypto", "finance", "tech", "culture"]
LOG_ODDS_THRESHOLD = 0.8
DEDUP_HOURS = 48
MARKETS_PER_CATEGORY = 25
PRICE_HISTORY_INTERVAL = "1h"
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3


def _get_json(url: str, *, params: dict[str, Any] | None = None, timeout: int = REQUEST_TIMEOUT) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(0.8 * attempt)
    raise last_error or RuntimeError(f"GET failed: {url}")


def _fetch_price_history(token_id: str, start_ts: int, end_ts: int) -> list[dict[str, float]]:
    params = {
        "market": token_id,
        "startTs": start_ts,
        "endTs": end_ts,
        "interval": PRICE_HISTORY_INTERVAL,
        "fidelity": 60,
    }
    data = _get_json(
        "https://clob.polymarket.com/prices-history",
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    return data.get("history", []) or []


def fetch_all_markets():
    start_ts = int((datetime.now() - timedelta(days=7)).timestamp())
    end_ts = int(datetime.now().timestamp())
    all_markets = []
    for cat in CATEGORIES:
        try:
            markets = _get_json(
                "https://gamma-api.polymarket.com/markets",
                params={
                    "category": cat,
                    "active": "true",
                    "closed": "false",
                    "limit": MARKETS_PER_CATEGORY,
                },
                timeout=REQUEST_TIMEOUT,
            )
            valid = 0
            for m in markets:
                try:
                    token_ids = json.loads(m.get("clobTokenIds", "[]"))
                except (TypeError, json.JSONDecodeError):
                    continue
                if not token_ids:
                    continue
                try:
                    history = _fetch_price_history(str(token_ids[0]), start_ts, end_ts)
                except Exception:
                    continue
                if len(history) < 2:
                    continue
                m["category"] = cat
                m["history"] = history
                all_markets.append(m)
                valid += 1
            print(f"  {cat}: {valid} markets")
            time.sleep(0.5)
        except Exception as e:
            print(f"  {cat}: error - {e}")
    return all_markets


def log_odds(p):
    if p <= 0 or p >= 1:
        return None
    return math.log(p / (1 - p))


def detect_changes(markets):
    cutoff = int((datetime.now() - timedelta(days=7)).timestamp())
    changes = []
    for m in markets:
        market_id = m.get("id")
        if not market_id:
            continue
        history = m.get("history", [])
        pts = sorted([h for h in history if h.get("t", 0) >= cutoff], key=lambda h: h["t"])
        if len(pts) < 2:
            continue
        best = None
        for i in range(1, len(pts)):
            prev_t, prev_p = pts[i - 1]["t"], pts[i - 1]["p"]
            curr_t, curr_p = pts[i]["t"], pts[i]["p"]
            lo1, lo2 = log_odds(prev_p), log_odds(curr_p)
            if lo1 is None or lo2 is None:
                continue
            diff = abs(lo2 - lo1)
            if diff > LOG_ODDS_THRESHOLD and (best is None or diff > best["log_odds_diff"]):
                best = {
                    "market_id": market_id,
                    "slug": m.get("slug", ""),
                    "question": m.get("question", ""),
                    "category": m.get("category", ""),
                    "change_timestamp": curr_t,
                    "prev_timestamp": prev_t,
                    "prev_price": prev_p,
                    "curr_price": curr_p,
                    "log_odds_diff": diff,
                }
        if best:
            changes.append(best)
    return changes


def upload_changes(sb: SupabaseClient, changes: list[dict[str, Any]], chunk_size: int = 10) -> int:
    uploaded = 0
    for i in range(0, len(changes), chunk_size):
        chunk = changes[i:i + chunk_size]
        try:
            sb.upsert_changes(chunk)
            uploaded += len(chunk)
        except Exception as e:
            print(f"  chunk {i // chunk_size + 1} failed ({len(chunk)} rows): {e}")
            for row in chunk:
                try:
                    sb.upsert_changes([row])
                    uploaded += 1
                except Exception as row_e:
                    print(
                        f"    row failed market_id={row.get('market_id')} "
                        f"ts={row.get('change_timestamp')}: {row_e}"
                    )
    return uploaded


def run_anomaly() -> None:
    print("=== Anomaly: Fetch -> Detect -> Upload ===\n")

    print("[1/3] Fetching trending markets...")
    markets = fetch_all_markets()
    print(f"  Total: {len(markets)} markets\n")
    if not markets:
        print("No markets fetched.")
        return

    print("[2/3] Detecting probability anomalies...")
    changes = detect_changes(markets)
    print(f"  Found {len(changes)} anomalies (threshold={LOG_ODDS_THRESHOLD})\n")
    if not changes:
        print("No anomalies detected.")
        return

    print("[3/3] Uploading new changes to Supabase...")
    sb = SupabaseClient()
    recent_ids = sb.get_recent_market_ids(hours=DEDUP_HOURS)
    new_changes = [c for c in changes if c["market_id"] not in recent_ids]
    print(f"  {len(changes)} detected, {len(changes) - len(new_changes)} skipped, {len(new_changes)} new")

    if not new_changes:
        print("  Nothing new to upload.")
        return

    uploaded = upload_changes(sb, new_changes)
    print(f"  Uploaded {uploaded} rows")

    print("\n=== Anomaly pipeline complete ===")


def main():
    run_anomaly()


if __name__ == "__main__":
    main()
