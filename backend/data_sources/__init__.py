"""Data sources coordinator for multi-market support.

Routes data requests to the appropriate source based on market type:
- US stocks: Polygon
- CN stocks (A-shares): Tushare
- HK stocks: Tushare
"""

from typing import List, Dict, Any, Optional

from backend.config import settings
from backend.data_sources.polygon_client import (
    fetch_ohlc as polygon_fetch_ohlc,
    fetch_news as polygon_fetch_news,
    search_tickers as polygon_search_tickers,
)

# Lazy imports for optional dependencies
_tushare_client = None
_cn_news_client = None


def _get_tushare_client():
    global _tushare_client
    if _tushare_client is None:
        from backend.data_sources.tushare_client import TushareClient
        _tushare_client = TushareClient()
    return _tushare_client


def _get_cn_news_client():
    global _cn_news_client
    if _cn_news_client is None:
        from backend.data_sources.cn_news_client import MultiSourceCNNewsClient
        _cn_news_client = MultiSourceCNNewsClient()
    return _cn_news_client


def get_market(symbol: str) -> str:
    """Determine market type from symbol format.

    Returns:
        'US' - US stocks (no suffix or standard US format)
        'CN' - A-shares (.SH or .SZ suffix)
        'HK' - Hong Kong stocks (.HK suffix)
    """
    if symbol.endswith('.SH') or symbol.endswith('.SZ'):
        return 'CN'
    elif symbol.endswith('.HK'):
        return 'HK'
    else:
        return 'US'


def fetch_ohlc(symbol: str, start: str, end: str) -> List[Dict[str, Any]]:
    """Fetch OHLC data for any market.

    Args:
        symbol: Stock symbol (e.g., 'AAPL', '600000.SH', '00700.HK')
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)

    Returns:
        List of OHLC data dictionaries in unified format
    """
    market = get_market(symbol)

    if market == 'US':
        return polygon_fetch_ohlc(symbol, start, end)
    elif market in ('CN', 'HK'):
        client = _get_tushare_client()
        if market == 'CN':
            return client.fetch_ohlc_cn(symbol, start, end)
        else:
            return client.fetch_ohlc_hk(symbol, start, end)
    else:
        raise ValueError(f"Unknown market: {market}")


def fetch_news(symbol: str, start: str, end: str) -> List[Dict[str, Any]]:
    """Fetch news for any market.

    Args:
        symbol: Stock symbol
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)

    Returns:
        List of news articles in unified format
    """
    market = get_market(symbol)

    if market == 'US':
        return polygon_fetch_news(symbol, start, end)
    elif market in ('CN', 'HK'):
        client = _get_cn_news_client()
        return client.fetch_stock_news(symbol)
    else:
        raise ValueError(f"Unknown market: {market}")


def search_tickers(query: str, limit: int = 20) -> List[Dict[str, str]]:
    """Search tickers across all markets.

    For numeric queries, attempts to match A-share (6-digit) or HK (5-digit) codes.
    For other queries, searches US stocks via Polygon.
    """
    results = []

    # Try numeric matching for CN/HK stocks
    if query.isdigit():
        if len(query) == 6:
            # Likely A-share code
            client = _get_tushare_client()
            cn_results = client.search_stock(query)
            results.extend(cn_results)
        elif len(query) == 5:
            # Likely HK code
            client = _get_tushare_client()
            hk_results = client.search_hk_stock(query)
            results.extend(hk_results)

    # Also search US stocks via Polygon
    try:
        us_results = polygon_search_tickers(query, limit)
        for r in us_results:
            r['market'] = 'US'
        results.extend(us_results)
    except Exception:
        pass

    return results[:limit]


class DataCoordinator:
    """Convenience class that provides a unified interface to all data sources.

    Example:
        coordinator = DataCoordinator()
        ohlc = coordinator.fetch_ohlc('600000.SH', '2024-01-01', '2024-12-31')
        news = coordinator.fetch_news('600000.SH', '2024-01-01', '2024-12-31')
    """

    def __init__(self):
        self._tushare = None
        self._cn_news = None

    @property
    def tushare(self):
        if self._tushare is None:
            from backend.data_sources.tushare_client import TushareClient
            self._tushare = TushareClient()
        return self._tushare

    @property
    def cn_news(self):
        if self._cn_news is None:
            from backend.data_sources.cn_news_client import AKShareNewsClient
            self._cn_news = AKShareNewsClient()
        return self._cn_news

    def fetch_ohlc(self, symbol: str, start: str, end: str) -> List[Dict[str, Any]]:
        return fetch_ohlc(symbol, start, end)

    def fetch_news(self, symbol: str, start: str, end: str) -> List[Dict[str, Any]]:
        return fetch_news(symbol, start, end)

    def search(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        return search_tickers(query, limit)
