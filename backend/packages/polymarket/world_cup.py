# -*- coding: utf-8 -*-
"""World Cup match boards pipeline."""

from __future__ import annotations

import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests import HTTPError

from packages.common.supabase_client import SupabaseClient

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
USER_PNL_API = "https://user-pnl-api.polymarket.com"

WINDOW_HOURS = 72
EVENT_TAG_ID = 102232
VALIDATE_TAG_ID = 100639
EVENT_SLUG_RE = re.compile(r"^fifwc-[a-z0-9]+-[a-z0-9]+-[0-9]{4}-[0-9]{2}-[0-9]{2}$")
REQUEST_TIMEOUT_S = 25
HOLDERS_LIMIT = 10
EVENT_PAGE_SIZE = 100
EVENTS_MAX_PAGES = 5
MAX_EVENTS = 30
MAX_WORKERS = 8
ADDRESS_CACHE_TTL_HOURS = 24
USER_PNL_FIDELITY = "12h"
USER_PNL_INTERVAL = "all"
METRICS_COMPAT_VERSION = "world_cup_user_pnl_all_12h_v1"
DEFAULT_CLOSED_POSITIONS_LIMIT = 500


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        raw = value.strip().replace(",", "")
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        return value if math.isfinite(value) else None
    return None


def _http_get_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = REQUEST_TIMEOUT_S,
    max_retries: int = 4,
) -> Any:
    last_error: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                url,
                params=params or {},
                timeout=timeout,
                headers={"accept": "application/json"},
            )
            if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                last_error = RuntimeError(f"{response.status_code}: {response.text[:300]}")
                time.sleep(0.6 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(0.6 * (2 ** (attempt - 1)))
    raise RuntimeError(f"GET failed for {url} params={params}: {last_error}")


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _market_metric(market: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        value = _safe_float(market.get(name))
        if value is not None:
            return value
    return None


def _event_start_time(event: dict[str, Any]) -> datetime | None:
    for key in ("startDate", "startDateIso", "gameStartTime", "start_time"):
        dt = _parse_datetime(event.get(key))
        if dt is not None:
            return dt

    markets = event.get("markets")
    if isinstance(markets, list):
        candidates: list[datetime] = []
        for market in markets:
            if not isinstance(market, dict):
                continue
            for key in ("gameStartTime", "startDate", "startDateIso", "endDateIso", "endDate"):
                dt = _parse_datetime(market.get(key))
                if dt is not None:
                    candidates.append(dt)
                    break
        if candidates:
            return min(candidates)
    return None


def _is_unfinished_market(market: dict[str, Any]) -> bool:
    if market.get("closed") is True or market.get("ended") is True:
        return False
    events = market.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("closed") is True or event.get("ended") is True:
                return False
    return True


def _market_text(market: dict[str, Any]) -> str:
    parts = [
        str(market.get("question") or ""),
        str(market.get("title") or ""),
        str(market.get("groupItemTitle") or ""),
    ]
    return " ".join(part for part in parts if part).strip()


def _is_moneyline_market(market: dict[str, Any]) -> bool:
    text = _market_text(market).lower()
    if any(keyword in text for keyword in ("spread", "handicap", "over", "under", "o/u", "total")):
        return False
    if any(keyword in text for keyword in ("first to score", "score first", "both teams to score", "clean sheet")):
        return False
    return bool(
        "win" in text
        or "draw" in text
        or "moneyline" in text
        or "vs" in text
        or "match result" in text
    )


def _is_spread_market(market: dict[str, Any]) -> bool:
    text = _market_text(market).lower()
    if any(keyword in text for keyword in ("spread", "handicap", "asian handicap")):
        return True
    return bool(re.search(r"([+-]\d+(?:\.\d+)?)", text) and "total" not in text and "over" not in text)


def _is_total_market(market: dict[str, Any]) -> bool:
    text = _market_text(market).lower()
    if any(keyword in text for keyword in ("total", "over/under", "over under", "o/u")):
        return True
    if "over" in text and "under" in text:
        return True
    return False


def _classify_market(market: dict[str, Any]) -> str | None:
    if _is_total_market(market):
        return "total"
    if _is_spread_market(market):
        return "spread"
    if _is_moneyline_market(market):
        return "moneyline"
    return None


def _market_sort_key(market: dict[str, Any]) -> tuple[float, float]:
    volume = _market_metric(market, ("volumeNum", "volume", "volume24hr", "volume1wk", "volume1mo")) or 0.0
    liquidity = _market_metric(market, ("liquidityNum", "liquidity", "liquidityClob")) or 0.0
    return (-volume, -liquidity)


def _line_label(market: dict[str, Any]) -> str:
    for key in ("groupItemTitle", "question", "title"):
        value = str(market.get(key) or "").strip()
        if value:
            return value
    return str(market.get("slug") or "Unknown market")


def fetch_world_cup_events(session: requests.Session) -> list[dict[str, Any]]:
    now_utc = _now_utc()
    window_end = now_utc + timedelta(hours=WINDOW_HOURS)
    matched: list[dict[str, Any]] = []

    for page in range(EVENTS_MAX_PAGES):
        params = {
            "tag_id": EVENT_TAG_ID,
            "active": "true",
            "closed": "false",
            "limit": EVENT_PAGE_SIZE,
            "offset": page * EVENT_PAGE_SIZE,
        }
        payload = _http_get_json(session, f"{GAMMA_API}/events", params=params)
        if not isinstance(payload, list) or not payload:
            break

        for event in payload:
            if not isinstance(event, dict):
                continue
            slug = str(event.get("slug") or "")
            if not EVENT_SLUG_RE.search(slug):
                continue
            if event.get("closed") is True or event.get("ended") is True:
                continue
            start_time = _event_start_time(event)
            if start_time is None or start_time <= now_utc or start_time > window_end:
                continue

            event_copy = dict(event)
            if not isinstance(event_copy.get("markets"), list):
                event_id = event_copy.get("id")
                if event_id:
                    full_event = _http_get_json(session, f"{GAMMA_API}/events/{event_id}")
                    if isinstance(full_event, dict):
                        event_copy = full_event
                        start_time = _event_start_time(event_copy) or start_time

            event_copy["_derived_start_time"] = start_time.isoformat()
            matched.append(event_copy)

        if len(payload) < EVENT_PAGE_SIZE:
            break

    matched.sort(key=lambda item: str(item.get("_derived_start_time") or ""))
    return matched[:MAX_EVENTS]


def _holders_for_market(session: requests.Session, market: dict[str, Any]) -> dict[str, Any]:
    question = str(market.get("question") or market.get("title") or "")
    outcomes = _parse_json_list(market.get("outcomes"))
    prices = _parse_json_list(market.get("outcomePrices"))
    token_ids = [str(token) for token in _parse_json_list(market.get("clobTokenIds"))]
    condition_id = str(market.get("conditionId") or "")
    market_slug = str(market.get("slug") or "")
    line = {
        "market_slug": market_slug,
        "condition_id": condition_id,
        "question": question,
        "label": _line_label(market),
        "volume": _market_metric(market, ("volumeNum", "volume", "volume24hr", "volume1wk", "volume1mo")),
        "liquidity": _market_metric(market, ("liquidityNum", "liquidity", "liquidityClob")),
        "sides": [],
        "error": None,
    }

    for idx, outcome in enumerate(outcomes):
        price = _safe_float(prices[idx]) if idx < len(prices) else None
        line["sides"].append(
            {
                "name": str(outcome),
                "token_id": token_ids[idx] if idx < len(token_ids) else None,
                "price": price,
                "holders": [],
            }
        )

    if not condition_id or not token_ids:
        line["error"] = "missing_condition_or_tokens"
        return line

    try:
        holders_payload = _http_get_json(
            session,
            f"{DATA_API}/holders",
            params={"market": condition_id, "limit": HOLDERS_LIMIT},
            timeout=20,
        )
    except Exception as exc:
        line["error"] = str(exc)
        return line

    if not isinstance(holders_payload, list):
        line["error"] = "invalid_holders_payload"
        return line

    holders_by_token = {
        str(block.get("token") or ""): block.get("holders") or []
        for block in holders_payload
        if isinstance(block, dict)
    }

    for side in line["sides"]:
        holders = holders_by_token.get(str(side.get("token_id") or ""), [])
        out_rows = []
        for holder in holders[:HOLDERS_LIMIT]:
            if not isinstance(holder, dict):
                continue
            address = str(holder.get("proxyWallet") or "").lower().strip()
            if not address:
                continue
            out_rows.append(
                {
                    "address": address,
                    "name": holder.get("name") or holder.get("pseudonym") or "Anonymous",
                    "amount": _safe_float(holder.get("amount")) or 0.0,
                    "address_age_days": None,
                    "total_pnl": None,
                    "pnl_7d": None,
                    "pnl_30d": None,
                    "win_rate": None,
                }
            )
        out_rows.sort(key=lambda item: item["amount"], reverse=True)
        side["holders"] = out_rows[:HOLDERS_LIMIT]

    return line


def _interpolate_pnl_at(points: list[tuple[datetime, float]], target: datetime) -> float | None:
    if not points:
        return None
    pts = sorted(points, key=lambda item: item[0])
    if target <= pts[0][0]:
        return pts[0][1]
    if target >= pts[-1][0]:
        return pts[-1][1]
    for idx in range(1, len(pts)):
        left_t, left_v = pts[idx - 1]
        right_t, right_v = pts[idx]
        if left_t <= target <= right_t:
            total = (right_t - left_t).total_seconds()
            if total <= 0:
                return right_v
            ratio = (target - left_t).total_seconds() / total
            return left_v + (right_v - left_v) * ratio
    return None


def _compute_window_pnl(points: list[tuple[datetime, float]], days: int) -> float | None:
    if not points:
        return None
    current = points[-1][1]
    baseline = _interpolate_pnl_at(points, _now_utc() - timedelta(days=days))
    if baseline is None:
        return None
    return current - baseline


def _fetch_user_pnl_points(session: requests.Session, address: str) -> list[tuple[datetime, float]]:
    payload = _http_get_json(
        session,
        f"{USER_PNL_API}/user-pnl",
        params={
            "user_address": address,
            "interval": USER_PNL_INTERVAL,
            "fidelity": USER_PNL_FIDELITY,
        },
        timeout=20,
    )
    points: list[tuple[datetime, float]] = []
    if not isinstance(payload, list):
        return points
    for row in payload:
        if not isinstance(row, dict):
            continue
        ts = _safe_float(row.get("t"))
        pnl = _safe_float(row.get("p"))
        if ts is None or pnl is None:
            continue
        points.append((datetime.fromtimestamp(ts, tz=timezone.utc), pnl))
    points.sort(key=lambda item: item[0])
    return points


def _fetch_closed_positions(session: requests.Session, address: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    limit = 50
    for offset in range(0, DEFAULT_CLOSED_POSITIONS_LIMIT, limit):
        payload = _http_get_json(
            session,
            f"{DATA_API}/closed-positions",
            params={
                "user": address,
                "limit": limit,
                "offset": offset,
                "sortBy": "TIMESTAMP",
                "sortDirection": "ASC",
            },
            timeout=25,
        )
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < limit:
            break
    return rows


def _fetch_open_positions(session: requests.Session, address: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    limit = 200
    for offset in range(0, 1000, limit):
        payload = _http_get_json(
            session,
            f"{DATA_API}/positions",
            params={"user": address, "sizeThreshold": 0, "limit": limit, "offset": offset},
            timeout=25,
        )
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < limit:
            break
    return rows


def _extract_position_pnl(position: dict[str, Any]) -> float | None:
    for key in ("cashPnl", "cash_pnl", "pnl", "profit", "realizedPnl", "realized_pnl"):
        value = _safe_float(position.get(key))
        if value is not None:
            return value
    return None


def _compute_win_rate(open_rows: list[dict[str, Any]], closed_rows: list[dict[str, Any]]) -> float | None:
    considered = 0
    winning = 0
    for row in [*open_rows, *closed_rows]:
        pnl = _extract_position_pnl(row)
        if pnl is None:
            continue
        considered += 1
        if pnl > 0:
            winning += 1
    if considered <= 0:
        return None
    return winning / considered


def _cached_metric_is_fresh(row: dict[str, Any]) -> bool:
    snapshot = _parse_datetime(row.get("snapshot_utc")) or _parse_datetime(row.get("updated_at"))
    if snapshot is None:
        return False
    return _now_utc() - snapshot < timedelta(hours=ADDRESS_CACHE_TTL_HOURS)


def _build_metric_payload_from_cache(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": str(row.get("address") or "").lower(),
        "address_age_days": _safe_float(row.get("address_age_days")),
        "total_pnl": _safe_float(row.get("total_pnl")),
        "pnl_7d": _safe_float(row.get("pnl_7d")),
        "pnl_30d": _safe_float(row.get("pnl_30d")),
        "win_rate": _safe_float(row.get("win_rate")),
    }


def _fetch_address_metric(session: requests.Session, address: str) -> tuple[dict[str, Any], dict[str, Any]]:
    points = _fetch_user_pnl_points(session, address)
    open_rows = _fetch_open_positions(session, address)
    closed_rows = _fetch_closed_positions(session, address)
    first_activity = points[0][0] if points else None
    now = _now_utc()
    total_pnl = points[-1][1] if points else None
    metric = {
        "address": address,
        "address_age_days": ((now - first_activity).total_seconds() / 86400.0) if first_activity else None,
        "total_pnl": total_pnl,
        "pnl_7d": _compute_window_pnl(points, 7),
        "pnl_30d": _compute_window_pnl(points, 30),
        "win_rate": _compute_win_rate(open_rows, closed_rows),
    }
    cache_row = {
        **metric,
        "snapshot_utc": now.isoformat(),
        "updated_at": now.isoformat(),
        "details_json": {
            "metrics_compat_version": METRICS_COMPAT_VERSION,
            "user_pnl_interval": USER_PNL_INTERVAL,
            "user_pnl_fidelity": USER_PNL_FIDELITY,
            "pnl_points": len(points),
            "open_positions": len(open_rows),
            "closed_positions": len(closed_rows),
            "first_activity_utc": first_activity.isoformat() if first_activity else None,
        },
    }
    return metric, cache_row


def _enrich_holders_with_metrics(
    boards_by_event: dict[str, dict[str, Any]],
    metrics_by_address: dict[str, dict[str, Any]],
) -> None:
    for event in boards_by_event.values():
        for board_type in ("moneyline", "spread", "total"):
            for line in event["boards_json"].get(board_type, []):
                for side in line.get("sides", []):
                    for holder in side.get("holders", []):
                        address = str(holder.get("address") or "").lower()
                        metric = metrics_by_address.get(address)
                        if not metric:
                            continue
                        holder["address_age_days"] = metric.get("address_age_days")
                        holder["total_pnl"] = metric.get("total_pnl")
                        holder["pnl_7d"] = metric.get("pnl_7d")
                        holder["pnl_30d"] = metric.get("pnl_30d")
                        holder["win_rate"] = metric.get("win_rate")


def _collect_unique_addresses(boards_by_event: dict[str, dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for event in boards_by_event.values():
        for board_type in ("moneyline", "spread", "total"):
            for line in event["boards_json"].get(board_type, []):
                for side in line.get("sides", []):
                    for holder in side.get("holders", []):
                        address = str(holder.get("address") or "").lower().strip()
                        if not address or address in seen:
                            continue
                        seen.add(address)
                        ordered.append(address)
    return ordered


def _build_match_boards(session: requests.Session, events: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], int]:
    event_rows: dict[str, dict[str, Any]] = {}
    markets_to_fetch: list[tuple[str, str, dict[str, Any]]] = []
    validated_count = 0

    for event in events:
        event_slug = str(event.get("slug") or "")
        start_time = str(event.get("_derived_start_time") or "")
        if not event_slug or not start_time:
            continue
        tags = event.get("tags") or []
        tag_ids = {int(tag.get("id")) for tag in tags if isinstance(tag, dict) and _safe_float(tag.get("id")) is not None}
        if VALIDATE_TAG_ID in tag_ids:
            validated_count += 1

        event_rows[event_slug] = {
            "event_slug": event_slug,
            "event_title": str(event.get("title") or event_slug),
            "start_time": start_time,
            "event_url": f"https://polymarket.com/event/{event_slug}",
            "boards_json": {"moneyline": [], "spread": [], "total": []},
            "updated_at": _now_utc().isoformat(),
        }

        markets = event.get("markets") or []
        typed_markets: dict[str, list[dict[str, Any]]] = {"moneyline": [], "spread": [], "total": []}
        for market in markets:
            if not isinstance(market, dict):
                continue
            if not _is_unfinished_market(market):
                continue
            board_type = _classify_market(market)
            if board_type is None:
                continue
            if not market.get("conditionId"):
                continue
            typed_markets[board_type].append(market)

        for board_type, board_markets in typed_markets.items():
            board_markets.sort(key=_market_sort_key)
            for market in board_markets:
                markets_to_fetch.append((event_slug, board_type, market))

    def fetch_one(task: tuple[str, str, dict[str, Any]]) -> tuple[str, str, dict[str, Any]]:
        event_slug, board_type, market = task
        return event_slug, board_type, _holders_for_market(session, market)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_one, task): task for task in markets_to_fetch}
        for future in as_completed(futures):
            event_slug, board_type, line = future.result()
            row = event_rows.get(event_slug)
            if row is None:
                continue
            row["boards_json"][board_type].append(line)

    for row in event_rows.values():
        for board_type in ("moneyline", "spread", "total"):
            row["boards_json"][board_type].sort(
                key=lambda item: (
                    -float(item.get("volume") or 0.0),
                    -float(item.get("liquidity") or 0.0),
                    str(item.get("label") or ""),
                )
            )

    return event_rows, validated_count


def _refresh_address_metrics(
    session: requests.Session,
    sb: SupabaseClient,
    boards_by_event: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], int, int]:
    addresses = _collect_unique_addresses(boards_by_event)
    cached_rows = sb.get_world_cup_address_metrics(addresses)

    metrics_by_address: dict[str, dict[str, Any]] = {}
    fresh_cache_hits = 0
    to_refresh: list[str] = []

    for address in addresses:
        cached = cached_rows.get(address)
        if cached and _cached_metric_is_fresh(cached):
            metrics_by_address[address] = _build_metric_payload_from_cache(cached)
            fresh_cache_hits += 1
        else:
            to_refresh.append(address)

    upsert_rows: list[dict[str, Any]] = []

    def fetch_one(address: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        metric, cache_row = _fetch_address_metric(session, address)
        return address, metric, cache_row

    if to_refresh:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fetch_one, address): address for address in to_refresh}
            for future in as_completed(futures):
                address, metric, cache_row = future.result()
                metrics_by_address[address] = metric
                upsert_rows.append(cache_row)

    if upsert_rows:
        sb.upsert_world_cup_address_metrics(upsert_rows)

    _enrich_holders_with_metrics(boards_by_event, metrics_by_address)
    return metrics_by_address, fresh_cache_hits, len(to_refresh)


def _cleanup_stale_rows(sb: SupabaseClient, current_event_slugs: list[str]) -> int:
    existing = sb.get_world_cup_match_board_slugs()
    current_set = set(current_event_slugs)
    stale = [slug for slug in existing if slug not in current_set]
    if stale:
        sb.delete_world_cup_match_boards_by_event_slugs(stale)
    return len(stale)


def _run_world_cup(sb: SupabaseClient, once: bool = False) -> None:
    session = requests.Session()

    print(
        f"[1/4] Fetching World Cup events "
        f"(tag_id={EVENT_TAG_ID}, validate_tag_id={VALIDATE_TAG_ID}, window={WINDOW_HOURS}h)..."
    )
    events = fetch_world_cup_events(session)
    if once:
        events = events[:5]
    print(f"  Matched {len(events)} upcoming events")
    if not events:
        stale_removed = _cleanup_stale_rows(sb, [])
        if stale_removed:
            print(f"  Removed {stale_removed} stale rows")
        print("  No upcoming World Cup events found.")
        return

    print("[2/4] Fetching holders for moneyline / spread / total markets...")
    boards_by_event, validated_count = _build_match_boards(session, events)
    print(
        f"  Built boards for {len(boards_by_event)} events "
        f"(validate_tag_hit={validated_count}/{len(events)})"
    )

    print("[3/4] Refreshing address metrics with 24h cache...")
    _, cache_hits, refreshed = _refresh_address_metrics(session, sb, boards_by_event)
    print(f"  Address metrics cache_hit={cache_hits}, refreshed={refreshed}")

    print("[4/4] Uploading latest match boards to Supabase...")
    rows = list(boards_by_event.values())
    rows.sort(key=lambda item: item["start_time"])
    sb.upsert_world_cup_match_boards(rows)
    stale_removed = _cleanup_stale_rows(sb, [row["event_slug"] for row in rows])
    print(f"  Uploaded {len(rows)} match boards, removed stale={stale_removed}")

    for idx, row in enumerate(rows[:5], 1):
        board_counts = {
            key: len(value)
            for key, value in row["boards_json"].items()
            if isinstance(value, list)
        }
        print(
            f"  {idx}. {row['start_time']} | {row['event_title'][:80]} | "
            f"moneyline={board_counts.get('moneyline', 0)} "
            f"spread={board_counts.get('spread', 0)} total={board_counts.get('total', 0)}"
        )

    print("\n=== World Cup pipeline complete ===")


def run_world_cup(sb: SupabaseClient, once: bool = False) -> None:
    print("\n" + "=" * 50)
    print("=== World Cup: Fetch -> Enrich -> Upload ===\n")
    try:
        _run_world_cup(sb, once=once)
    except HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            print("  World Cup pipeline error: Supabase tables not found.")
            print("  Apply supabase/migrations/007_world_cup.sql, then rerun this pipeline.")
            return
        print(f"  World Cup pipeline error: {exc}")
    except Exception as exc:
        print(f"  World Cup pipeline error: {exc}")
