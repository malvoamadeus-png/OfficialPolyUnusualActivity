#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared filtering rules for late markets ingestion."""

from __future__ import annotations

from typing import Iterable

EXCLUDED_CATEGORY_SLUGS = {
    "baseball",
    "basketball",
    "bitcoin",
    "boxing",
    "champions-league",
    "counter-strike",
    "cricket",
    "crypto",
    "crypto-prices",
    "cs2",
    "dota-2",
    "esports",
    "ethereum",
    "football",
    "golf",
    "league-of-legends",
    "lol",
    "mma",
    "nba",
    "nfl",
    "nhl",
    "olympics",
    "pga",
    "soccer",
    "sports",
    "tennis",
    "uefa",
    "wnba",
}

EXCLUDED_TITLE_KEYWORDS = (
    "bitcoin",
    "btc",
    "crypto",
    "cryptocurrency",
    "ethereum",
    "eth ",
    "solana",
    "sol ",
    "dogecoin",
    "doge",
    "nba",
    "wnba",
    "nfl",
    "nhl",
    "mlb",
    "ufc",
    "mma",
    "formula 1",
    "f1 ",
    "champions league",
    "uefa",
    "premier league",
    "la liga",
    "serie a",
    "bundesliga",
    "french open",
    "wimbledon",
    "counter-strike",
    "counter strike",
    "cs2",
    "league of legends",
    "lol:",
    "dota",
    "valorant",
)


def normalize_token(value: str | None) -> str:
    return (value or "").strip().lower()


def is_excluded_late_market(
    *,
    title: str | None,
    category: str | None = None,
    tags: Iterable[str] | None = None,
) -> bool:
    normalized_title = normalize_token(title)
    normalized_tokens = {normalize_token(category)}
    normalized_tokens.update(normalize_token(tag) for tag in tags or [])
    normalized_tokens.discard("")

    if normalized_tokens & EXCLUDED_CATEGORY_SLUGS:
        return True

    return any(keyword in normalized_title for keyword in EXCLUDED_TITLE_KEYWORDS)
