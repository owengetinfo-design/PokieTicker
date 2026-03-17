"""Daily news fetcher for Chinese stocks.

Run this daily to accumulate news over time:
    python backend/daily_news_fetch.py

Or set up a cron job:
    0 18 * * 1-5 cd /path/to/pokieticker && python backend/daily_news_fetch.py
"""

import sys
sys.path.insert(0, '/Users/mecilmeng/Homework/AI_Projects/PokieTicker')

from backend.database import get_conn
from backend.data_sources import get_market
from backend.data_sources.cn_news_client import MultiSourceCNNewsClient
from backend.pipeline.alignment import align_news_for_symbol
from backend.pipeline.layer0 import run_layer0
from backend.pipeline.layer1 import run_layer1


def fetch_and_process_cn_news(symbol: str) -> dict:
    """Fetch news for a Chinese stock and process through pipeline."""
    print(f"\n=== Processing {symbol} ===")

    # Fetch news
    client = MultiSourceCNNewsClient()
    articles = client.fetch_stock_news(symbol, limit=100)
    print(f"Fetched {len(articles)} articles")

    if not articles:
        return {"symbol": symbol, "new_articles": 0}

    # Store in database
    conn = get_conn()
    new_count = 0

    for art in articles:
        # Check if already exists
        existing = conn.execute(
            "SELECT 1 FROM news_raw WHERE id = ?",
            (art['id'],)
        ).fetchone()

        if not existing:
            conn.execute(
                """INSERT INTO news_raw
                   (id, title, description, publisher, author,
                    published_utc, article_url, amp_url, tickers_json, insights_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (art['id'], art['title'], art['description'],
                 art['publisher'], art['author'], art['published_utc'],
                 art['article_url'], art['amp_url'],
                 str(art['tickers']).replace("'", '"'),
                 None)
            )

            # Link to ticker
            for ticker in art['tickers']:
                conn.execute(
                    "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                    (art['id'], ticker)
                )
            new_count += 1

    conn.commit()
    conn.close()

    print(f"New articles stored: {new_count}")

    if new_count > 0:
        # Run pipeline
        print("Running alignment...")
        align_news_for_symbol(symbol)

        print("Running Layer 0...")
        l0 = run_layer0(symbol)
        print(f"  Layer0: {l0.get('passed', 0)}/{l0.get('total', 0)} passed")

        print("Running Layer 1...")
        l1 = run_layer1(symbol)
        print(f"  Layer1: {l1.get('processed', 0)} processed, {l1.get('relevant', 0)} relevant")

    return {
        "symbol": symbol,
        "fetched": len(articles),
        "new_articles": new_count
    }


def main():
    """Fetch news for all CN/HK stocks in database."""
    conn = get_conn()

    # Get all CN/HK stocks
    rows = conn.execute(
        "SELECT symbol FROM tickers WHERE market IN ('CN', 'HK') ORDER BY symbol"
    ).fetchall()

    symbols = [r['symbol'] for r in rows]
    conn.close()

    print(f"=== Daily News Fetch for {len(symbols)} Chinese stocks ===")

    results = []
    for symbol in symbols:
        try:
            result = fetch_and_process_cn_news(symbol)
            results.append(result)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            results.append({"symbol": symbol, "error": str(e)})

    print("\n=== Summary ===")
    total_new = sum(r.get('new_articles', 0) for r in results)
    print(f"Total new articles: {total_new}")


if __name__ == "__main__":
    main()
