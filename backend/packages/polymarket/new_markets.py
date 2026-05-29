# -*- coding: utf-8 -*-
"""New Markets sub-pipeline: Fetch → AI filter → Upload.

Imported by pipeline.py — not meant to be run standalone.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any

import requests

from packages.common.paths import STATE_DIR, ensure_runtime_dirs
from packages.common.supabase_client import SupabaseClient
from packages.polymarket.latest_events.fetch_latest import fetch_latest_events
from packages.polymarket.new_markets_ai import NewMarketsFilterClient

# File to track slugs seen in previous runs (avoids re-sending rejected markets to AI)
_SEEN_SLUGS_FILE = STATE_DIR / "seen_new_slugs.json"


def _load_seen_slugs() -> set[str]:
    ensure_runtime_dirs()
    try:
        return set(json.loads(_SEEN_SLUGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_seen_slugs(slugs: set[str]) -> None:
    ensure_runtime_dirs()
    # Keep only last 2000 to avoid unbounded growth
    trimmed = sorted(slugs)[-2000:]
    _SEEN_SLUGS_FILE.write_text(json.dumps(trimmed, ensure_ascii=False), encoding="utf-8")


def fetch_new_events() -> list[dict]:
    """Reuse the Playwright scraper from latest_events/."""
    raw = fetch_latest_events()
    seen: set[str] = set()
    unique: list[dict] = []
    for item in raw:
        if item["slug"] not in seen:
            seen.add(item["slug"])
            unique.append(item)
    return unique


def _run_new_markets(sb: SupabaseClient, once: bool = False):

    # Step 1: Fetch
    print("[1/3] Fetching new markets from Polymarket /new ...")
    fetched = fetch_new_events()
    print(f"  Fetched {len(fetched)} unique markets")
    if not fetched:
        print("  No markets fetched.")
        return

    # Dedup: skip slugs already in Supabase OR already sent to AI in previous runs
    existing_slugs = sb.get_existing_new_market_slugs()
    seen_slugs = _load_seen_slugs()
    known = existing_slugs | seen_slugs
    truly_new = [m for m in fetched if m["slug"] not in known]
    print(f"  {len(fetched) - len(truly_new)} already seen, {len(truly_new)} truly new")

    if not truly_new:
        print("  Nothing new to process.")
        return

    # Filter by creationDate: only keep markets created within last 24h
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    fresh: list[dict] = []
    creation_dates: dict[str, str | None] = {}
    for m in truly_new:
        slug = m["slug"]
        try:
            resp = requests.get(
                f"https://gamma-api.polymarket.com/events/slug/{slug}",
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                cd = data.get("creationDate")
                if cd:
                    creation_dates[slug] = cd
                    created = datetime.fromisoformat(cd.replace("Z", "+00:00"))
                    if created >= cutoff:
                        fresh.append(m)
                        continue
                    else:
                        continue
            # If API fails, keep it (benefit of the doubt)
            fresh.append(m)
        except Exception:
            fresh.append(m)

    print(f"  {len(truly_new) - len(fresh)} older than 24h, {len(fresh)} fresh\n")

    if not fresh:
        print("  No fresh markets to process.")
        return

    if once:
        fresh = fresh[:5]
        print(f"  --once mode: processing only {len(fresh)} markets\n")

    # Step 2: AI filtering
    print(f"[2/3] Sending {len(fresh)} markets to Gemini for filtering...")
    gemini = NewMarketsFilterClient()
    result = gemini.filter_markets(fresh)
    selected = result.selected
    print(f"  AI selected {len(selected)} interesting markets")
    print(f"  Tokens: {result.usage}\n")

    # Record all slugs sent to AI (both selected and rejected) to avoid re-sending
    seen_slugs.update(m["slug"] for m in fresh)
    _save_seen_slugs(seen_slugs)

    if not selected:
        print("  AI found no interesting markets this round.")
        return

    # Step 3: Upload
    print(f"[3/3] Uploading {len(selected)} markets to Supabase...")
    batch_id = datetime.utcnow().isoformat()

    # Build lookup for url from fetched data
    url_map = {m["slug"]: m["url"] for m in fetched}

    rows = []
    for item in selected:
        slug = item.get("slug", "")
        created_at = creation_dates.get(slug)

        rows.append({
            "slug": slug,
            "question": item.get("question", ""),
            "url": url_map.get(slug, f"https://polymarket.com/event/{slug}"),
            "ai_analysis": {
                "question_zh": item.get("question_zh", ""),
                "reason": item.get("reason", ""),
                "appeal_tags": item.get("appeal_tags", []),
            },
            "created_at": created_at,
            "batch_id": batch_id,
        })

    uploaded = 0
    chunk_size = 10
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        try:
            sb.insert_new_markets(chunk)
            uploaded += len(chunk)
        except Exception as e:
            print(f"  chunk {i // chunk_size + 1} failed ({len(chunk)} rows): {e}")
            for row in chunk:
                try:
                    sb.insert_new_markets([row])
                    uploaded += 1
                except Exception as row_e:
                    print(f"    row failed slug={row.get('slug')}: {row_e}")
    print(f"  Uploaded {uploaded} rows")

    # Preview
    for i, r in enumerate(rows[:5], 1):
        tags = ", ".join(r["ai_analysis"]["appeal_tags"][:3])
        print(f"  {i}. [{tags}] {r['question'][:60]}")

    print("\n=== New Markets pipeline complete ===")


def run_new_markets(sb: SupabaseClient, once: bool = False):
    """Entry point called from pipeline.py."""
    print("\n" + "=" * 50)
    print("=== New Markets: Fetch → Filter → Upload ===\n")

    try:
        _run_new_markets(sb, once)
    except Exception as e:
        print(f"  New Markets pipeline error: {e}")
