#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch latest events from Polymarket /new page using Playwright."""

import json
import time


def fetch_latest_events() -> list[dict]:
    """Fetch latest events from Polymarket /new page using headless browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: playwright not installed")
        print("Install with: pip install playwright")
        print("Then run: playwright install chromium")
        return []

    questions = []

    with sync_playwright() as p:
        import os
        proxy_url = os.environ.get("https_proxy") or os.environ.get("http_proxy")
        launch_opts = {"headless": True}
        if proxy_url:
            launch_opts["proxy"] = {"server": proxy_url}
        browser = p.chromium.launch(**launch_opts)
        page = browser.new_page()

        # Set longer timeout
        page.set_default_timeout(60000)

        print("Loading https://polymarket.com/new ...")
        try:
            page.goto("https://polymarket.com/new", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Error loading page: {e}")
            browser.close()
            return []

        # Wait for market cards to load (adjust selector if needed)
        print("Waiting for content to load...")
        time.sleep(5)

        # Extract all market links
        links = page.query_selector_all('a[href^="/event/"]')

        print(f"Found {len(links)} market links")

        for link in links:
            href = link.get_attribute("href")
            text = link.text_content().strip()

            if href and text:
                # Extract slug from href
                slug = href.replace("/event/", "").split("?")[0]
                questions.append({
                    "slug": slug,
                    "question": text,
                    "url": f"https://polymarket.com{href}",
                })

        browser.close()

    return questions


def main():
    print("Fetching latest events from Polymarket /new page...\n")
    questions = fetch_latest_events()

    # Deduplicate by slug
    seen = set()
    unique_questions = []
    for q in questions:
        if q["slug"] not in seen:
            seen.add(q["slug"])
            unique_questions.append(q)

    print(f"\nFound {len(unique_questions)} unique events\n")

    # Save to JSON
    output_file = "latest_questions.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(unique_questions, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_file}")

    # Preview first 5
    if unique_questions:
        print("\nPreview (first 5):")
        for i, q in enumerate(unique_questions[:5], 1):
            print(f"{i}. {q['question']}")
    else:
        print("\nNo questions found.")


if __name__ == "__main__":
    main()
