import logging

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from backend.database import get_conn
from backend.data_sources import (
    fetch_ohlc,
    fetch_news,
    search_tickers,
    get_market,
)
from backend.data_sources.tushare_client import TushareClient
from backend.pipeline.alignment import align_news_for_symbol
from backend.pipeline.layer0 import run_layer0

router = APIRouter()


class AddTickerRequest(BaseModel):
    symbol: str
    name: Optional[str] = None


@router.get("")
def list_tickers(market: Optional[str] = None):
    """List all tracked tickers, optionally filtered by market."""
    conn = get_conn()
    if market:
        rows = conn.execute(
            "SELECT * FROM tickers WHERE market = ? ORDER BY symbol",
            (market.upper(),)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tickers ORDER BY symbol").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _search_cn_stocks(query: str) -> list[dict]:
    """Search A-share stocks via Tushare."""
    try:
        client = TushareClient()
        return client.search_stock(query)
    except Exception as e:
        logger.debug("Tushare CN search failed for query=%s: %s", query, e)
        return []


def _search_hk_stocks(query: str) -> list[dict]:
    """Search HK stocks via Tushare."""
    try:
        client = TushareClient()
        return client.search_hk_stock(query)
    except Exception as e:
        logger.debug("Tushare HK search failed for query=%s: %s", query, e)
        return []


@router.get("/search")
def search(q: str = Query(..., min_length=1)):
    """Multi-market fuzzy search for tickers.

    Supports:
    - US stocks via Polygon
    - A-shares (.SH/.SZ) via Tushare
    - HK stocks (.HK) via Tushare
    """
    # First check local DB
    conn = get_conn()
    local = conn.execute(
        """SELECT symbol, name, sector, market FROM tickers
           WHERE symbol LIKE ? OR name LIKE ? LIMIT 10""",
        (f"%{q}%", f"%{q}%"),
    ).fetchall()
    conn.close()

    results = [dict(r) for r in local]

    # If few local results, search appropriate data source
    if len(results) < 5:
        try:
            # Detect market based on query format
            if q.isdigit():
                if len(q) == 6:
                    # Likely A-share code
                    cn_results = _search_cn_stocks(q)
                    seen = {r["symbol"] for r in results}
                    for r in cn_results:
                        if r["symbol"] not in seen:
                            results.append(r)
                elif len(q) == 5:
                    # Likely HK code
                    hk_results = _search_hk_stocks(q)
                    seen = {r["symbol"] for r in results}
                    for r in hk_results:
                        if r["symbol"] not in seen:
                            results.append(r)
            else:
                # Search US stocks via Polygon
                remote = search_tickers(q, limit=10)
                seen = {r["symbol"] for r in results}
                for r in remote:
                    if r["symbol"] not in seen:
                        results.append(r)
        except Exception:
            logger.debug("Remote search failed for query=%s", q)

    return results


@router.get("/{symbol}/ohlc")
def get_ohlc(
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Get OHLC data for a symbol."""
    conn = get_conn()

    query = "SELECT * FROM ohlc WHERE symbol = ?"
    params: list = [symbol.upper()]

    if start:
        query += " AND date >= ?"
        params.append(start)
    if end:
        query += " AND date <= ?"
        params.append(end)

    query += " ORDER BY date ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No OHLC data for {symbol}")

    return [dict(r) for r in rows]


@router.post("")
def add_ticker(req: AddTickerRequest, background_tasks: BackgroundTasks):
    """Add a new ticker and trigger background data fetch."""
    symbol = req.symbol.upper()
    market = get_market(symbol)

    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO tickers (symbol, name, market) VALUES (?, ?, ?)",
        (symbol, req.name or symbol, market),
    )
    conn.commit()
    conn.close()

    background_tasks.add_task(_fetch_ticker_data, symbol)
    return {"symbol": symbol, "market": market, "status": "added", "message": "Data fetch started in background"}


def _fetch_ticker_data(symbol: str):
    """Background task to fetch OHLC and news for a ticker."""
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=2 * 366)).isoformat()
    end = today.isoformat()

    try:
        # Fetch OHLC
        ohlc_rows = fetch_ohlc(symbol, start, end)
        conn = get_conn()
        for row in ohlc_rows:
            conn.execute(
                """INSERT OR IGNORE INTO ohlc
                   (symbol, date, open, high, low, close, volume, vwap, transactions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    symbol,
                    row["date"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"],
                    row["vwap"],
                    row["transactions"],
                ),
            )
        conn.execute(
            "UPDATE tickers SET last_ohlc_fetch = ? WHERE symbol = ?",
            (end, symbol),
        )
        conn.commit()

        # Fetch news
        import json

        articles = fetch_news(symbol, start, end)
        for art in articles:
            news_id = art.get("id")
            if not news_id:
                continue
            tickers = art.get("tickers") or []
            conn.execute(
                """INSERT OR IGNORE INTO news_raw
                   (id, title, description, publisher, author,
                    published_utc, article_url, amp_url, tickers_json, insights_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    news_id,
                    art.get("title"),
                    art.get("description"),
                    art.get("publisher"),
                    art.get("author"),
                    art.get("published_utc"),
                    art.get("article_url"),
                    art.get("amp_url"),
                    json.dumps(tickers),
                    json.dumps(art.get("insights")) if art.get("insights") else None,
                ),
            )
            for tk in tickers:
                conn.execute(
                    "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                    (news_id, tk),
                )

        conn.execute(
            "UPDATE tickers SET last_news_fetch = ? WHERE symbol = ?",
            (end, symbol),
        )
        conn.commit()
        conn.close()

        # Run alignment and layer 0 for the new data
        try:
            align_news_for_symbol(symbol)
            run_layer0(symbol)
        except Exception as e:
            logger.warning("Alignment/Layer0 error for %s: %s", symbol, e)

    except Exception:
        logger.exception("Error fetching data for %s", symbol)
