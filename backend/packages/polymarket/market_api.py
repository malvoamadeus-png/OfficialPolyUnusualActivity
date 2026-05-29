# -*- coding: utf-8 -*-
"""Market Analyzer API — FastAPI service for real-time Polymarket analysis."""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover - lets non-API commands run without FastAPI.
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    CORSMiddleware = None  # type: ignore[assignment]

from packages.common.supabase_client import SupabaseClient

if FastAPI is not None and CORSMiddleware is not None:
    app = FastAPI(title="OdailySeer Market API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
else:
    app = None

CACHE_TTL_MINUTES = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://polymarketanalytics.com/",
}

# ── Polymarket data fetchers ──────────────────────────────

def get_market_by_slug(slug: str) -> dict[str, Any]:
    r = requests.get(
        f"https://gamma-api.polymarket.com/markets?slug={slug}", timeout=15
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data:
        return data[0]
    raise ValueError(f"Market not found: {slug}")


def get_top_holders(condition_id: str, limit: int = 5) -> list[dict]:
    r = requests.get(
        f"https://data-api.polymarket.com/holders?market={condition_id}&limit={limit}",
        timeout=15,
    )
    r.raise_for_status()
    return r.json()
# PLACEHOLDER_MARKET_API_CONTINUE


def get_trader_profile(address: str) -> dict[str, Any] | None:
    try:
        r = requests.get(
            f"https://polymarketanalytics.com/api/traders-dashboard?trader_id={address}",
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success") and data.get("data"):
            return data["data"][0]
    except Exception:
        pass
    return None


def get_user_stats(address: str) -> dict[str, Any] | None:
    """Fetch trades count from Polymarket official API."""
    try:
        r = requests.get(
            f"https://data-api.polymarket.com/v1/user-stats?proxyAddress={address}",
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data:
            return {"trades": data.get("trades")}
    except Exception:
        pass
    return None


def fetch_market_data(slug: str) -> dict[str, Any]:
    """Fetch full market analysis from Polymarket APIs."""
    market = get_market_by_slug(slug)
    question = market["question"]
    outcomes = json.loads(market["outcomes"])
    prices = json.loads(market["outcomePrices"])
    condition_id = market["conditionId"]
    token_ids = json.loads(market["clobTokenIds"])

    holders_data = get_top_holders(condition_id, limit=5)

    sides = []
    for idx, outcome in enumerate(outcomes):
        price = float(prices[idx])
        token_id = token_ids[idx]

        holders_group = []
        for group in holders_data:
            if group["token"] == token_id:
                holders_group = group.get("holders", [])
                break

        holders = []
        for h in holders_group:
            address = h.get("proxyWallet", "")
            name = h.get("name") or h.get("pseudonym") or "Anonymous"
            amount = h.get("amount", 0)

            profile = get_trader_profile(address)
            user_stats = get_user_stats(address)
            holders.append({
                "address": address,
                "name": name,
                "amount": amount,
                "win_rate": profile.get("win_rate") if profile else None,
                "total_positions": profile.get("total_positions") if profile else None,
                "pnl": profile.get("overall_gain") if profile else None,
                "tags": profile.get("tags", "") if profile else None,
                "trades": user_stats.get("trades") if user_stats else None,
            })

        sides.append({"name": outcome, "price": price, "holders": holders})

    return {"question": question, "slug": slug, "sides": sides}
# PLACEHOLDER_ENDPOINT


# ── Supabase cache ────────────────────────────────────────

_sb: SupabaseClient | None = None


def get_sb() -> SupabaseClient:
    global _sb
    if _sb is None:
        _sb = SupabaseClient()
    return _sb


def get_cached(slug: str) -> dict[str, Any] | None:
    """Return cached analysis if fresh enough."""
    try:
        row = (
            get_sb().client.table("market_analysis")
            .select("*")
            .eq("slug", slug)
            .single()
            .execute()
        )
        if row.data:
            updated = row.data.get("analyzed_at")
            if updated:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - ts < timedelta(minutes=CACHE_TTL_MINUTES):
                    return row.data
    except Exception:
        pass
    return None


def save_cache(slug: str, data: dict[str, Any]) -> None:
    """Upsert analysis result into Supabase."""
    try:
        get_sb().client.table("market_analysis").upsert(
            {
                "slug": slug,
                "question": data["question"],
                "sides": data["sides"],
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="slug",
        ).execute()
    except Exception as e:
        print(f"Warning: cache write failed: {e}")


# ── API endpoint ──────────────────────────────────────────

if app is not None:
    @app.get("/api/analyze")
    def analyze(slug: str = Query(..., description="Market slug or full URL")):
        return analyze_market(slug)


def analyze_market(slug: str) -> dict[str, Any]:
    # Support full URL input — extract slug from last path segment
    if "/" in slug:
        slug = slug.rstrip("/").split("/")[-1]

    if not slug:
        raise HTTPException(400, "slug is required")  # type: ignore[misc]

    # Check cache
    cached = get_cached(slug)
    if cached:
        return {
            "question": cached["question"],
            "slug": cached["slug"],
            "sides": cached["sides"],
            "cached": True,
        }

    # Fetch live data
    try:
        result = fetch_market_data(slug)
    except ValueError as e:
        raise HTTPException(404, str(e))  # type: ignore[misc]
    except Exception as e:
        raise HTTPException(502, f"Upstream API error: {e}")  # type: ignore[misc]

    save_cache(slug, result)
    return {**result, "cached": False}


def run_market_api(host: str = "0.0.0.0", port: int = 8917) -> None:
    if app is None:
        raise RuntimeError("FastAPI dependencies are not installed. Run pip install -r backend/requirements.txt")
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_market_api()
