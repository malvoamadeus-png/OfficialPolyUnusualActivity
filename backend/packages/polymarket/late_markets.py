#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Late Markets pipeline: discover high-volume events nearing resolution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests import HTTPError

from packages.common.supabase_client import SupabaseClient
from packages.polymarket.late_market_filters import is_excluded_late_market

API_URL = "https://gamma-api.polymarket.com/events"
MIN_VOLUME_USD = 100_000
WINDOW_DAYS = 30
PAGE_SIZE = 500


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _infer_category(event: dict[str, Any]) -> str:
    tags = event.get("tags") or []
    for tag in tags:
        slug = (tag or {}).get("slug")
        if slug:
            return str(slug)
    return ""


def _tag_slugs(event: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for tag in event.get("tags") or []:
        slug = (tag or {}).get("slug")
        if slug:
            out.append(str(slug))
    return out


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cleanup_stored_late_markets(sb: SupabaseClient, now: datetime) -> tuple[int, int]:
    expired_removed = 0
    filtered_removed = 0

    existing_rows = sb.get_late_markets()
    expired_slugs: list[str] = []
    filtered_slugs: list[str] = []

    for row in existing_rows:
        slug = str(row.get("slug") or "").strip()
        if not slug:
            continue

        end_at = _parse_datetime(str(row.get("end_date") or ""))
        if end_at is not None and end_at <= now:
            expired_slugs.append(slug)
            continue

        if is_excluded_late_market(
            title=str(row.get("title") or ""),
            category=str(row.get("category") or ""),
        ):
            filtered_slugs.append(slug)

    if expired_slugs:
        for i in range(0, len(expired_slugs), 200):
            sb.delete_late_markets_by_slugs(expired_slugs[i:i + 200])
        expired_removed = len(expired_slugs)

    if filtered_slugs:
        for i in range(0, len(filtered_slugs), 200):
            sb.delete_late_markets_by_slugs(filtered_slugs[i:i + 200])
        filtered_removed = len(filtered_slugs)

    return expired_removed, filtered_removed


def fetch_late_events(
    *,
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
            slug = str(event.get("slug") or "").strip()
            title = str(event.get("title") or "").strip()
            end_date = event.get("endDate")
            volume = _safe_float(event.get("volume"))
            category = _infer_category(event)
            tag_slugs = _tag_slugs(event)

            if not slug or not title or not end_date or volume < min_volume_usd:
                continue
            if is_excluded_late_market(
                title=title,
                category=category,
                tags=tag_slugs,
            ):
                continue

            matched.append(
                {
                    "event_id": str(event.get("id") or ""),
                    "slug": slug,
                    "title": title,
                    "end_date": end_date,
                    "volume_usd": volume,
                    "liquidity_usd": _safe_float(event.get("liquidity")),
                    "markets_count": len(event.get("markets") or []),
                    "category": category,
                    "url": f"https://polymarket.com/event/{slug}",
                }
            )

        if len(batch) < PAGE_SIZE:
            break
        offset += len(batch)

    matched.sort(key=lambda item: (item["end_date"], -item["volume_usd"], item["title"]))
    return matched


def _chunked_insert(sb: SupabaseClient, rows: list[dict[str, Any]]) -> int:
    uploaded = 0
    chunk_size = 50

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        try:
            sb.insert_late_markets(chunk)
            uploaded += len(chunk)
        except Exception as exc:
            print(f"  chunk {i // chunk_size + 1} failed ({len(chunk)} rows): {exc}")
            for row in chunk:
                try:
                    sb.insert_late_markets([row])
                    uploaded += 1
                except Exception as row_exc:
                    print(f"    row failed slug={row.get('slug')}: {row_exc}")

    return uploaded


def run_late_markets(sb: SupabaseClient, once: bool = False) -> None:
    print("\n" + "=" * 50)
    print("=== Late Markets: Fetch -> Upload ===\n")

    try:
        print(
            f"[1/2] Scanning events ending within {WINDOW_DAYS} days "
            f"with volume >= ${MIN_VOLUME_USD:,.0f} ..."
        )
        now = datetime.now(timezone.utc)
        expired_removed, filtered_removed = _cleanup_stored_late_markets(sb, now)
        if expired_removed or filtered_removed:
            print(
                "  Cleaned existing rows:"
                f" expired={expired_removed}, excluded={filtered_removed}"
            )

        rows = fetch_late_events()
        print(f"  Matched {len(rows)} events")

        if not rows:
            print("  No qualifying late markets found.")
            return

        existing_slugs = sb.get_existing_late_market_slugs()
        fresh_rows = [row for row in rows if row["slug"] not in existing_slugs]
        print(f"  {len(existing_slugs)} already stored, {len(fresh_rows)} new to insert")

        if once:
            fresh_rows = fresh_rows[:20]
            print(f"  --once mode: inserting at most {len(fresh_rows)} rows")

        if not fresh_rows:
            print("  Nothing new to upload.")
            return

        print(f"\n[2/2] Uploading {len(fresh_rows)} rows to Supabase...")
        uploaded = _chunked_insert(sb, fresh_rows)
        print(f"  Uploaded {uploaded} rows")

        for i, row in enumerate(fresh_rows[:5], 1):
            print(
                f"  {i}. {row['end_date']} | ${row['volume_usd']:,.0f} | "
                f"{row['title'][:80]}"
            )

        print("\n=== Late Markets pipeline complete ===")
    except HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            print("  Late Markets pipeline error: Supabase table late_markets not found.")
            print("  Apply supabase/migrations/006_late_markets.sql, then rerun this pipeline.")
            return
        print(f"  Late Markets pipeline error: {exc}")
    except Exception as exc:
        print(f"  Late Markets pipeline error: {exc}")
