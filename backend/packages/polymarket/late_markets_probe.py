#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe Polymarket events that are nearing resolution with meaningful volume."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from packages.common.paths import RUNTIME_DIR, ensure_runtime_dirs

API_URL = "https://gamma-api.polymarket.com/events"
MIN_VOLUME_USD = 100_000
WINDOW_DAYS = 30
PAGE_SIZE = 500
OUTPUT_FILE = RUNTIME_DIR / "late_markets_probe.json"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def fetch_late_events(
    min_volume_usd: float = MIN_VOLUME_USD,
    window_days: int = WINDOW_DAYS,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    end_max = now + timedelta(days=window_days)
    offset = 0
    matched: list[dict[str, Any]] = []

    while True:
        params = {
            "limit": PAGE_SIZE,
            "offset": offset,
            "active": "true",
            "closed": "false",
            "end_date_min": now.strftime("%Y-%m-%d"),
            "end_date_max": end_max.strftime("%Y-%m-%d"),
            "order": "volume",
            "ascending": "false",
        }
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        for event in batch:
            volume = _safe_float(event.get("volume"))
            if volume < min_volume_usd:
                continue

            matched.append(
                {
                    "event_id": str(event.get("id", "")),
                    "slug": event.get("slug", ""),
                    "title": event.get("title", ""),
                    "end_date": event.get("endDate"),
                    "volume_usd": volume,
                    "liquidity_usd": _safe_float(event.get("liquidity")),
                    "markets_count": len(event.get("markets") or []),
                    "category": _infer_category(event),
                    "url": f"https://polymarket.com/event/{event.get('slug', '')}",
                }
            )

        if len(batch) < PAGE_SIZE:
            break
        offset += len(batch)

    matched.sort(key=lambda item: (-item["volume_usd"], item["end_date"] or ""))
    return matched


def _infer_category(event: dict[str, Any]) -> str:
    tags = event.get("tags") or []
    for tag in tags:
        slug = (tag or {}).get("slug")
        if slug:
            return str(slug)
    return ""


def main() -> None:
    ensure_runtime_dirs()
    print(
        f"Scanning Polymarket events ending within {WINDOW_DAYS} days "
        f"with volume >= ${MIN_VOLUME_USD:,.0f}..."
    )
    rows = fetch_late_events()
    print(f"Matched {len(rows)} events")

    OUTPUT_FILE.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved to {OUTPUT_FILE}")

    for i, row in enumerate(rows[:20], 1):
        print(
            f"{i}. ${row['volume_usd']:,.0f} | {row['end_date']} | "
            f"{row['title'][:100]}"
        )


if __name__ == "__main__":
    main()
