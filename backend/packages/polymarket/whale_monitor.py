# -*- coding: utf-8 -*-
"""Whale Monitor: detect new accounts with large positions.

Criteria: active_days < 30, trades < 20, shares > 10,000, position_value >= $5,000.
Imported by pipeline.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import requests

from packages.common.paths import PROJECT_ROOT, STATE_DIR, ensure_runtime_dirs
from packages.common.supabase_client import SupabaseClient

QUEUE_STATE_FILE = STATE_DIR / "whale_holder_queue.json"
MARKET_TASK_CACHE_FILE = STATE_DIR / "whale_market_tasks.json"


def _load_env_file() -> None:
    for env_path in (
        Path.cwd() / ".env",
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "backend" / ".env",
        Path("/etc/odailyseer/odailyseer.env"),
    ):
        if not env_path.exists():
            continue
        try:
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip().lstrip("\ufeff")
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
            break
        except OSError:
            continue


def _env_int(name: str, default: int, min_value: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(float(raw))
    except ValueError:
        return default
    return max(min_value, value)


_load_env_file()

# Config. Keep the defaults conservative; override with WHALE_* env vars if needed.
TOP_EVENTS_LIMIT = _env_int("WHALE_TOP_EVENTS_LIMIT", 1_000, 1)
EVENT_WINDOW_DAYS = _env_int("WHALE_EVENT_WINDOW_DAYS", 180, 1)
EVENTS_PAGE_SIZE = _env_int("WHALE_EVENTS_PAGE_SIZE", 500, 1)
REQUESTS_PER_SECOND = _env_int("WHALE_REQUESTS_PER_SECOND", 6, 1)
MARKETS_PER_RUN = _env_int("WHALE_MARKETS_PER_RUN", 600, 1)
MIN_AMOUNT = _env_int("WHALE_MIN_AMOUNT", 10_000, 1)
MIN_POSITION_VALUE = _env_int("WHALE_MIN_POSITION_VALUE", 5_000, 1)
MAX_TRADES = _env_int("WHALE_MAX_TRADES", 20, 1)
MAX_ACTIVE_DAYS = _env_int("WHALE_MAX_ACTIVE_DAYS", 30, 1)
HOLDERS_LIMIT = _env_int("WHALE_HOLDERS_LIMIT", 5, 1)
DEDUP_HOURS = _env_int("WHALE_DEDUP_HOURS", 48, 1)
RETENTION_HOURS = _env_int("WHALE_RETENTION_HOURS", 48, 1)
MAX_WORKERS = _env_int("WHALE_MAX_WORKERS", 8, 1)
USER_STATS_DB_TTL_HOURS = _env_int("WHALE_USER_STATS_DB_TTL_HOURS", 24, 1)
MARKET_TASK_CACHE_TTL_HOURS = _env_int("WHALE_MARKET_TASK_CACHE_TTL_HOURS", 4, 0)
MIN_MARKET_VOLUME = _env_int("WHALE_MIN_MARKET_VOLUME", 10_000, 0)
MIN_MARKET_LIQUIDITY = _env_int("WHALE_MIN_MARKET_LIQUIDITY", 0, 0)
ONCE_MARKETS_LIMIT = _env_int("WHALE_ONCE_MARKETS_LIMIT", 100, 1)


# API helpers
class RequestRateLimiter:
    """Thread-safe limiter to keep outbound requests under N per second."""

    def __init__(self, max_per_second: int):
        self.max_per_second = max_per_second
        self._calls: deque[float] = deque()
        self._lock = Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= 1.0:
                    self._calls.popleft()

                if len(self._calls) < self.max_per_second:
                    self._calls.append(now)
                    return

                sleep_for = 1.0 - (now - self._calls[0])

            if sleep_for > 0:
                time.sleep(sleep_for)


REQUEST_LIMITER = RequestRateLimiter(REQUESTS_PER_SECOND)


def rate_limited_get(url: str, *, params: dict[str, Any] | None = None, timeout: int = 30) -> requests.Response:
    REQUEST_LIMITER.wait()
    return requests.get(url, params=params, timeout=timeout)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    ensure_runtime_dirs()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _now_ts() -> float:
    return time.time()


def _market_metric(market: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        if name in market:
            value = _safe_float(market.get(name), -1.0)
            if value >= 0:
                return value
    return None


def _market_passes_volume_filters(market: dict[str, Any]) -> bool:
    if MIN_MARKET_VOLUME > 0:
        volume = _market_metric(
            market,
            ("volumeNum", "volume", "volume24hr", "volume24hrClob", "volume1wk", "volume1mo"),
        )
        if volume is not None and volume < MIN_MARKET_VOLUME:
            return False

    if MIN_MARKET_LIQUIDITY > 0:
        liquidity = _market_metric(market, ("liquidityNum", "liquidity", "liquidityClob"))
        if liquidity is not None and liquidity < MIN_MARKET_LIQUIDITY:
            return False

    return True


def fetch_top_events(limit: int = TOP_EVENTS_LIMIT) -> list[dict]:
    """Fetch top events by volume ending within configured lookahead window."""
    today = datetime.now(timezone.utc)
    base_params = {
        "order": "volume",
        "ascending": "false",
        "end_date_min": today.strftime("%Y-%m-%d"),
        "end_date_max": (today + timedelta(days=EVENT_WINDOW_DAYS)).strftime("%Y-%m-%d"),
        "active": "true",
        "closed": "false",
    }
    events: list[dict] = []
    offset = 0

    while len(events) < limit:
        page_size = min(EVENTS_PAGE_SIZE, limit - len(events))
        params = {**base_params, "limit": page_size, "offset": offset}
        resp = rate_limited_get("https://gamma-api.polymarket.com/events", params=params, timeout=30)
        resp.raise_for_status()
        batch = resp.json()

        if not batch:
            break

        events.extend(batch)
        if len(batch) < page_size:
            break
        offset += len(batch)

    return events


def get_holders(condition_id: str) -> list[dict]:
    """Get top holders for a market."""
    resp = rate_limited_get(
        f"https://data-api.polymarket.com/holders?market={condition_id}&limit={HOLDERS_LIMIT}",
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_user_stats(address: str) -> dict[str, Any] | None:
    """Fetch trades + joinDate from Polymarket."""
    try:
        resp = rate_limited_get(
            f"https://data-api.polymarket.com/v1/user-stats?proxyAddress={address}",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None

        result: dict[str, Any] = {"trades": int(data.get("trades", 0))}
        join_date = data.get("joinDate")
        if join_date:
            joined = datetime.fromisoformat(join_date.replace("Z", "+00:00"))
            result["joined_ts"] = joined.timestamp()
            result["active_days"] = (datetime.now(timezone.utc) - joined).days
        return result
    except Exception:
        return None


def _build_market_tasks(events: list[dict]) -> tuple[list[str], dict[str, tuple[str, str, str, dict[str, tuple[str, float]]]]]:
    """Return ordered market ids + task map keyed by condition id."""
    order: list[str] = []
    tasks: dict[str, tuple[str, str, str, dict[str, tuple[str, float]]]] = {}

    for event in events:
        slug = event.get("slug", "")
        event_title = event.get("title", "")
        for market in event.get("markets", []):
            condition_id = market.get("conditionId")
            if not condition_id or condition_id in tasks:
                continue
            if not _market_passes_volume_filters(market):
                continue
            try:
                outcomes = json.loads(market.get("outcomes", "[]"))
                token_ids = json.loads(market.get("clobTokenIds", "[]"))
                prices = json.loads(market.get("outcomePrices", "[]"))
            except (json.JSONDecodeError, TypeError):
                continue

            token_meta: dict[str, tuple[str, float]] = {}
            for idx, token_id in enumerate(token_ids):
                token = str(token_id)
                side = outcomes[idx] if idx < len(outcomes) else "?"
                price = _safe_float(prices[idx]) if idx < len(prices) else 0.0
                token_meta[token] = (str(side), price)

            market_question = market.get("question", event_title)
            tasks[condition_id] = (slug, event_title, market_question, token_meta)
            order.append(condition_id)

    return order, tasks


def _load_queue_state() -> dict[str, Any]:
    data = _read_json(QUEUE_STATE_FILE, {})
    if not isinstance(data, dict):
        return {}
    return data


def _load_queue_ids(state: dict[str, Any] | None = None) -> list[str]:
    data = state if state is not None else _load_queue_state()
    ids = data.get("pending_ids", [])
    if not isinstance(ids, list):
        return []
    return [str(x) for x in ids if isinstance(x, str) and x]


def _save_queue_ids(ids: list[str], snapshot_key: str | None = None, completed: bool = False) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pending_ids": ids,
        "completed": completed,
    }
    if snapshot_key:
        payload["snapshot_key"] = snapshot_key
    _write_json(QUEUE_STATE_FILE, payload)


def _market_snapshot_key(market_ids: list[str]) -> str:
    digest = hashlib.sha1("\n".join(market_ids).encode("utf-8")).hexdigest()[:12]
    return f"{int(_now_ts())}:{len(market_ids)}:{digest}"


def _sync_queue(current_market_ids: list[str], snapshot_key: str) -> tuple[list[str], int, int]:
    """Keep pending queue and append new markets from latest snapshot.

    Returns: (pending_ids, added_count, dropped_count)
    """
    state = _load_queue_state()
    prev_snapshot_key = str(state.get("snapshot_key") or "")
    prev_pending = _load_queue_ids(state) if prev_snapshot_key == snapshot_key else []

    if prev_snapshot_key == snapshot_key and not prev_pending and state.get("completed"):
        return [], 0, 0

    current_set = set(current_market_ids)

    pending = [cid for cid in prev_pending if cid in current_set]
    dropped = len(prev_pending) - len(pending)

    seen = set(pending)
    added = 0
    for cid in current_market_ids:
        if cid not in seen:
            pending.append(cid)
            seen.add(cid)
            added += 1

    return pending, added, dropped


def _parse_iso_to_ts(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _load_market_tasks_cache() -> tuple[str, list[str], dict[str, tuple[str, str, str, dict[str, tuple[str, float]]]]] | None:
    if MARKET_TASK_CACHE_TTL_HOURS <= 0:
        return None

    data = _read_json(MARKET_TASK_CACHE_FILE, {})
    if not isinstance(data, dict):
        return None

    fetched_ts = _parse_iso_to_ts(data.get("fetched_at"))
    if fetched_ts is None or (_now_ts() - fetched_ts) > MARKET_TASK_CACHE_TTL_HOURS * 3600:
        return None

    snapshot_key = str(data.get("snapshot_key") or "")
    market_order = data.get("market_order", [])
    raw_tasks = data.get("market_tasks", {})
    if not snapshot_key or not isinstance(market_order, list) or not isinstance(raw_tasks, dict):
        return None

    tasks: dict[str, tuple[str, str, str, dict[str, tuple[str, float]]]] = {}
    for cid, raw_task in raw_tasks.items():
        if not isinstance(raw_task, dict):
            continue
        raw_token_meta = raw_task.get("token_meta", {})
        if not isinstance(raw_token_meta, dict):
            raw_token_meta = {}

        token_meta: dict[str, tuple[str, float]] = {}
        for token, raw_pair in raw_token_meta.items():
            if isinstance(raw_pair, list) and len(raw_pair) >= 2:
                token_meta[str(token)] = (str(raw_pair[0]), _safe_float(raw_pair[1]))

        tasks[str(cid)] = (
            str(raw_task.get("slug", "")),
            str(raw_task.get("event_title", "")),
            str(raw_task.get("market_question", "")),
            token_meta,
        )

    ordered_ids = [str(cid) for cid in market_order if str(cid) in tasks]
    if not ordered_ids:
        return None

    return snapshot_key, ordered_ids, tasks


def _save_market_tasks_cache(
    market_order: list[str],
    market_tasks: dict[str, tuple[str, str, str, dict[str, tuple[str, float]]]],
) -> str:
    snapshot_key = _market_snapshot_key(market_order)
    payload = {
        "version": 1,
        "snapshot_key": snapshot_key,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "market_order": market_order,
        "market_tasks": {
            cid: {
                "slug": task[0],
                "event_title": task[1],
                "market_question": task[2],
                "token_meta": {token: [side, price] for token, (side, price) in task[3].items()},
            }
            for cid, task in market_tasks.items()
        },
    }
    if MARKET_TASK_CACHE_TTL_HOURS > 0:
        _write_json(MARKET_TASK_CACHE_FILE, payload)
    return snapshot_key


def _build_stats_from_profile(profile: dict[str, Any], ttl_seconds: float) -> dict[str, Any] | None:
    fetched_ts = _parse_iso_to_ts(profile.get("last_fetched_at"))
    if fetched_ts is None or (_now_ts() - fetched_ts) > ttl_seconds:
        return None

    joined_ts = _parse_iso_to_ts(profile.get("join_date"))
    trades = int(profile.get("trades", 999))
    if joined_ts is not None:
        active_days = max(0, int((_now_ts() - joined_ts) // 86400))
    else:
        active_days = 999

    return {
        "trades": trades,
        "active_days": active_days,
        "joined_ts": joined_ts,
    }


# Core logic
def _run_whale_monitor(sb: SupabaseClient, once: bool = False):
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)).isoformat()
    try:
        sb.delete_old_whale_alerts(cutoff_iso)
        print(f"  Pruned whale_alerts older than {RETENTION_HOURS}h")
    except Exception as e:
        print(f"  whale_alert prune skipped: {e}")

    # Step 1: Build or reuse market tasks
    snapshot_key = "once"
    cached = None if once else _load_market_tasks_cache()

    if cached:
        snapshot_key, market_order, market_tasks = cached
        print(
            f"[1/3] Using cached market task snapshot "
            f"({len(market_tasks)} markets, ttl={MARKET_TASK_CACHE_TTL_HOURS}h)..."
        )
    else:
        events_limit = 5 if once else TOP_EVENTS_LIMIT
        print(f"[1/3] Fetching top {events_limit} events by volume (window {EVENT_WINDOW_DAYS}d)...")
        events = fetch_top_events(events_limit)
        print(f"  Got {len(events)} events")

        if not events:
            print("  No events found.")
            return

        market_order, market_tasks = _build_market_tasks(events)
        if not once:
            snapshot_key = _save_market_tasks_cache(market_order, market_tasks)

    print(
        f"  Market tasks: {len(market_tasks)} "
        f"(min_volume=${MIN_MARKET_VOLUME:,}, min_liquidity=${MIN_MARKET_LIQUIDITY:,})"
    )
    if not market_tasks:
        print("  No valid markets found.")
        return

    # Step 2: Scan holders (parallel)
    print("[2/3] Scanning holders for whale signals...")
    existing_keys = sb.get_recent_whale_keys(hours=DEDUP_HOURS)

    if once:
        batch_ids = market_order[: min(ONCE_MARKETS_LIMIT, len(market_order))]
        remaining_ids: list[str] = []
        print(f"  --once mode: processing {len(batch_ids)} markets")
    else:
        pending_ids, added_count, dropped_count = _sync_queue(market_order, snapshot_key)
        if not pending_ids:
            print("  Current market snapshot already completed; waiting for next cache refresh.")
            _save_queue_ids([], snapshot_key=snapshot_key, completed=True)
            return
        batch_size = min(MARKETS_PER_RUN, len(pending_ids))
        batch_ids = pending_ids[:batch_size]
        remaining_ids = pending_ids[batch_size:]
        print(
            f"  Queue status: pending={len(pending_ids)} | this_run={len(batch_ids)} | "
            f"added={added_count} | dropped={dropped_count}"
        )

    holder_tasks = []
    for cid in batch_ids:
        task = market_tasks.get(cid)
        if task:
            slug, event_title, market_question, token_meta = task
            holder_tasks.append((cid, slug, event_title, market_question, token_meta))

    if not holder_tasks:
        print("  No markets to process this round.")
        if not once:
            _save_queue_ids([], snapshot_key=snapshot_key, completed=True)
        return

    print(f"  {len(holder_tasks)} markets to scan, fetching holders ({MAX_WORKERS} threads)...")

    # Phase B: Parallel fetch holders
    def fetch_holder_task(task: tuple[str, str, str, str, dict[str, tuple[str, float]]]):
        cid, slug, event_title, market_question, token_meta = task
        try:
            data = get_holders(cid)
            return cid, True, (slug, event_title, market_question, token_meta, data)
        except Exception:
            return cid, False, None

    holder_results = []
    failed_ids: list[str] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_holder_task, t): t for t in holder_tasks}
        total_holders_tasks = len(futures)
        for idx, f in enumerate(as_completed(futures), 1):
            cid, ok, payload = f.result()
            if ok and payload:
                holder_results.append(payload)
            else:
                failed_ids.append(cid)
            if idx % 1000 == 0 or idx == total_holders_tasks:
                print(f"    holders progress: {idx}/{total_holders_tasks} ({idx/total_holders_tasks:.1%})")

    print(f"  Got holders for {len(holder_results)} markets (failed: {len(failed_ids)})")

    if not once:
        new_pending = remaining_ids + failed_ids
        _save_queue_ids(new_pending, snapshot_key=snapshot_key, completed=not new_pending)
        print(
            f"  Queue updated: pending={len(new_pending)} "
            f"(requeued_failed={len(failed_ids)}, completed={not new_pending})"
        )

    # Phase C: Filter big holders, collect addresses needing stats
    candidates = []
    addresses_to_check = set()

    for slug, event_title, market_question, token_meta, holders_data in holder_results:
        for group in holders_data:
            token = str(group.get("token", ""))
            side, side_price = token_meta.get(token, ("?", 0.0))
            for h in group.get("holders", []):
                amount = _safe_float(h.get("amount", 0), 0.0)
                if amount < MIN_AMOUNT:
                    continue
                address = h.get("proxyWallet", "")
                if not address or (slug, market_question, address) in existing_keys:
                    continue
                name = h.get("name") or h.get("pseudonym") or "Anonymous"
                position_value = amount * side_price
                if position_value < MIN_POSITION_VALUE:
                    continue
                candidates.append(
                    (slug, event_title, market_question, address, name, amount, side, side_price, position_value)
                )
                addresses_to_check.add(address)

    print(
        f"  {len(candidates)} big holders (value >= ${MIN_POSITION_VALUE:,}), "
        f"{len(addresses_to_check)} unique addresses to check"
    )

    # Phase D: Fetch user stats with Supabase persistent profile cache
    stats_cache: dict[str, dict[str, Any] | None] = {}
    cache_ttl_seconds = USER_STATS_DB_TTL_HOURS * 3600
    to_fetch: list[str] = []
    cache_hit = 0
    profile_rows_to_upsert: list[dict[str, Any]] = []

    profiles_by_addr: dict[str, dict[str, Any]] = {}
    profile_table_ok = True
    try:
        profiles_by_addr = sb.get_whale_user_profiles(list(addresses_to_check))
    except Exception as e:
        profile_table_ok = False
        print(f"  user-stats profile table unavailable, fallback to API only: {e}")

    for addr in addresses_to_check:
        profile = profiles_by_addr.get(addr)
        if profile:
            cached = _build_stats_from_profile(profile, cache_ttl_seconds)
            if cached:
                stats_cache[addr] = cached
                cache_hit += 1
                continue
        to_fetch.append(addr)

    print(
        f"  user-stats profile cache: hit={cache_hit}, miss={len(to_fetch)}, "
        f"ttl={USER_STATS_DB_TTL_HOURS}h"
    )

    def fetch_stats_task(addr: str):
        return addr, get_user_stats(addr)

    if to_fetch:
        print(f"  Fetching user stats ({MAX_WORKERS} threads)...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fetch_stats_task, a): a for a in to_fetch}
            total_stats_tasks = len(futures)
            for idx, f in enumerate(as_completed(futures), 1):
                addr, stats = f.result()
                stats_cache[addr] = stats
                if stats:
                    joined_ts = stats.get("joined_ts")
                    join_date = (
                        datetime.fromtimestamp(float(joined_ts), tz=timezone.utc).isoformat()
                        if isinstance(joined_ts, (float, int))
                        else None
                    )
                    profile_rows_to_upsert.append({
                        "holder_address": addr,
                        "trades": int(stats.get("trades", 0)),
                        "join_date": join_date,
                        "last_fetched_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    })
                if idx % 1000 == 0 or idx == total_stats_tasks:
                    print(f"    user-stats progress: {idx}/{total_stats_tasks} ({idx/total_stats_tasks:.1%})")

    if profile_table_ok and profile_rows_to_upsert:
        try:
            sb.upsert_whale_user_profiles(profile_rows_to_upsert)
            print(f"  user-stats profiles upserted: {len(profile_rows_to_upsert)}")
        except Exception as e:
            print(f"  user-stats profile upsert failed: {e}")

    # Phase E: Filter by criteria
    alerts = []
    for slug, event_title, market_question, address, name, amount, side, side_price, position_value in candidates:
        stats = stats_cache.get(address)
        if not stats:
            continue
        trades = int(stats.get("trades", 999))
        active_days = int(stats.get("active_days", 999))
        if trades < MAX_TRADES and active_days < MAX_ACTIVE_DAYS:
            alerts.append(
                {
                    "slug": slug,
                    "event_title": event_title,
                    "url": f"https://polymarket.com/event/{slug}",
                    "market_question": market_question,
                    "holder_address": address,
                    "holder_name": name,
                    "holder_amount": float(amount),
                    "holder_trades": trades,
                    "holder_active_days": active_days,
                    "side": side,
                    "side_price": round(side_price, 4),
                    "position_value": round(position_value, 2),
                }
            )
            existing_keys.add((slug, market_question, address))

    print(f"  Total: {len(alerts)} whale alerts found\n")

    if not alerts:
        print("  No whale alerts this round.")
        return

    # Step 3: Upload
    print(f"[3/3] Uploading {len(alerts)} alerts to Supabase...")
    sb.upsert_whale_alerts(alerts)
    print(f"  Uploaded {len(alerts)} rows")

    for i, a in enumerate(alerts[:5], 1):
        print(
            f"  {i}. [{a['side']}] ${a['holder_amount']:,.0f} "
            f"(val ${a['position_value']:,.0f}) | {a['holder_trades']}tx/{a['holder_active_days']}d | "
            f"{a['market_question'][:50]}"
        )

    print("\n=== Whale monitor complete ===")


def run_whale_monitor(sb: SupabaseClient, once: bool = False):
    """Entry point called from pipeline.py."""
    print("\n" + "=" * 50)
    print("=== Whale Monitor: Scan -> Filter -> Upload ===\n")
    print(
        f"Config: events={TOP_EVENTS_LIMIT}, markets/run={MARKETS_PER_RUN}, "
        f"holders={HOLDERS_LIMIT}, rps={REQUESTS_PER_SECOND}, workers={MAX_WORKERS}, "
        f"cache_ttl={MARKET_TASK_CACHE_TTL_HOURS}h"
    )

    try:
        _run_whale_monitor(sb, once)
    except Exception as e:
        print(f"  Whale monitor error: {e}")
