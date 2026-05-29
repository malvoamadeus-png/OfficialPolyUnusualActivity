# -*- coding: utf-8 -*-
"""Whale Trades: fetch large trades from Polymarket data API."""

from __future__ import annotations

import requests

from packages.common.supabase_client import SupabaseClient

API_URL = "https://data-api.polymarket.com/trades"
PARAMS = {
    "takerOnly": "true",
    "limit": 50,
    "offset": 0,
    "filterType": "CASH",
    "filterAmount": 10000,
}


def _run_whale_trades(sb: SupabaseClient):
    print("[1/3] Fetching large trades from Polymarket...")
    resp = requests.get(API_URL, params=PARAMS, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    print(f"  Got {len(raw)} trades")

    if not raw:
        print("  No trades found.")
        return

    print("[2/3] Deduplicating...")
    existing = sb.get_existing_trade_hashes()
    new_trades = []
    for t in raw:
        tx = t.get("transactionHash", "")
        if not tx or tx in existing:
            continue
        new_trades.append({
            "transaction_hash": tx,
            "proxy_wallet": t.get("proxyWallet", ""),
            "name": t.get("name") or t.get("pseudonym") or None,
            "side": t.get("side", ""),
            "size": float(t.get("size", 0)),
            "price": float(t.get("price", 0)),
            "outcome": t.get("outcome"),
            "title": t.get("title", ""),
            "slug": t.get("slug", ""),
            "event_slug": t.get("eventSlug"),
            "icon": t.get("icon"),
            "timestamp": int(t.get("timestamp", 0)),
        })

    print(f"  {len(new_trades)} new trades (skipped {len(raw) - len(new_trades)} duplicates)")

    if not new_trades:
        return

    print(f"[3/3] Uploading {len(new_trades)} trades...")
    sb.insert_whale_trades(new_trades)
    print(f"  Done. Uploaded {len(new_trades)} rows")

    for i, t in enumerate(new_trades[:5], 1):
        print(f"  {i}. [{t['side']}] ${t['size']:,.0f} @ {t['price']} | {t['title'][:50]}")


def run_whale_trades(sb: SupabaseClient):
    """Entry point called from pipeline."""
    print("\n" + "=" * 50)
    print("=== Whale Trades: Fetch → Dedup → Upload ===\n")
    try:
        _run_whale_trades(sb)
    except Exception as e:
        print(f"  Whale trades error: {e}")
    print("\n=== Whale trades complete ===")


if __name__ == "__main__":
    sb = SupabaseClient()
    run_whale_trades(sb)
