# -*- coding: utf-8 -*-
"""Unified OdailySeer backend CLI."""

from __future__ import annotations

import argparse

from packages.common.supabase_client import SupabaseClient
from packages.polymarket.anomaly import run_anomaly
from packages.polymarket.late_markets import run_late_markets
from packages.polymarket.late_markets_probe import main as run_late_markets_probe
from packages.polymarket.market_api import run_market_api
from packages.polymarket.new_markets import run_new_markets
from packages.polymarket.whale_monitor import run_whale_monitor
from packages.polymarket.whale_trades import run_whale_trades
from packages.polymarket.world_cup import run_world_cup
from src.scheduler import run_scheduler


def _add_once(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--once", action="store_true", help="Run in reduced test mode")


def main() -> None:
    parser = argparse.ArgumentParser(description="OdailySeer backend")
    sub = parser.add_subparsers(dest="command", required=True)

    scheduler = sub.add_parser("scheduler", help="Run scheduler")
    _add_once(scheduler)
    scheduler.add_argument("--loop", action="store_true", help="Run scheduled loop")

    sub.add_parser("run-once", help="Run all pipelines once")
    sub.add_parser("anomaly", help="Run anomaly pipeline")
    new_markets = sub.add_parser("new-markets", help="Run new markets pipeline")
    _add_once(new_markets)
    late_markets = sub.add_parser("late-markets", help="Run late markets pipeline")
    _add_once(late_markets)
    whale = sub.add_parser("whale", help="Run whale monitor pipeline")
    _add_once(whale)
    world_cup = sub.add_parser("world-cup", help="Run world cup pipeline")
    _add_once(world_cup)
    sub.add_parser("whale-trades", help="Run whale trades pipeline")
    sub.add_parser("late-markets-probe", help="Write a late markets probe JSON file")
    market_api = sub.add_parser("market-api", help="Run market analyzer API")
    market_api.add_argument("--host", default="0.0.0.0")
    market_api.add_argument("--port", type=int, default=8917)

    args = parser.parse_args()

    if args.command == "scheduler":
        run_scheduler(once=args.once, loop=args.loop)
    elif args.command == "run-once":
        run_scheduler(once=True, loop=False)
    elif args.command == "anomaly":
        run_anomaly()
    elif args.command == "new-markets":
        run_new_markets(SupabaseClient(), once=args.once)
    elif args.command == "late-markets":
        run_late_markets(SupabaseClient(), once=args.once)
    elif args.command == "whale":
        run_whale_monitor(SupabaseClient(), once=args.once)
    elif args.command == "world-cup":
        run_world_cup(SupabaseClient(), once=args.once)
    elif args.command == "whale-trades":
        run_whale_trades(SupabaseClient())
    elif args.command == "late-markets-probe":
        run_late_markets_probe()
    elif args.command == "market-api":
        run_market_api(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
