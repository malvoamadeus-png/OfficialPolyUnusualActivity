# -*- coding: utf-8 -*-
"""Supabase REST client for OdailySeer.

This replaces the Python SDK dependency so the project can run on Python 3.14
without requiring packages that currently need local C++ build tools.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from packages.common.paths import PROJECT_ROOT


class _Response:
    def __init__(self, data: Any) -> None:
        self.data = data


class _QueryBuilder:
    def __init__(self, rest: "_RestClient", table_name: str) -> None:
        self._rest = rest
        self._table_name = table_name
        self._params: list[tuple[str, str]] = []
        self._headers: dict[str, str] = {}
        self._method = "GET"
        self._payload: Any = None
        self._single = False

    def select(self, columns: str) -> "_QueryBuilder":
        self._params.append(("select", columns))
        return self

    def order(self, column: str, desc: bool = False, ascending: bool | None = None, nullsFirst: bool | None = None) -> "_QueryBuilder":
        direction = "asc"
        if ascending is not None:
            direction = "asc" if ascending else "desc"
        elif desc:
            direction = "desc"
        value = f"{column}.{direction}"
        if nullsFirst is True:
            value += ".nullsfirst"
        elif nullsFirst is False:
            value += ".nullslast"
        self._params.append(("order", value))
        return self

    def limit(self, count: int) -> "_QueryBuilder":
        self._params.append(("limit", str(count)))
        return self

    def eq(self, column: str, value: Any) -> "_QueryBuilder":
        self._params.append((column, f"eq.{self._format_value(value)}"))
        return self

    def gte(self, column: str, value: Any) -> "_QueryBuilder":
        self._params.append((column, f"gte.{self._format_value(value)}"))
        return self

    def lt(self, column: str, value: Any) -> "_QueryBuilder":
        self._params.append((column, f"lt.{self._format_value(value)}"))
        return self

    def in_(self, column: str, values: list[Any]) -> "_QueryBuilder":
        encoded = ",".join(self._format_in_value(v) for v in values)
        self._params.append((column, f"in.({encoded})"))
        return self

    def is_(self, column: str, value: str) -> "_QueryBuilder":
        self._params.append((column, f"is.{value}"))
        return self

    def single(self) -> "_QueryBuilder":
        self._single = True
        self._headers["Accept"] = "application/vnd.pgrst.object+json"
        return self

    def update(self, values: dict[str, Any]) -> "_QueryBuilder":
        self._method = "PATCH"
        self._payload = values
        return self

    def delete(self) -> "_QueryBuilder":
        self._method = "DELETE"
        return self

    def upsert(self, values: Any, on_conflict: str | None = None) -> "_QueryBuilder":
        self._method = "POST"
        self._payload = values
        prefer = "resolution=merge-duplicates"
        if on_conflict:
            self._params.append(("on_conflict", on_conflict))
        self._headers["Prefer"] = prefer
        return self

    def execute(self) -> _Response:
        return self._rest.request(
            method=self._method,
            table_name=self._table_name,
            params=self._params,
            headers=self._headers,
            payload=self._payload,
            single=self._single,
        )

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    @staticmethod
    def _format_in_value(value: Any) -> str:
        if isinstance(value, str):
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        return str(value)


class _RestClient:
    def __init__(self, base_url: str, headers: dict[str, str]) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers

    def table(self, table_name: str) -> _QueryBuilder:
        return _QueryBuilder(self, table_name)

    def request(
        self,
        *,
        method: str,
        table_name: str,
        params: list[tuple[str, str]],
        headers: dict[str, str],
        payload: Any,
        single: bool,
    ) -> _Response:
        merged_headers = dict(self._headers)
        merged_headers.update(headers)

        resp = requests.request(
            method,
            f"{self._base_url}/{quote(table_name, safe='')}",
            params=params,
            headers=merged_headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code == 406 and single:
            return _Response(None)

        resp.raise_for_status()

        if not resp.text:
            return _Response(None)

        try:
            return _Response(resp.json())
        except ValueError:
            return _Response(resp.text)


class SupabaseClient:
    def __init__(self) -> None:
        env_paths = self._load_env_file()
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        self.db_url = os.getenv("SUPABASE_DB_URL")
        if not url or not key:
            checked = ", ".join(str(p) for p in env_paths)
            raise ValueError(
                "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env "
                f"(checked: {checked})"
            )

        rest_url = f"{url.rstrip('/')}/rest/v1"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        self.client = _RestClient(rest_url, headers)

    def _run_psql(self, sql: str, *, tuples_only: bool = False) -> str:
        if not self.db_url:
            raise ValueError("Missing SUPABASE_DB_URL for direct Postgres access")
        cmd = ["psql", self.db_url, "-X", "-v", "ON_ERROR_STOP=1"]
        if tuples_only:
            cmd.extend(["-A", "-t"])
        env = dict(os.environ)
        env.setdefault("PGCONNECT_TIMEOUT", "15")
        proc = subprocess.run(
            cmd,
            input=sql,
            text=True,
            capture_output=True,
            timeout=60,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "psql failed")
        return proc.stdout

    @staticmethod
    def _sql_literal(value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            numeric = float(value)
            if not math.isfinite(numeric):
                return "NULL"
            if isinstance(value, int) or numeric.is_integer():
                return str(int(numeric))
            return repr(numeric)
        text = str(value).replace("'", "''")
        return f"'{text}'"

    @staticmethod
    def _load_env_file() -> list[Path]:
        candidates = [
            Path.cwd() / ".env",
            PROJECT_ROOT / ".env",
            PROJECT_ROOT / "backend" / ".env",
            Path("/etc/odailyseer/odailyseer.env"),
        ]
        for env_path in candidates:
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
        return candidates

    def upsert_changes(self, changes: list[dict[str, Any]]) -> None:
        if not changes:
            return
        self.client.table("probability_changes").upsert(
            changes, on_conflict="market_id,change_timestamp"
        ).execute()

    def update_analysis(
        self, market_id: str, change_timestamp: int, analysis: dict[str, Any]
    ) -> None:
        self.client.table("probability_changes").update(
            {"analysis": analysis, "analyzed_at": datetime.utcnow().isoformat()}
        ).eq("market_id", market_id).eq(
            "change_timestamp", change_timestamp
        ).execute()

    def get_unanalyzed_changes(self) -> list[dict[str, Any]]:
        data = (
            self.client.table("probability_changes")
            .select("*")
            .is_("analysis", "null")
            .execute()
            .data
        )
        return data or []

    def get_recent_market_ids(self, hours: int = 48) -> set[str]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows = (
            self.client.table("probability_changes")
            .select("market_id")
            .gte("detected_at", cutoff)
            .execute()
            .data
        ) or []
        return {r["market_id"] for r in rows}

    def get_existing_new_market_slugs(self) -> set[str]:
        rows = (
            self.client.table("new_markets")
            .select("slug")
            .execute()
            .data
        ) or []
        return {r["slug"] for r in rows}

    def insert_new_markets(self, markets: list[dict[str, Any]]) -> None:
        if not markets:
            return
        self.client.table("new_markets").upsert(
            markets, on_conflict="slug"
        ).execute()

    def get_recent_whale_keys(self, hours: int = 48) -> set[tuple[str, str, str]]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows = (
            self.client.table("whale_alerts")
            .select("slug,market_question,holder_address")
            .gte("detected_at", cutoff)
            .execute()
            .data
        ) or []
        return {(r["slug"], r["market_question"], r["holder_address"]) for r in rows}

    def upsert_whale_alerts(self, alerts: list[dict[str, Any]]) -> None:
        if not alerts:
            return
        self.client.table("whale_alerts").upsert(
            alerts, on_conflict="slug,market_question,holder_address"
        ).execute()

    def delete_old_whale_alerts(self, cutoff_iso: str) -> None:
        self.client.table("whale_alerts").delete().lt("detected_at", cutoff_iso).execute()

    def get_whale_user_profiles(self, addresses: list[str]) -> dict[str, dict[str, Any]]:
        if not addresses:
            return {}

        out: dict[str, dict[str, Any]] = {}
        chunk_size = 500
        for i in range(0, len(addresses), chunk_size):
            chunk = addresses[i:i + chunk_size]
            rows = (
                self.client.table("whale_user_profiles")
                .select("holder_address,trades,join_date,last_fetched_at")
                .in_("holder_address", chunk)
                .execute()
                .data
            ) or []
            for r in rows:
                addr = r.get("holder_address")
                if addr:
                    out[addr] = r
        return out

    def upsert_whale_user_profiles(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self.client.table("whale_user_profiles").upsert(
            rows, on_conflict="holder_address"
        ).execute()

    def get_existing_trade_hashes(self) -> set[str]:
        rows = (
            self.client.table("whale_trades")
            .select("transaction_hash")
            .order("timestamp", desc=True)
            .limit(500)
            .execute()
            .data
        ) or []
        return {r["transaction_hash"] for r in rows}

    def insert_whale_trades(self, trades: list[dict[str, Any]]) -> None:
        if not trades:
            return
        self.client.table("whale_trades").upsert(
            trades, on_conflict="transaction_hash"
        ).execute()

    def delete_old_whale_trades(self, cutoff_ts: int) -> None:
        self.client.table("whale_trades").delete().lt("timestamp", cutoff_ts).execute()

    def get_existing_late_market_slugs(self) -> set[str]:
        rows = (
            self.client.table("late_markets")
            .select("slug")
            .execute()
            .data
        ) or []
        return {r["slug"] for r in rows}

    def get_late_markets(self) -> list[dict[str, Any]]:
        rows = (
            self.client.table("late_markets")
            .select("slug,title,end_date,category")
            .execute()
            .data
        ) or []
        return rows

    def delete_expired_late_markets(self, cutoff_iso: str) -> None:
        self.client.table("late_markets").delete().lt("end_date", cutoff_iso).execute()

    def delete_late_markets_by_slugs(self, slugs: list[str]) -> None:
        if not slugs:
            return
        self.client.table("late_markets").delete().in_("slug", slugs).execute()

    def insert_late_markets(self, markets: list[dict[str, Any]]) -> None:
        if not markets:
            return
        self.client.table("late_markets").upsert(
            markets, on_conflict="slug"
        ).execute()

    def get_world_cup_address_metrics(
        self, addresses: list[str]
    ) -> dict[str, Any]:
        if not addresses:
            return {}

        out: dict[str, Any] = {}
        # Keep the generated REST query URL below common proxy limits.
        chunk_size = 20
        for i in range(0, len(addresses), chunk_size):
            chunk = addresses[i:i + chunk_size]
            try:
                rows = (
                    self.client.table("world_cup_address_metrics")
                    .select("*")
                    .in_("address", chunk)
                    .execute()
                    .data
                ) or []
            except requests.RequestException:
                rows = []
            for row in rows:
                address = str(row.get("address") or "").lower()
                if address:
                    out[address] = row
        return out

    def upsert_world_cup_address_metrics(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self.client.table("world_cup_address_metrics").upsert(
            rows, on_conflict="address"
        ).execute()

    def get_world_cup_match_board_slugs(self) -> list[str]:
        rows = (
            self.client.table("world_cup_match_boards")
            .select("event_slug")
            .execute()
            .data
        ) or []
        return [str(row.get("event_slug") or "") for row in rows if row.get("event_slug")]

    def upsert_world_cup_match_boards(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self.client.table("world_cup_match_boards").upsert(
            rows, on_conflict="event_slug"
        ).execute()

    def delete_world_cup_match_boards_by_event_slugs(self, event_slugs: list[str]) -> None:
        if not event_slugs:
            return
        self.client.table("world_cup_match_boards").delete().in_("event_slug", event_slugs).execute()

    def get_world_cup_finished_scanned_event_slugs(self, event_slugs: list[str]) -> set[str]:
        if not event_slugs:
            return set()
        out: set[str] = set()
        chunk_size = 100
        for i in range(0, len(event_slugs), chunk_size):
            chunk = event_slugs[i:i + chunk_size]
            values = ", ".join(self._sql_literal(slug) for slug in chunk)
            sql = (
                "SELECT event_slug "
                "FROM world_cup_finished_events "
                f"WHERE event_slug IN ({values});"
            )
            raw = self._run_psql(sql, tuples_only=True)
            for line in raw.splitlines():
                slug = line.strip()
                if slug:
                    out.add(slug)
        return out

    def upsert_world_cup_finished_events(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        columns = [
            "event_slug",
            "event_id",
            "event_title",
            "event_end_time",
            "event_url",
            "markets_scanned",
            "results_count",
            "scanned_at",
        ]
        values_sql = ",\n".join(
            "(" + ", ".join(self._sql_literal(row.get(column)) for column in columns) + ")"
            for row in rows
        )
        update_columns = [column for column in columns if column != "event_slug"]
        updates_sql = ", ".join(f"{column}=EXCLUDED.{column}" for column in update_columns)
        sql = (
            "INSERT INTO world_cup_finished_events "
            f"({', '.join(columns)}) VALUES\n{values_sql}\n"
            "ON CONFLICT (event_slug) DO UPDATE SET "
            f"{updates_sql};"
        )
        self._run_psql(sql)

    def upsert_world_cup_finished_positions(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        columns = [
            "event_slug",
            "event_title",
            "event_end_time",
            "event_url",
            "board_type",
            "market_slug",
            "condition_id",
            "market_question",
            "market_label",
            "outcome_name",
            "address",
            "bet_amount",
            "profit_amount",
            "position_closed_at",
            "scanned_at",
        ]
        values_sql = ",\n".join(
            "(" + ", ".join(self._sql_literal(row.get(column)) for column in columns) + ")"
            for row in rows
        )
        update_columns = [column for column in columns if column not in {"event_slug", "market_slug", "address", "market_label"}]
        updates_sql = ", ".join(f"{column}=EXCLUDED.{column}" for column in update_columns)
        sql = (
            "INSERT INTO world_cup_finished_positions "
            f"({', '.join(columns)}) VALUES\n{values_sql}\n"
            "ON CONFLICT (event_slug, market_slug, address, market_label) DO UPDATE SET "
            f"{updates_sql};"
        )
        self._run_psql(sql)
