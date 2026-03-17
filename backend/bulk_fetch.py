"""Bulk fetch OHLC + news for all tickers missing data.

Polygon free tier: 5 requests/minute for US stocks.
Tushare/AKShare for CN/HK stocks (no strict rate limit but be respectful).
Strategy: fetch OHLC (1 call) + news per ticker, with rate limiting.
"""

import json
import time
import sys
from datetime import datetime, timedelta, timezone

from backend.config import settings
from backend.database import get_conn
from backend.data_sources import fetch_ohlc, fetch_news, get_market
from backend.data_sources.polygon_client import http_get, BASE
from backend.data_sources.tushare_client import TushareClient
from backend.pipeline.alignment import align_news_for_symbol
from backend.pipeline.layer0 import run_layer0

# 2 years of data
TODAY = datetime.now(timezone.utc).date()
START = (TODAY - timedelta(days=2 * 366)).isoformat()
END = TODAY.isoformat()

# Rate limit: keep a rolling window
REQUEST_TIMES = []
MAX_PER_MIN = 5
SAFETY_SLEEP = 0.5  # extra buffer between calls


def rate_limit():
    """Block until we can make another request within Polygon's rate limit."""
    global REQUEST_TIMES
    now = time.time()
    # Remove entries older than 60 seconds
    REQUEST_TIMES = [t for t in REQUEST_TIMES if now - t < 60]
    if len(REQUEST_TIMES) >= MAX_PER_MIN:
        wait = 60 - (now - REQUEST_TIMES[0]) + SAFETY_SLEEP
        if wait > 0:
            print(f"    Rate limit: waiting {wait:.1f}s...")
            time.sleep(wait)
    REQUEST_TIMES.append(time.time())


def fetch_ticker_name(symbol: str) -> str:
    """Fetch company name from appropriate data source."""
    market = get_market(symbol)

    if market == 'US':
        rate_limit()
        try:
            url = f"{BASE}/v3/reference/tickers/{symbol}"
            resp = http_get(url)
            data = resp.json()
            results = data.get("results", {})
            return results.get("name", "")
        except Exception as e:
            print(f"  Warning: could not fetch name for {symbol}: {e}")
            return ""
    elif market == 'CN':
        try:
            client = TushareClient()
            info = client.get_stock_basic_cn(symbol)
            return info.get('name', '') if info else ''
        except Exception as e:
            print(f"  Warning: could not fetch name for {symbol}: {e}")
            return ""
    elif market == 'HK':
        try:
            client = TushareClient()
            info = client.get_stock_basic_hk(symbol)
            return info.get('name', '') if info else ''
        except Exception as e:
            print(f"  Warning: could not fetch name for {symbol}: {e}")
            return ""
    return ""


def fetch_and_store_ohlc(symbol: str) -> int:
    """Fetch OHLC data and store in database. Returns row count."""
    market = get_market(symbol)

    # Rate limiting only for US stocks (Polygon)
    if market == 'US':
        rate_limit()

    try:
        rows = fetch_ohlc(symbol, START, END)
    except Exception as e:
        print(f"  OHLC error for {symbol}: {e}")
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
        (END, symbol),
    )
    conn.commit()
    conn.close()
    return len(rows)


def fetch_and_store_news(symbol: str) -> int:
    """Fetch news and store in database. Returns article count."""
    market = get_market(symbol)

    # Fetch news using appropriate source
    if market == 'US':
        # Polygon news (paginated)
        all_articles = []
        seen_ids = set()
        url = f"{BASE}/v2/reference/news"
        params = {
            "ticker": symbol,
            "published_utc.gte": START,
            "published_utc.lte": END,
            "limit": 50,
            "order": "asc",
        }
        next_url = None
        pages = 0

        while True:
            rate_limit()
            try:
                resp = http_get(next_url or url, params=None if next_url else params)
            except Exception as e:
                print(f"  News error for {symbol} (page {pages}): {e}")
                break

            data = resp.json()
            results = data.get("results") or []
            if not results:
                break

            for r in results:
                rid = r.get("id")
                if rid and rid in seen_ids:
                    continue
                article = {
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
                }
                all_articles.append(article)
                if rid:
                    seen_ids.add(rid)

            next_url = data.get("next_url")
            pages += 1
            if not next_url:
                break
    else:
        # CN/HK stocks use AKShare
        try:
            all_articles = fetch_news(symbol, START, END)
        except Exception as e:
            print(f"  News error for {symbol}: {e}")
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
        (END, symbol),
    )
    conn.commit()
    conn.close()
    return len(all_articles)


def main():
    conn = get_conn()

    # Get tickers that haven't been fetched yet
    rows = conn.execute(
        "SELECT symbol FROM tickers WHERE last_ohlc_fetch IS NULL ORDER BY symbol"
    ).fetchall()
    conn.close()

    pending = [r["symbol"] for r in rows]
    print(f"=== Bulk Fetch: {len(pending)} tickers pending ===")
    print(f"Date range: {START} to {END}")
    print(f"Rate limit: {MAX_PER_MIN} req/min\n")

    total_ohlc = 0
    total_news = 0
    errors = []

    for idx, symbol in enumerate(pending, 1):
        market = get_market(symbol)
        print(f"[{idx}/{len(pending)}] {symbol} ({market})")

        # Fetch company name if missing
        conn = get_conn()
        name = conn.execute(
            "SELECT name FROM tickers WHERE symbol = ?", (symbol,)
        ).fetchone()
        conn.close()

        if not name or not name["name"]:
            company_name = fetch_ticker_name(symbol)
            if company_name:
                conn = get_conn()
                conn.execute(
                    "UPDATE tickers SET name = ? WHERE symbol = ?",
                    (company_name, symbol),
                )
                conn.commit()
                conn.close()
                print(f"  Name: {company_name}")

        # Fetch OHLC
        ohlc_count = fetch_and_store_ohlc(symbol)
        print(f"  OHLC: {ohlc_count} rows")
        total_ohlc += ohlc_count

        if ohlc_count == 0:
            print(f"  WARNING: No OHLC data, possibly delisted or invalid ticker")
            errors.append(symbol)
            continue

        # Fetch news
        news_count = fetch_and_store_news(symbol)
        print(f"  News: {news_count} articles")
        total_news += news_count

        # Run alignment + layer 0
        try:
            align_news_for_symbol(symbol)
            l0 = run_layer0(symbol)
            passed = l0.get("passed", 0)
            total = l0.get("total", 0)
            print(f"  Layer0: {passed}/{total} passed")
        except Exception as e:
            print(f"  Alignment/Layer0 error: {e}")

        print()

    print(f"\n=== DONE ===")
    print(f"Total OHLC rows: {total_ohlc}")
    print(f"Total news articles: {total_news}")
    if errors:
        print(f"Errors ({len(errors)}): {', '.join(errors)}")


if __name__ == "__main__":
    main()
