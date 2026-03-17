"""Weekly incremental update: fetch new OHLC + news for all active tickers.

Only fetches data newer than the last fetch date for each ticker.
Run manually or via cron: python -m backend.weekly_update

Cron example (every Sunday at 2am):
  0 2 * * 0 cd /path/to/PokieTicker && python -m backend.weekly_update >> logs/weekly.log 2>&1
"""

import json
import time
import sys
from datetime import datetime, timedelta, timezone

from backend.config import settings
from backend.database import get_conn
from backend.data_sources import fetch_ohlc, fetch_news, get_market
from backend.data_sources.polygon_client import http_get, BASE
from backend.pipeline.alignment import align_news_for_symbol
from backend.pipeline.layer0 import run_layer0

TODAY = datetime.now(timezone.utc).date().isoformat()

# Rate limiting
REQUEST_TIMES = []
MAX_PER_MIN = 5
SAFETY_SLEEP = 0.5


def rate_limit():
    global REQUEST_TIMES
    now = time.time()
    REQUEST_TIMES = [t for t in REQUEST_TIMES if now - t < 60]
    if len(REQUEST_TIMES) >= MAX_PER_MIN:
        wait = 60 - (now - REQUEST_TIMES[0]) + SAFETY_SLEEP
        if wait > 0:
            time.sleep(wait)
    REQUEST_TIMES.append(time.time())


def update_ohlc(symbol: str, last_fetch: str) -> int:
    """Fetch OHLC data from day after last fetch to today."""
    start = (datetime.fromisoformat(last_fetch) + timedelta(days=1)).date().isoformat()
    if start > TODAY:
        return 0

    market = get_market(symbol)
    if market == 'US':
        rate_limit()

    try:
        rows = fetch_ohlc(symbol, start, TODAY)
    except Exception as e:
        print(f"  OHLC error: {e}")
        return 0

    if not rows:
        return 0

    conn = get_conn()
    for row in rows:
        conn.execute(
            """INSERT OR IGNORE INTO ohlc
               (symbol, date, open, high, low, close, volume, vwap, transactions)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, row["date"], row["open"], row["high"], row["low"],
             row["close"], row["volume"], row["vwap"], row["transactions"]),
        )
    conn.execute(
        "UPDATE tickers SET last_ohlc_fetch = ? WHERE symbol = ?",
        (TODAY, symbol),
    )
    conn.commit()
    conn.close()
    return len(rows)


def update_news(symbol: str, last_fetch: str) -> int:
    """Fetch news from day after last fetch to today."""
    start = (datetime.fromisoformat(last_fetch) + timedelta(days=1)).date().isoformat()
    if start > TODAY:
        return 0

    market = get_market(symbol)

    if market == 'US':
        # Polygon news for US stocks
        all_articles = []
        seen_ids = set()
        url = f"{BASE}/v2/reference/news"
        params = {
            "ticker": symbol,
            "published_utc.gte": start,
            "published_utc.lte": TODAY,
            "limit": 50,
            "order": "asc",
        }
        next_url = None

        while True:
            rate_limit()
            try:
                resp = http_get(next_url or url, params=None if next_url else params)
            except Exception as e:
                print(f"  News error: {e}")
                break

            data = resp.json()
            results = data.get("results") or []
            if not results:
                break

            for r in results:
                rid = r.get("id")
                if rid and rid in seen_ids:
                    continue
                all_articles.append({
                    "id": rid,
                    "publisher": (r.get("publisher") or {}).get("name"),
                    "title": r.get("title"),
                    "author": r.get("author"),
                    "published_utc": r.get("published_utc"),
                    "amp_url": r.get("amp_url"),
                    "article_url": r.get("article_url"),
                    "tickers": r.get("tickers"),
                    "description": r.get("description"),
                    "insights": r.get("insights"),
                })
                if rid:
                    seen_ids.add(rid)

            next_url = data.get("next_url")
            if not next_url:
                break
    else:
        # CN/HK stocks use AKShare
        try:
            all_articles = fetch_news(symbol, start, TODAY)
        except Exception as e:
            print(f"  News error: {e}")
            all_articles = []

    if not all_articles:
        return 0

    conn = get_conn()
    for art in all_articles:
        news_id = art.get("id")
        if not news_id:
            continue
        tickers = art.get("tickers") or []
        conn.execute(
            """INSERT OR IGNORE INTO news_raw
               (id, title, description, publisher, author,
                published_utc, article_url, amp_url, tickers_json, insights_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (news_id, art.get("title"), art.get("description"),
             art.get("publisher"), art.get("author"), art.get("published_utc"),
             art.get("article_url"), art.get("amp_url"),
             json.dumps(tickers),
             json.dumps(art.get("insights")) if art.get("insights") else None),
        )
        for tk in tickers:
            conn.execute(
                "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                (news_id, tk),
            )

    conn.execute(
        "UPDATE tickers SET last_news_fetch = ? WHERE symbol = ?",
        (TODAY, symbol),
    )
    conn.commit()
    conn.close()
    return len(all_articles)


def main():
    print(f"=== Weekly Update: {TODAY} ===\n")

    conn = get_conn()
    tickers = conn.execute(
        "SELECT symbol, last_ohlc_fetch, last_news_fetch FROM tickers WHERE last_ohlc_fetch IS NOT NULL ORDER BY symbol"
    ).fetchall()
    conn.close()

    total_ohlc = 0
    total_news = 0

    for i, t in enumerate(tickers, 1):
        symbol = t["symbol"]
        ohlc_fetch = t["last_ohlc_fetch"] or "2024-01-01"
        news_fetch = t["last_news_fetch"] or ohlc_fetch
        market = get_market(symbol)

        # Skip if already updated today
        if ohlc_fetch >= TODAY and news_fetch >= TODAY:
            continue

        print(f"[{i}/{len(tickers)}] {symbol} ({market})")

        # Update OHLC
        ohlc_count = update_ohlc(symbol, ohlc_fetch)
        if ohlc_count > 0:
            print(f"  OHLC: +{ohlc_count} rows")
        total_ohlc += ohlc_count

        # Update news
        news_count = update_news(symbol, news_fetch)
        if news_count > 0:
            print(f"  News: +{news_count} articles")
        total_news += news_count

        # Run alignment + layer 0 for new articles
        if news_count > 0:
            try:
                align_news_for_symbol(symbol)
                l0 = run_layer0(symbol)
                print(f"  Layer0: {l0.get('passed', 0)} new passed")
            except Exception as e:
                print(f"  Pipeline error: {e}")

    print(f"\n=== Done ===")
    print(f"Updated OHLC: +{total_ohlc} rows")
    print(f"Updated News: +{total_news} articles")
    print(f"\nNote: Run 'python -m backend.batch_submit' to process new articles through Layer 1")


if __name__ == "__main__":
    main()
