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
SPORTS_PAGE_URL = "https://polymarket.com/zh/sports/world-cup/{event_slug}"

WINDOW_HOURS = 72
VALIDATE_TAG_ID = 100639
SERIES_ID = "11433"
EVENT_SLUG_RE = re.compile(r"^fifwc-[a-z0-9]+-[a-z0-9]+-[0-9]{4}-[0-9]{2}-[0-9]{2}$")
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json" crossorigin="anonymous">(.*?)</script>',
    re.S,
)
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

SPREAD_SLUG_RE = re.compile(r"-spread-(?:home|away)-(\d+)pt(\d+)$")
TOTAL_SLUG_RE = re.compile(r"-total-(\d+)pt(\d+)$")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_session() -> requests.Session:
    return requests.Session()


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
                headers={"accept": "application/json", "user-agent": "Mozilla/5.0"},
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


def _http_get_text(
    session: requests.Session,
    url: str,
    *,
    timeout: int = REQUEST_TIMEOUT_S,
    max_retries: int = 4,
) -> str:
    last_error: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                url,
                timeout=timeout,
                headers={"accept": "text/html", "user-agent": "Mozilla/5.0"},
            )
            if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                last_error = RuntimeError(f"{response.status_code}: {response.text[:300]}")
                time.sleep(0.6 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(0.6 * (2 ** (attempt - 1)))
    raise RuntimeError(f"GET failed for {url}: {last_error}")


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
    for key in ("gameStartTime", "endDate", "endDateIso", "startDate", "startDateIso", "start_time"):
        dt = _parse_datetime(event.get(key))
        if dt is not None:
            return dt

    markets = event.get("markets")
    if isinstance(markets, list):
        candidates: list[datetime] = []
        for market in markets:
            if not isinstance(market, dict):
                continue
            for key in ("gameStartTime", "endDate", "endDateIso", "startDate", "startDateIso"):
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


def _market_sort_key(market: dict[str, Any]) -> tuple[float, float]:
    volume = _market_metric(market, ("volumeNum", "volume", "volume24hr", "volume1wk", "volume1mo")) or 0.0
    liquidity = _market_metric(market, ("liquidityNum", "liquidity", "liquidityClob")) or 0.0
    return (-volume, -liquidity)


def _format_line_value(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _slug_line_value(slug: str, pattern: re.Pattern[str]) -> float | None:
    match = pattern.search(slug)
    if not match:
        return None
    whole = int(match.group(1))
    frac = int(match.group(2))
    digits = len(match.group(2))
    return whole + frac / (10 ** digits)


def _spread_line_value(market: dict[str, Any]) -> float | None:
    line_value = _safe_float(market.get("line"))
    if line_value is not None:
        return abs(line_value)
    return _slug_line_value(str(market.get("slug") or ""), SPREAD_SLUG_RE)


def _total_line_value(market: dict[str, Any]) -> float | None:
    line_value = _safe_float(market.get("line"))
    if line_value is not None:
        return line_value
    return _slug_line_value(str(market.get("slug") or ""), TOTAL_SLUG_RE)


def _is_main_moneyline_market(event_slug: str, market: dict[str, Any]) -> bool:
    slug = str(market.get("slug") or "")
    prefix = f"{event_slug}-"
    if not slug.startswith(prefix):
        return False
    suffix = slug[len(prefix):]
    return bool(suffix) and "-" not in suffix


def _is_full_game_spread_market(market: dict[str, Any]) -> bool:
    sports_market_type = str(market.get("sportsMarketType") or "").lower()
    if sports_market_type == "spreads":
        return True
    slug = str(market.get("slug") or "")
    return bool(SPREAD_SLUG_RE.search(slug))


def _is_full_game_total_market(market: dict[str, Any]) -> bool:
    sports_market_type = str(market.get("sportsMarketType") or "").lower()
    if sports_market_type:
        return sports_market_type == "totals"
    slug = str(market.get("slug") or "")
    if "-team-total-" in slug or "-first-half-" in slug or "-second-half-" in slug:
        return False
    return bool(TOTAL_SLUG_RE.search(slug))


def _parse_event_teams(event_title: str) -> tuple[str | None, str | None]:
    normalized = event_title.replace(" vs. ", " vs ").replace(" vs ", " | ")
    parts = [part.strip() for part in normalized.split("|", 1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return None, None


def _moneyline_sort_rank(market: dict[str, Any], home_team: str | None, away_team: str | None) -> int:
    label = str(market.get("groupItemTitle") or market.get("question") or "").strip().lower()
    if home_team and label == home_team.lower():
        return 0
    if "draw" in label:
        return 1
    if away_team and label == away_team.lower():
        return 2
    slug = str(market.get("slug") or "").lower()
    if slug.endswith("-draw"):
        return 1
    return 99


def fetch_world_cup_events(session: requests.Session) -> list[dict[str, Any]]:
    now_utc = _now_utc()
    window_end = now_utc + timedelta(hours=WINDOW_HOURS)
    matched: list[dict[str, Any]] = []

    for page in range(EVENTS_MAX_PAGES):
        params = {
            "series_id": SERIES_ID,
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
            event_copy = dict(event)
            event_id = event_copy.get("id")
            if event_id:
                full_event = _http_get_json(session, f"{GAMMA_API}/events/{event_id}")
                if isinstance(full_event, dict):
                    event_copy = full_event

            if event_copy.get("closed") is True or event_copy.get("ended") is True:
                continue

            start_time = _event_start_time(event_copy)
            if start_time is None or start_time <= now_utc or start_time > window_end:
                continue

            event_copy["_derived_start_time"] = start_time.isoformat()
            matched.append(event_copy)

        if len(payload) < EVENT_PAGE_SIZE:
            break

    matched.sort(key=lambda item: str(item.get("_derived_start_time") or ""))
    return matched[:MAX_EVENTS]


def _fetch_child_event_ids(session: requests.Session, event_slug: str) -> list[str]:
    html = _http_get_text(session, SPORTS_PAGE_URL.format(event_slug=event_slug), timeout=20)
    match = NEXT_DATA_RE.search(html)
    if match:
        try:
            next_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            next_data = None

        if isinstance(next_data, dict):
            queries = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("dehydratedState", {})
                .get("queries", [])
            )
            for query in queries:
                if not isinstance(query, dict):
                    continue
                query_key = query.get("queryKey")
                if not isinstance(query_key, list) or not query_key:
                    continue
                if query_key[0] != "parentToChildEventIds":
                    continue
                state_data = (query.get("state") or {}).get("data")
                if not isinstance(state_data, dict):
                    continue
                child_ids = state_data.get(event_slug) or []
                return [str(child_id) for child_id in child_ids if str(child_id)]

    query_idx = html.find("parentToChildEventIds")
    if query_idx >= 0:
        event_marker = f'\\"{event_slug}\\":['
        window_start = max(0, query_idx - 8000)
        marker_idx = html.rfind(event_marker, window_start, query_idx)
        if marker_idx >= 0:
            ids_start = marker_idx + len(event_marker)
            ids_end = html.find("]", ids_start)
            if ids_end >= 0:
                ids_blob = html[ids_start:ids_end]
                return re.findall(r"\d+", ids_blob)
    return []


def _fetch_event_by_id(session: requests.Session, event_id: str) -> dict[str, Any] | None:
    payload = _http_get_json(session, f"{GAMMA_API}/events/{event_id}")
    return payload if isinstance(payload, dict) else None


def _extract_holder_rows(
    holders_by_token: dict[str, list[Any]],
    token_id: str | None,
) -> list[dict[str, Any]]:
    if not token_id:
        return []
    holders = holders_by_token.get(str(token_id), [])
    out_rows: list[dict[str, Any]] = []
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
                "quantity": _safe_float(holder.get("amount")) or 0.0,
                "address_age_days": None,
                "total_pnl": None,
                "pnl_7d": None,
                "pnl_30d": None,
                "win_rate": None,
            }
        )
    out_rows.sort(key=lambda item: item["amount"], reverse=True)
    return out_rows[:HOLDERS_LIMIT]


def _attach_holder_value(holders: list[dict[str, Any]], price: float | None) -> None:
    if price is None or not math.isfinite(price):
        for holder in holders:
            holder["amount"] = None
        return
    for holder in holders:
        quantity = _safe_float(holder.get("quantity"))
        holder["amount"] = (quantity * price) if quantity is not None else None


def _fetch_holders_by_token(session: requests.Session, condition_id: str) -> dict[str, list[Any]]:
    holders_payload = _http_get_json(
        session,
        f"{DATA_API}/holders",
        params={"market": condition_id, "limit": HOLDERS_LIMIT},
        timeout=20,
    )
    if not isinstance(holders_payload, list):
        raise RuntimeError("invalid_holders_payload")
    return {
        str(block.get("token") or ""): block.get("holders") or []
        for block in holders_payload
        if isinstance(block, dict)
    }


def _build_line_base(
    *,
    market_slug: str,
    condition_id: str,
    question: str,
    label: str,
    short_label: str | None,
    volume: float | None,
    liquidity: float | None,
    line_value: float | None,
) -> dict[str, Any]:
    return {
        "market_slug": market_slug,
        "condition_id": condition_id,
        "question": question,
        "label": label,
        "short_label": short_label or label,
        "line_value": line_value,
        "volume": volume,
        "liquidity": liquidity,
        "sides": [],
        "error": None,
    }


def _holders_for_market(
    session: requests.Session,
    market: dict[str, Any],
    *,
    label: str | None = None,
    short_label: str | None = None,
    side_names: list[str] | None = None,
    line_value: float | None = None,
) -> dict[str, Any]:
    question = str(market.get("question") or market.get("title") or "")
    outcomes = _parse_json_list(market.get("outcomes"))
    prices = _parse_json_list(market.get("outcomePrices"))
    token_ids = [str(token) for token in _parse_json_list(market.get("clobTokenIds"))]
    condition_id = str(market.get("conditionId") or "")
    market_slug = str(market.get("slug") or "")
    line = _build_line_base(
        market_slug=market_slug,
        condition_id=condition_id,
        question=question,
        label=label or question or market_slug,
        short_label=short_label,
        volume=_market_metric(market, ("volumeNum", "volume", "volume24hr", "volume1wk", "volume1mo")),
        liquidity=_market_metric(market, ("liquidityNum", "liquidity", "liquidityClob")),
        line_value=line_value,
    )

    for idx, outcome in enumerate(outcomes):
        price = _safe_float(prices[idx]) if idx < len(prices) else None
        token_id = token_ids[idx] if idx < len(token_ids) else None
        name = side_names[idx] if side_names and idx < len(side_names) else str(outcome)
        line["sides"].append(
            {
                "name": name,
                "outcome": str(outcome),
                "direction": "Yes" if idx == 0 else "No",
                "token_id": token_id,
                "price": price,
                "holders": [],
            }
        )

    if not condition_id or not token_ids:
        line["error"] = "missing_condition_or_tokens"
        return line

    try:
        holders_by_token = _fetch_holders_by_token(session, condition_id)
    except Exception as exc:
        line["error"] = str(exc)
        return line

    for side in line["sides"]:
        side["holders"] = _extract_holder_rows(holders_by_token, side.get("token_id"))
        _attach_holder_value(side["holders"], _safe_float(side.get("price")))

    return line


def _build_moneyline_lines(
    session: requests.Session,
    event: dict[str, Any],
    moneyline_markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    event_slug = str(event.get("slug") or "")
    event_title = str(event.get("title") or event_slug)
    home_team, away_team = _parse_event_teams(event_title)

    ordered_markets = sorted(
        moneyline_markets,
        key=lambda market: (
            _moneyline_sort_rank(market, home_team, away_team),
            *_market_sort_key(market),
        ),
    )

    lines: list[dict[str, Any]] = []
    for market in ordered_markets:
        outcomes = _parse_json_list(market.get("outcomes"))
        outcome_name = str(market.get("groupItemTitle") or market.get("title") or market.get("question") or "").strip()
        if not outcome_name and outcomes:
            outcome_name = str(outcomes[0])
        if "draw" in outcome_name.lower():
            outcome_name = "Draw"
        if not outcome_name:
            outcome_name = "Moneyline"

        line = _holders_for_market(
            session,
            market,
            label=f"{outcome_name} 胜平负",
            short_label=outcome_name,
            side_names=[outcome_name for _ in outcomes],
            line_value=None,
        )
        line["question"] = str(market.get("question") or market.get("title") or event_title)
        lines.append(line)

    return lines


def _spread_side_names(market: dict[str, Any], line_value: float) -> list[str]:
    outcomes = [str(item) for item in _parse_json_list(market.get("outcomes"))]
    if len(outcomes) >= 2:
        value_text = _format_line_value(line_value)
        return [f"{outcomes[0]} -{value_text}", f"{outcomes[1]} +{value_text}"]
    return outcomes


def _build_spread_line(session: requests.Session, market: dict[str, Any], line_value: float) -> dict[str, Any]:
    group_title = str(market.get("groupItemTitle") or "").strip()
    short_label = group_title or f"Spread {_format_line_value(line_value)}"
    return _holders_for_market(
        session,
        market,
        label=group_title or short_label,
        short_label=short_label,
        line_value=line_value,
    )


def _build_total_line(session: requests.Session, market: dict[str, Any], line_value: float) -> dict[str, Any]:
    group_title = str(market.get("groupItemTitle") or "").strip()
    value_text = _format_line_value(line_value)
    return _holders_for_market(
        session,
        market,
        label=group_title or f"O/U {value_text}",
        short_label=group_title or value_text,
        line_value=line_value,
    )


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


def _build_event_context(session: requests.Session, event: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    worker_session = _new_session()
    event_slug = str(event.get("slug") or "")
    start_time = str(event.get("_derived_start_time") or "")
    tags = event.get("tags") or []
    tag_ids = {int(tag.get("id")) for tag in tags if isinstance(tag, dict) and _safe_float(tag.get("id")) is not None}
    validated = 1 if VALIDATE_TAG_ID in tag_ids else 0

    row = {
        "event_slug": event_slug,
        "event_title": str(event.get("title") or event_slug),
        "start_time": start_time,
        "event_url": SPORTS_PAGE_URL.format(event_slug=event_slug),
        "boards_json": {"moneyline": [], "spread": [], "total": []},
        "updated_at": _now_utc().isoformat(),
    }

    tasks: list[dict[str, Any]] = []
    moneyline_markets = [
        market
        for market in (event.get("markets") or [])
        if isinstance(market, dict) and _is_unfinished_market(market) and _is_main_moneyline_market(event_slug, market)
    ]
    if moneyline_markets:
        tasks.append({"event_slug": event_slug, "board_type": "moneyline", "task_type": "moneyline", "event": event, "markets": moneyline_markets})

    try:
        child_event_ids = _fetch_child_event_ids(worker_session, event_slug)
    except Exception:
        child_event_ids = []

    child_events: list[dict[str, Any]] = []
    for child_event_id in child_event_ids:
        try:
            child_event = _fetch_event_by_id(worker_session, child_event_id)
        except Exception:
            child_event = None
        if child_event:
            child_events.append(child_event)

    for child_event in child_events:
        for market in child_event.get("markets") or []:
            if not isinstance(market, dict) or not _is_unfinished_market(market):
                continue

            spread_value = _spread_line_value(market)
            if spread_value is not None and _is_full_game_spread_market(market):
                tasks.append(
                    {
                        "event_slug": event_slug,
                        "board_type": "spread",
                        "task_type": "spread",
                        "market": market,
                        "line_value": spread_value,
                    }
                )
                continue

            total_value = _total_line_value(market)
            if total_value is not None and _is_full_game_total_market(market):
                tasks.append(
                    {
                        "event_slug": event_slug,
                        "board_type": "total",
                        "task_type": "total",
                        "market": market,
                        "line_value": total_value,
                    }
                )

    return row, tasks, validated


def _fetch_line_for_task(session: requests.Session, task: dict[str, Any]) -> tuple[str, str, dict[str, Any] | list[dict[str, Any]]]:
    worker_session = _new_session()
    event_slug = str(task["event_slug"])
    board_type = str(task["board_type"])
    task_type = str(task["task_type"])

    if task_type == "moneyline":
        line = _build_moneyline_lines(worker_session, task["event"], task["markets"])
    elif task_type == "spread":
        line = _build_spread_line(worker_session, task["market"], float(task["line_value"]))
    elif task_type == "total":
        line = _build_total_line(worker_session, task["market"], float(task["line_value"]))
    else:
        raise RuntimeError(f"unsupported task_type={task_type}")
    return event_slug, board_type, line


def _build_match_boards(session: requests.Session, events: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], int]:
    event_rows: dict[str, dict[str, Any]] = {}
    holder_tasks: list[dict[str, Any]] = []
    validated_count = 0

    with ThreadPoolExecutor(max_workers=max(2, min(MAX_WORKERS, len(events) or 1))) as pool:
        futures = {pool.submit(_build_event_context, session, event): event for event in events}
        for future in as_completed(futures):
            row, tasks, validated = future.result()
            event_rows[row["event_slug"]] = row
            holder_tasks.extend(tasks)
            validated_count += validated

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_line_for_task, session, task): task for task in holder_tasks}
        for future in as_completed(futures):
            event_slug, board_type, line = future.result()
            row = event_rows.get(event_slug)
            if row is None:
                continue
            if isinstance(line, list):
                row["boards_json"][board_type].extend(line)
            else:
                row["boards_json"][board_type].append(line)

    for row in event_rows.values():
        home_team, away_team = _parse_event_teams(str(row.get("event_title") or ""))
        row["boards_json"]["moneyline"].sort(
            key=lambda item: (
                _moneyline_sort_rank(
                    {
                        "groupItemTitle": item.get("short_label"),
                        "question": item.get("question"),
                        "title": item.get("label"),
                    },
                    home_team,
                    away_team,
                ),
                -float(item.get("volume") or 0.0),
                str(item.get("label") or ""),
            )
        )
        for board_type in ("spread", "total"):
            row["boards_json"][board_type].sort(
                key=lambda item: (
                    -float(item.get("volume") or 0.0),
                    -float(item.get("liquidity") or 0.0),
                    float(item.get("line_value") or 0.0),
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
    try:
        cached_rows = sb.get_world_cup_address_metrics(addresses)
    except Exception:
        cached_rows = {}

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
        metric, cache_row = _fetch_address_metric(_new_session(), address)
        return address, metric, cache_row

    if to_refresh:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fetch_one, address): address for address in to_refresh}
            for future in as_completed(futures):
                try:
                    address, metric, cache_row = future.result()
                except Exception:
                    continue
                metrics_by_address[address] = metric
                upsert_rows.append(cache_row)

    if upsert_rows:
        try:
            sb.upsert_world_cup_address_metrics(upsert_rows)
        except Exception:
            pass

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
        f"(series_id={SERIES_ID}, validate_tag_id={VALIDATE_TAG_ID}, window={WINDOW_HOURS}h)..."
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
