# Re-export from data_sources for backward compatibility
from backend.data_sources.polygon_client import (
    fetch_ohlc,
    fetch_news,
    search_tickers,
    http_get,
    BASE,
    PolygonClient,
)

__all__ = [
    "fetch_ohlc",
    "fetch_news",
    "search_tickers",
    "http_get",
    "BASE",
    "PolygonClient",
]
