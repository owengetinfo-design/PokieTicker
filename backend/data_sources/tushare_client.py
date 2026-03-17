"""Tushare client for A-share and Hong Kong stock data.

Requires:
    pip install tushare pandas

Get API key from: https://tushare.pro/
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

import pandas as pd

from backend.config import settings


class TushareClient:
    """Client for fetching Chinese stock data via Tushare API."""

    def __init__(self):
        self._pro = None
        self._api_key = settings.tushare_api_key

    def _get_pro(self):
        """Lazy initialization of Tushare API."""
        if self._pro is None:
            import tushare as ts
            if not self._api_key:
                raise ValueError(
                    "Tushare API key not configured. "
                    "Set TUSHARE_API_KEY in .env file"
                )
            self._pro = ts.pro_api(self._api_key)
        return self._pro

    def _format_date(self, date_str: str) -> str:
        """Convert YYYY-MM-DD to YYYYMMDD format required by Tushare."""
        return date_str.replace('-', '')

    def _normalize_ohlc(self, df, market: str) -> List[Dict[str, Any]]:
        """Convert Tushare DataFrame to unified format.

        Args:
            df: Tushare DataFrame
            market: 'CN' or 'HK'

        Returns:
            List of OHLC dictionaries in unified format
        """
        rows = []
        for _, row in df.iterrows():
            # Tushare uses different column names for CN vs HK
            if market == 'CN':
                date_col = 'trade_date'
                vol_col = 'vol'
            else:
                date_col = 'trade_date'
                vol_col = 'vol'

            # Parse date from YYYYMMDD to YYYY-MM-DD
            trade_date = str(row[date_col])
            if len(trade_date) == 8:
                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
            else:
                formatted_date = trade_date

            rows.append({
                "date": formatted_date,
                "open": float(row['open']) if pd.notna(row['open']) else None,
                "high": float(row['high']) if pd.notna(row['high']) else None,
                "low": float(row['low']) if pd.notna(row['low']) else None,
                "close": float(row['close']) if pd.notna(row['close']) else None,
                "volume": float(row[vol_col]) if pd.notna(row[vol_col]) else None,
                "vwap": None,  # Tushare doesn't provide VWAP
                "transactions": None,  # Tushare doesn't provide transaction count
                "market": market,
            })
        return rows

    def fetch_ohlc_cn(self, ts_code: str, start: str, end: str) -> List[Dict[str, Any]]:
        """Fetch A-share daily OHLC data.

        Args:
            ts_code: Tushare code (e.g., "600000.SH", "000001.SZ")
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)

        Returns:
            List of OHLC data dictionaries
        """
        import pandas as pd

        pro = self._get_pro()
        df = pro.daily(
            ts_code=ts_code,
            start_date=self._format_date(start),
            end_date=self._format_date(end)
        )

        if df is None or df.empty:
            return []

        return self._normalize_ohlc(df, market='CN')

    def fetch_ohlc_hk(self, ts_code: str, start: str, end: str) -> List[Dict[str, Any]]:
        """Fetch Hong Kong stock daily OHLC data.

        Args:
            ts_code: Tushare code (e.g., "00700.HK")
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)

        Returns:
            List of OHLC data dictionaries
        """
        import pandas as pd

        pro = self._get_pro()
        df = pro.hk_daily(
            ts_code=ts_code,
            start_date=self._format_date(start),
            end_date=self._format_date(end)
        )

        if df is None or df.empty:
            return []

        return self._normalize_ohlc(df, market='HK')

    def search_stock(self, query: str) -> List[Dict[str, str]]:
        """Search A-share stocks by code or name.

        Args:
            query: Stock code (e.g., "600000") or name (e.g., "浦发")

        Returns:
            List of matching stocks with symbol, name, sector, market
        """
        pro = self._get_pro()

        # Try exact code match first
        try:
            df = pro.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name,area,industry,exchange'
            )
        except Exception as e:
            print(f"Tushare stock_basic error: {e}")
            return []

        if df is None or df.empty:
            return []

        # Filter by query
        mask = (
            df['symbol'].str.contains(query, case=False, na=False) |
            df['name'].str.contains(query, case=False, na=False) |
            df['ts_code'].str.contains(query, case=False, na=False)
        )
        matches = df[mask].head(10)

        results = []
        for _, row in matches.iterrows():
            exchange = row['exchange']
            suffix = '.SH' if exchange == 'SSE' else '.SZ'
            symbol = f"{row['symbol']}{suffix}"

            results.append({
                'symbol': symbol,
                'name': row['name'],
                'sector': row.get('industry', ''),
                'market': 'CN',
            })

        return results

    def search_hk_stock(self, query: str) -> List[Dict[str, str]]:
        """Search Hong Kong stocks by code.

        Args:
            query: Stock code (e.g., "00700")

        Returns:
            List of matching stocks
        """
        pro = self._get_pro()

        try:
            # HK stock basics
            df = pro.hk_basic(fields='ts_code,name,enname,list_date')
        except Exception as e:
            print(f"Tushare hk_basic error: {e}")
            return []

        if df is None or df.empty:
            return []

        # Filter by code
        mask = df['ts_code'].str.contains(query, case=False, na=False)
        matches = df[mask].head(10)

        results = []
        for _, row in matches.iterrows():
            results.append({
                'symbol': row['ts_code'],
                'name': row['name'],
                'sector': '',
                'market': 'HK',
            })

        return results

    def get_stock_basic_cn(self, symbol: str) -> Optional[Dict[str, str]]:
        """Get basic info for an A-share stock.

        Args:
            symbol: Symbol with suffix (e.g., "600000.SH")

        Returns:
            Dictionary with stock info or None
        """
        pro = self._get_pro()

        # Convert to Tushare format
        code = symbol.replace('.SH', '').replace('.SZ', '')

        try:
            df = pro.stock_basic(
                ts_code=f"{code}.SH" if symbol.endswith('.SH') else f"{code}.SZ",
                fields='ts_code,symbol,name,area,industry,exchange'
            )
        except Exception as e:
            print(f"Error fetching stock basic info: {e}")
            return None

        if df is None or df.empty:
            return None

        row = df.iloc[0]
        return {
            'symbol': symbol,
            'name': row['name'],
            'sector': row.get('industry', ''),
            'market': 'CN',
        }

    def get_stock_basic_hk(self, symbol: str) -> Optional[Dict[str, str]]:
        """Get basic info for a HK stock.

        Args:
            symbol: Symbol with suffix (e.g., "00700.HK")

        Returns:
            Dictionary with stock info or None
        """
        pro = self._get_pro()

        try:
            df = pro.hk_basic(ts_code=symbol, fields='ts_code,name,enname')
        except Exception as e:
            print(f"Error fetching HK stock basic info: {e}")
            return None

        if df is None or df.empty:
            return None

        row = df.iloc[0]
        return {
            'symbol': symbol,
            'name': row['name'],
            'sector': '',
            'market': 'HK',
        }
