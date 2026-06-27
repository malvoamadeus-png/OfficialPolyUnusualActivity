# -*- coding: utf-8 -*-
"""Finished World Cup market scanner and persistence pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

from packages.common.supabase_client import SupabaseClient
from packages.polymarket.world_cup import (
    DATA_API,
    EVENT_SLUG_RE,
    EVENT_PAGE_SIZE,
    EVENTS_MAX_PAGES,
    GAMMA_API,
    MAX_WORKERS,
    SERIES_ID,
    SPORTS_PAGE_URL,
    SPREAD_SLUG_RE,
    TOTAL_SLUG_RE,
    _fetch_child_event_ids,
    _fetch_event_by_id,
    _format_line_value,
    _http_get_json,
    _is_full_game_spread_market,
    _is_full_game_total_market,
    _is_main_moneyline_market,
    _parse_datetime,
    _parse_json_list,
    _safe_float,
    _slug_line_value,
    _spread_side_names,
)

BJ_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_MIN_PROFIT = 30_000.0
DEFAULT_LOOKBACK_HOURS = 48
DEFAULT_TRADES_LIMIT = 500
MAX_TRADES_OFFSET = 10_000
DEFAULT_CLOSED_LIMIT = 50
MARKET_FETCH_TIMEOUT = 12
MARKET_FETCH_RETRIES = 2


@dataclass(slots=True)
class MarketContext:
    event_id: str
    event_slug: str
    event_title: str
    event_end_time: datetime
    event_url: str
    board_type: str
    market_slug: str
    condition_id: str
    market_question: str
    market_label: str
    line_value: float | None
    outcome_name_map: dict[str, str]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _format_money(value: float | None) -> str:
    if value is None:
        return "-"
    if abs(value - round(value)) < 1e-9:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def _resolve_target_date(raw: str) -> date:
    value = (raw or "today").strip().lower()
    now_bj = _now_utc().astimezone(BJ_TZ)
    if value == "today":
        return now_bj.date()
    if value == "yesterday":
        return (now_bj - timedelta(days=1)).date()
    return date.fromisoformat(value)


def _event_end_time(event: dict[str, Any]) -> datetime | None:
    for key in ("endDate", "endDateIso", "startDate", "startDateIso", "eventDate", "startTime"):
        dt = _parse_datetime(event.get(key))
        if dt is not None:
            return dt
    return None


def _normalize_moneyline_name(value: str) -> str:
    name = value.strip()
    if " (" in name and name.endswith(")"):
        name = name.split(" (", 1)[0].strip()
    return name


def _build_moneyline_outcome_map(market: dict[str, Any]) -> dict[str, str]:
    group_title = _normalize_moneyline_name(
        str(market.get("groupItemTitle") or market.get("question") or market.get("slug") or "Moneyline")
    )
    outcomes = [str(item) for item in _parse_json_list(market.get("outcomes"))]
    if len(outcomes) >= 2 and outcomes[0].lower() == "yes" and outcomes[1].lower() == "no":
        return {
            outcomes[0]: group_title,
            outcomes[1]: f"No · {group_title}",
        }
    return {outcome: outcome for outcome in outcomes}


def _build_total_outcome_map(market: dict[str, Any], line_value: float) -> dict[str, str]:
    outcomes = [str(item) for item in _parse_json_list(market.get("outcomes"))]
    value_text = _format_line_value(line_value)
    if len(outcomes) >= 2:
        return {
            outcomes[0]: f"O {value_text}",
            outcomes[1]: f"U {value_text}",
        }
    return {outcome: outcome for outcome in outcomes}


def _fetch_finished_world_cup_events(
    session: requests.Session,
    *,
    since_utc: datetime | None = None,
    target_bj_date: date | None = None,
    once: bool = False,
) -> list[dict[str, Any]]:
    now_utc = _now_utc()
    matches: list[dict[str, Any]] = []

    for page in range(EVENTS_MAX_PAGES):
        payload = _http_get_json(
            session,
            f"{GAMMA_API}/events",
            params={
                "series_id": SERIES_ID,
                "limit": EVENT_PAGE_SIZE,
                "offset": page * EVENT_PAGE_SIZE,
            },
            timeout=25,
        )
        if not isinstance(payload, list) or not payload:
            break

        for summary in payload:
            if not isinstance(summary, dict):
                continue
            slug = str(summary.get("slug") or "")
            if not EVENT_SLUG_RE.search(slug):
                continue

            summary_end_time = _event_end_time(summary)
            if summary_end_time is None or summary_end_time > now_utc:
                continue
            if since_utc is not None and summary_end_time < since_utc:
                continue
            if target_bj_date is not None and summary_end_time.astimezone(BJ_TZ).date() != target_bj_date:
                continue

            event_id = str(summary.get("id") or "")
            if not event_id:
                continue

            full_event = _fetch_event_by_id(session, event_id)
            if not full_event:
                continue
            end_time = _event_end_time(full_event)
            if end_time is None or end_time > now_utc:
                continue
            if since_utc is not None and end_time < since_utc:
                continue
            if target_bj_date is not None and end_time.astimezone(BJ_TZ).date() != target_bj_date:
                continue

            full_event["_derived_end_time"] = end_time.isoformat()
            matches.append(full_event)
            if once and len(matches) >= 1:
                return matches

        if len(payload) < EVENT_PAGE_SIZE:
            break

    matches.sort(key=lambda item: str(item.get("_derived_end_time") or ""))
    return matches


def _build_market_contexts(session: requests.Session, event: dict[str, Any]) -> list[MarketContext]:
    event_id = str(event.get("id") or "")
    event_slug = str(event.get("slug") or "")
    event_title = str(event.get("title") or event_slug)
    event_end_time = _event_end_time(event)
    event_url = SPORTS_PAGE_URL.format(event_slug=event_slug)
    if not event_id or not event_slug or event_end_time is None:
        return []

    contexts: list[MarketContext] = []

    for market in event.get("markets") or []:
        if not isinstance(market, dict) or not _is_main_moneyline_market(event_slug, market):
            continue
        condition_id = str(market.get("conditionId") or "")
        market_slug = str(market.get("slug") or "")
        if not condition_id or not market_slug:
            continue
        contexts.append(
            MarketContext(
                event_id=event_id,
                event_slug=event_slug,
                event_title=event_title,
                event_end_time=event_end_time,
                event_url=event_url,
                board_type="moneyline",
                market_slug=market_slug,
                condition_id=condition_id,
                market_question=str(market.get("question") or market_slug),
                market_label=_normalize_moneyline_name(
                    str(market.get("groupItemTitle") or market.get("question") or "Moneyline")
                ),
                line_value=None,
                outcome_name_map=_build_moneyline_outcome_map(market),
            )
        )

    try:
        child_event_ids = _fetch_child_event_ids(session, event_slug)
    except Exception:
        child_event_ids = []

    for child_event_id in child_event_ids:
        try:
            child_event = _fetch_event_by_id(session, child_event_id)
        except Exception:
            child_event = None
        if not child_event:
            continue

        for market in child_event.get("markets") or []:
            if not isinstance(market, dict):
                continue
            condition_id = str(market.get("conditionId") or "")
            market_slug = str(market.get("slug") or "")
            if not condition_id or not market_slug:
                continue

            spread_value = _slug_line_value(market_slug, SPREAD_SLUG_RE)
            if spread_value is not None and _is_full_game_spread_market(market):
                side_names = _spread_side_names(market, spread_value)
                outcomes = [str(item) for item in _parse_json_list(market.get("outcomes"))]
                contexts.append(
                    MarketContext(
                        event_id=event_id,
                        event_slug=event_slug,
                        event_title=event_title,
                        event_end_time=event_end_time,
                        event_url=event_url,
                        board_type="spread",
                        market_slug=market_slug,
                        condition_id=condition_id,
                        market_question=str(market.get("question") or market_slug),
                        market_label=" / ".join(side_names) if side_names else f"Spread {_format_line_value(spread_value)}",
                        line_value=spread_value,
                        outcome_name_map={
                            outcome: side_names[idx] if idx < len(side_names) else outcome
                            for idx, outcome in enumerate(outcomes)
                        },
                    )
                )
                continue

            total_value = _slug_line_value(market_slug, TOTAL_SLUG_RE)
            if total_value is not None and _is_full_game_total_market(market):
                outcome_name_map = _build_total_outcome_map(market, total_value)
                contexts.append(
                    MarketContext(
                        event_id=event_id,
                        event_slug=event_slug,
                        event_title=event_title,
                        event_end_time=event_end_time,
                        event_url=event_url,
                        board_type="total",
                        market_slug=market_slug,
                        condition_id=condition_id,
                        market_question=str(market.get("question") or market_slug),
                        market_label=f"O/U {_format_line_value(total_value)}",
                        line_value=total_value,
                        outcome_name_map=outcome_name_map,
                    )
                )

    contexts.sort(key=lambda item: (item.board_type, item.market_slug))
    return contexts


def _fetch_market_trades(session: requests.Session, condition_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, MAX_TRADES_OFFSET, DEFAULT_TRADES_LIMIT):
        try:
            payload = _http_get_json(
                session,
                f"{DATA_API}/trades",
                params={"market": condition_id, "limit": DEFAULT_TRADES_LIMIT, "offset": offset},
                timeout=MARKET_FETCH_TIMEOUT,
                max_retries=MARKET_FETCH_RETRIES,
            )
        except Exception as exc:
            if "400" in str(exc) or "404" in str(exc):
                break
            raise
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < DEFAULT_TRADES_LIMIT:
            break
    return rows


def _collect_addresses_from_trades(trades: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for trade in trades:
        for key in ("proxyWallet", "proxy_wallet"):
            address = str(trade.get(key) or "").lower().strip()
            if not address or address in seen:
                continue
            seen.add(address)
            ordered.append(address)
    return ordered


def _fetch_closed_positions_for_market(
    session: requests.Session,
    address: str,
    condition_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, 250, DEFAULT_CLOSED_LIMIT):
        payload = _http_get_json(
            session,
            f"{DATA_API}/closed-positions",
            params={
                "user": address,
                "market": condition_id,
                "limit": DEFAULT_CLOSED_LIMIT,
                "offset": offset,
                "sortBy": "REALIZEDPNL",
                "sortDirection": "DESC",
            },
            timeout=MARKET_FETCH_TIMEOUT,
            max_retries=MARKET_FETCH_RETRIES,
        )
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < DEFAULT_CLOSED_LIMIT:
            break
    return rows


def _extract_realized_pnl(row: dict[str, Any]) -> float | None:
    for key in ("realizedPnl", "realized_pnl", "cashPnl", "cash_pnl", "pnl", "profit"):
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _extract_total_bought(row: dict[str, Any]) -> float | None:
    for key in ("totalBought", "total_bought"):
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    avg_price = _safe_float(row.get("avgPrice"))
    size = _safe_float(row.get("size"))
    if avg_price is not None and size is not None:
        return avg_price * size
    return None


def _extract_position_timestamp(row: dict[str, Any]) -> int:
    for key in ("timestamp", "endTimestamp", "updatedAtTimestamp"):
        raw = _safe_float(row.get(key))
        if raw is None:
            continue
        ts = int(raw)
        if ts > 10_000_000_000:
            ts //= 1000
        return ts
    for key in ("updatedAt", "closedAt", "endDate"):
        dt = _parse_datetime(row.get(key))
        if dt is not None:
            return int(dt.timestamp())
    return 0


def _timestamp_to_iso(ts: int) -> str | None:
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _aggregate_closed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        outcome = str(row.get("outcome") or "")
        asset = str(row.get("asset") or "")
        key = (outcome, asset)
        pnl = _extract_realized_pnl(row) or 0.0
        total_bought = _extract_total_bought(row) or 0.0
        timestamp = _extract_position_timestamp(row)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = {
                "outcome": outcome,
                "title": str(row.get("title") or ""),
                "slug": str(row.get("slug") or ""),
                "total_bought": total_bought,
                "realized_pnl": pnl,
                "timestamp": timestamp,
            }
            continue
        existing["total_bought"] += total_bought
        existing["realized_pnl"] += pnl
        existing["timestamp"] = max(existing["timestamp"], timestamp)
        if not existing["title"] and row.get("title"):
            existing["title"] = str(row.get("title"))
        if not existing["slug"] and row.get("slug"):
            existing["slug"] = str(row.get("slug"))
    return list(grouped.values())


def _resolve_result_label(context: MarketContext, outcome: str, fallback_title: str) -> str:
    if outcome and outcome in context.outcome_name_map:
        return context.outcome_name_map[outcome]
    if fallback_title:
        return fallback_title
    return context.market_label


def _scan_market(
    session: requests.Session,
    context: MarketContext,
    *,
    min_profit: float,
) -> list[dict[str, Any]]:
    trades = _fetch_market_trades(session, context.condition_id)
    addresses = _collect_addresses_from_trades(trades)
    if not addresses:
        return []

    winners: list[dict[str, Any]] = []

    def fetch_one(address: str) -> list[dict[str, Any]]:
        rows = _fetch_closed_positions_for_market(session, address, context.condition_id)
        aggregated = _aggregate_closed_rows(rows)
        out_rows: list[dict[str, Any]] = []
        for row in aggregated:
            pnl = _safe_float(row.get("realized_pnl"))
            if pnl is None or pnl < min_profit:
                continue
            ts = int(_safe_float(row.get("timestamp")) or 0)
            outcome_name = str(row.get("outcome") or "")
            out_rows.append(
                {
                    "event_slug": context.event_slug,
                    "event_title": context.event_title,
                    "event_end_time": context.event_end_time.isoformat(),
                    "event_url": context.event_url,
                    "board_type": context.board_type,
                    "market_slug": context.market_slug,
                    "condition_id": context.condition_id,
                    "market_question": context.market_question,
                    "market_label": _resolve_result_label(
                        context,
                        outcome_name,
                        str(row.get("title") or ""),
                    ),
                    "outcome_name": outcome_name or None,
                    "address": address,
                    "bet_amount": _safe_float(row.get("total_bought")),
                    "profit_amount": pnl,
                    "position_closed_at": _timestamp_to_iso(ts),
                    "scanned_at": _now_utc().isoformat(),
                }
            )
        return out_rows

    with ThreadPoolExecutor(max_workers=max(2, min(MAX_WORKERS, len(addresses)))) as pool:
        futures = {pool.submit(fetch_one, address): address for address in addresses}
        for future in as_completed(futures):
            try:
                winners.extend(future.result())
            except Exception:
                continue

    winners.sort(
        key=lambda item: (
            -float(item.get("profit_amount") or 0.0),
            -float(item.get("bet_amount") or 0.0),
            str(item.get("address") or ""),
        )
    )
    return winners


def _scan_event(
    session: requests.Session,
    event: dict[str, Any],
    *,
    min_profit: float,
    verbose: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    contexts = _build_market_contexts(session, event)
    event_slug = str(event.get("slug") or "")
    event_title = str(event.get("title") or event_slug)
    event_end_time = _event_end_time(event)
    event_url = SPORTS_PAGE_URL.format(event_slug=event_slug)

    if verbose:
        print(f"  Scanning {event_title} ({len(contexts)} markets)")

    report_rows: list[dict[str, Any]] = []
    failed_markets = 0
    succeeded_markets = 0
    for idx, context in enumerate(contexts, 1):
        if verbose:
            print(f"    {idx}/{len(contexts)} [{context.board_type}] {context.market_question}")
        try:
            rows = _scan_market(session, context, min_profit=min_profit)
        except Exception as exc:
            failed_markets += 1
            print(
                f"    market scan skipped: [{context.board_type}] "
                f"{context.market_slug} | {exc}"
            )
            continue
        report_rows.extend(rows)
        succeeded_markets += 1
        if verbose:
            print(f"      winners_over_threshold={len(rows)}")

    event_row = {
        "event_slug": event_slug,
        "event_id": str(event.get("id") or ""),
        "event_title": event_title,
        "event_end_time": event_end_time.isoformat() if event_end_time else None,
        "event_url": event_url,
        "markets_scanned": succeeded_markets,
        "results_count": len(report_rows),
        "scanned_at": _now_utc().isoformat(),
    }
    scan_complete = failed_markets == 0
    return report_rows, event_row, scan_complete


def _run_world_cup_finished_report(
    *,
    target_date_expr: str,
    min_profit: float,
    once: bool = False,
) -> None:
    target_date = _resolve_target_date(target_date_expr)
    session = requests.Session()
    print(
        f"[1/3] Fetching finished World Cup events for {target_date.isoformat()} "
        f"(Beijing time, min_profit={_format_money(min_profit)})..."
    )
    events = _fetch_finished_world_cup_events(
        session,
        target_bj_date=target_date,
        once=once,
    )
    print(f"  Matched {len(events)} finished events")
    if not events:
        print("  No finished World Cup events found for that Beijing date.")
        return

    print("[2/3] Scanning all moneyline / spread / total markets...")
    report_rows: list[dict[str, Any]] = []
    for event in events:
        event_rows, _, _ = _scan_event(session, event, min_profit=min_profit, verbose=True)
        report_rows.extend(event_rows)

    print("[3/3] Final report")
    if not report_rows:
        print("  No finished-market addresses exceeded the profit threshold.")
        return

    report_rows.sort(
        key=lambda item: (
            str(item.get("event_end_time") or ""),
            -float(item.get("profit_amount") or 0.0),
            str(item.get("market_slug") or ""),
        ),
        reverse=True,
    )
    print(
        f"  Found {len(report_rows)} rows over {_format_money(min_profit)} "
        f"for {target_date.isoformat()} (Beijing time)\n"
    )
    for idx, row in enumerate(report_rows, 1):
        print(
            f"  {idx}. {row['event_title']} —— {row['market_label']} "
            f"({row['board_type']}) —— {row['address']} —— "
            f"{_format_money(_safe_float(row.get('bet_amount')))} —— "
            f"{_format_money(_safe_float(row.get('profit_amount')))}"
        )


def _run_world_cup_finished_sync(
    sb: SupabaseClient,
    *,
    lookback_hours: int,
    min_profit: float,
    once: bool = False,
) -> None:
    session = requests.Session()
    since_utc = _now_utc() - timedelta(hours=lookback_hours)

    print(
        f"[1/4] Fetching finished World Cup events from the last {lookback_hours}h "
        f"(min_profit={_format_money(min_profit)})..."
    )
    events = _fetch_finished_world_cup_events(session, since_utc=since_utc)
    print(f"  Matched {len(events)} finished events in lookback window")
    if not events:
        print("  No finished World Cup events found in the lookback window.")
        return

    event_slugs = [str(event.get("slug") or "") for event in events if event.get("slug")]
    scanned_slugs = sb.get_world_cup_finished_scanned_event_slugs(event_slugs)
    pending_events = [event for event in events if str(event.get("slug") or "") not in scanned_slugs]
    if once:
        pending_events = pending_events[:1]

    print(f"[2/4] Pending new finished events to scan: {len(pending_events)}")
    if not pending_events:
        print("  All finished World Cup events in the lookback window were already scanned.")
        return

    print("[3/4] Scanning all market types and collecting winners...")
    all_result_rows: list[dict[str, Any]] = []
    scanned_event_rows: list[dict[str, Any]] = []
    for idx, event in enumerate(pending_events, 1):
        event_title = str(event.get("title") or event.get("slug") or "")
        print(f"  {idx}/{len(pending_events)} {event_title}")
        result_rows, event_row, scan_complete = _scan_event(
            session,
            event,
            min_profit=min_profit,
            verbose=False,
        )
        all_result_rows.extend(result_rows)
        print(
            f"    markets_scanned={event_row['markets_scanned']} "
            f"winners_over_threshold={event_row['results_count']}"
        )
        if not scan_complete:
            print("    event not marked complete; failed markets will retry next run")
            continue
        scanned_event_rows.append(event_row)

    print("[4/4] Writing finished World Cup results to Supabase...")
    sb.upsert_world_cup_finished_positions(all_result_rows)
    if scanned_event_rows:
        sb.upsert_world_cup_finished_events(scanned_event_rows)
    print(
        f"  Saved events={len(scanned_event_rows)} "
        f"rows={len(all_result_rows)} "
        f"threshold={_format_money(min_profit)}"
    )


def run_world_cup_finished(
    *,
    target_date_expr: str = "today",
    min_profit: float = DEFAULT_MIN_PROFIT,
    once: bool = False,
) -> None:
    print("\n" + "=" * 50)
    print("=== World Cup Finished Report ===\n")
    try:
        _run_world_cup_finished_report(
            target_date_expr=target_date_expr,
            min_profit=min_profit,
            once=once,
        )
    except Exception as exc:
        print(f"  World Cup finished report error: {exc}")
    print("\n=== World Cup finished report complete ===")


def run_world_cup_finished_sync(
    sb: SupabaseClient,
    *,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    min_profit: float = DEFAULT_MIN_PROFIT,
    once: bool = False,
) -> None:
    print("\n" + "=" * 50)
    print("=== World Cup Finished Sync ===\n")
    try:
        _run_world_cup_finished_sync(
            sb,
            lookback_hours=lookback_hours,
            min_profit=min_profit,
            once=once,
        )
    except Exception as exc:
        print(f"  World Cup finished sync error: {exc}")
    print("\n=== World Cup finished sync complete ===")
