"""Dynamic news search API - real-time news without saving to database.

Uses AKShare to fetch:
1. Individual stock news
2. Sector/Industry news
3. Related company news
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta

from backend.database import get_conn
from backend.data_sources import get_market

router = APIRouter()


def _get_stock_info(symbol: str) -> Optional[Dict[str, str]]:
    """Get stock name and sector from database."""
    conn = get_conn()
    row = conn.execute(
        "SELECT symbol, name, sector, market FROM tickers WHERE symbol = ?",
        (symbol.upper(),)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def _to_em_code(symbol: str) -> str:
    """Convert symbol to East Money format."""
    if symbol.endswith('.SH'):
        return f"sh{symbol.replace('.SH', '')}"
    elif symbol.endswith('.SZ'):
        return f"sz{symbol.replace('.SZ', '')}"
    elif symbol.endswith('.HK'):
        return f"hk{symbol.replace('.HK', '')}"
    return symbol.lower()


def _fetch_cn_stock_news(symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch real-time news for a Chinese stock using AKShare."""
    try:
        import akshare as ak

        em_code = _to_em_code(symbol)
        articles = []

        # 1. Individual stock news from East Money
        try:
            df = ak.stock_news_em(symbol=em_code)
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    title = row.get('title', '') or row.get('新闻标题', '')
                    content = row.get('content', '') or row.get('内容', '') or row.get('新闻内容', '')
                    time_str = row.get('time', '') or row.get('发布时间', '')
                    url = row.get('url', '') or row.get('链接', '')

                    if title:
                        articles.append({
                            'id': f"em_{hash(title + time_str) % 100000000}",
                            'source': '东方财富',
                            'title': title,
                            'content': content or title,
                            'published_at': _format_time(time_str),
                            'url': url,
                            'type': '个股新闻',
                            'symbol': symbol,
                        })
        except Exception as e:
            print(f"EastMoney stock news error: {e}")

        # 2. Sina Finance as backup
        try:
            sina_code = _to_sina_code(symbol)
            df = ak.stock_news_sina(symbol=sina_code)
            if df is not None and not df.empty:
                for _, row in df.head(limit//2).iterrows():
                    title = row.get('title', '') or row.get('标题', '')
                    time_str = row.get('time', '') or row.get('时间', '')
                    url = row.get('url', '') or row.get('链接', '')

                    if title and not any(a['title'] == title for a in articles):
                        articles.append({
                            'id': f"sina_{hash(title + time_str) % 100000000}",
                            'source': '新浪财经',
                            'title': title,
                            'content': title,
                            'published_at': _format_time(time_str),
                            'url': url,
                            'type': '个股新闻',
                            'symbol': symbol,
                        })
        except Exception as e:
            print(f"Sina news error: {e}")

        return articles

    except ImportError:
        raise HTTPException(status_code=500, detail="AKShare not installed")


def _fetch_sector_news(sector: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch real-time sector/industry news."""
    try:
        import akshare as ak

        articles = []

        # Map sector names to AKShare industry names
        sector_mapping = {
            '白酒': '白酒',
            '银行': '银行',
            '新能源': '新能源',
            '科技': '科技',
            '医药': '医药',
            '汽车': '汽车',
            '半导体': '半导体',
            '互联网': '互联网',
            '金融': '金融',
            '消费': '消费',
        }

        # Try to match sector
        matched_sector = None
        for key in sector_mapping:
            if key in sector:
                matched_sector = sector_mapping[key]
                break

        if matched_sector:
            try:
                df = ak.stock_sector_news_em(sector=matched_sector)
                if df is not None and not df.empty:
                    for _, row in df.head(limit).iterrows():
                        title = row.get('title', '') or row.get('标题', '')
                        time_str = row.get('time', '') or row.get('时间', '')

                        if title:
                            articles.append({
                                'id': f"sector_{hash(title + time_str) % 100000000}",
                                'source': '行业资讯',
                                'title': title,
                                'content': title,
                                'published_at': _format_time(time_str),
                                'url': '',
                                'type': f'{matched_sector}行业',
                                'symbol': None,
                            })
            except Exception as e:
                print(f"Sector news error: {e}")

        # Also fetch general macro news
        try:
            df = ak.news_cctv(date=datetime.now().strftime('%Y%m%d'))
            if df is not None and not df.empty:
                for _, row in df.head(5).iterrows():
                    title = row.get('title', '') or row.get('标题', '')
                    time_str = row.get('time', '') or row.get('时间', '')

                    if title:
                        articles.append({
                            'id': f"cctv_{hash(title + time_str) % 100000000}",
                            'source': '央视财经',
                            'title': title,
                            'content': title,
                            'published_at': _format_time(time_str),
                            'url': '',
                            'type': '宏观财经',
                            'symbol': None,
                        })
        except Exception as e:
            print(f"CCTV news error: {e}")

        return articles

    except ImportError:
        return []


def _to_sina_code(symbol: str) -> str:
    """Convert symbol to Sina format."""
    if symbol.endswith('.SH'):
        return f"sh{symbol.replace('.SH', '')}"
    elif symbol.endswith('.SZ'):
        return f"sz{symbol.replace('.SZ', '')}"
    elif symbol.endswith('.HK'):
        return f"hk{symbol.replace('.HK', '')}"
    return symbol


def _format_time(time_str: str) -> str:
    """Format time string to ISO format."""
    if not time_str:
        return datetime.now().isoformat()

    time_str = str(time_str).strip()

    # Try various formats
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%H:%M']:
        try:
            dt = datetime.strptime(time_str, fmt)
            if fmt == '%H:%M':
                # Assume today
                today = datetime.now()
                dt = dt.replace(year=today.year, month=today.month, day=today.day)
            return dt.isoformat()
        except ValueError:
            continue

    return datetime.now().isoformat()


@router.get("/{symbol}/dynamic")
def get_dynamic_news(
    symbol: str,
    include_sector: bool = Query(True, description="Include sector news"),
    limit: int = Query(30, ge=5, le=50)
):
    """Get dynamic real-time news for a stock (not saved to database).

    Returns:
        - Stock Chinese name and info
        - Individual stock news
        - Sector/Industry news (if include_sector=True)
    """
    symbol = symbol.upper()
    market = get_market(symbol)

    # Get stock info
    stock_info = _get_stock_info(symbol)
    if not stock_info:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    articles = []

    # Fetch news based on market
    if market in ('CN', 'HK'):
        # Individual stock news
        stock_news = _fetch_cn_stock_news(symbol, limit=limit//2)
        articles.extend(stock_news)

        # Sector news
        if include_sector and stock_info.get('sector'):
            sector_news = _fetch_sector_news(stock_info['sector'], limit=limit//3)
            articles.extend(sector_news)

    else:
        # US stocks - fetch from Polygon (existing method)
        from backend.data_sources.polygon_client import fetch_news
        from datetime import timedelta

        end = datetime.now().date().isoformat()
        start = (datetime.now() - timedelta(days=30)).date().isoformat()

        try:
            us_news = fetch_news(symbol, start, end)
            for art in us_news[:limit]:
                articles.append({
                    'id': art.get('id', ''),
                    'source': art.get('publisher', 'Polygon'),
                    'title': art.get('title', ''),
                    'content': art.get('description', ''),
                    'published_at': art.get('published_utc', ''),
                    'url': art.get('article_url', ''),
                    'type': '个股新闻',
                    'symbol': symbol,
                })
        except Exception as e:
            print(f"US stock news error: {e}")

    # Sort by time (newest first)
    articles.sort(key=lambda x: x.get('published_at', ''), reverse=True)

    return {
        'symbol': symbol,
        'name': stock_info.get('name', symbol),
        'sector': stock_info.get('sector', ''),
        'market': market,
        'total': len(articles),
        'articles': articles[:limit],
    }


@router.get("/search")
def search_live_news(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(20, ge=5, le=50)
):
    """Search real-time news by keyword (not saved to database).

    Useful for searching industry or company news.
    """
    try:
        import akshare as ak

        articles = []

        # Try to search via East Money
        try:
            # Use the stock news interface as a proxy for keyword search
            # Search major indices for market news
            df = ak.stock_news_em(symbol='sh000001')  # Shanghai index news
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    title = row.get('title', '') or row.get('新闻标题', '')
                    content = row.get('content', '') or row.get('内容', '')
                    time_str = row.get('time', '') or row.get('发布时间', '')

                    if title and keyword.lower() in title.lower():
                        articles.append({
                            'id': f"search_{hash(title) % 100000000}",
                            'source': '东方财富',
                            'title': title,
                            'content': content or title,
                            'published_at': _format_time(time_str),
                            'url': '',
                            'type': '搜索结果',
                            'keyword': keyword,
                        })
        except Exception as e:
            print(f"Search news error: {e}")

        return {
            'keyword': keyword,
            'total': len(articles),
            'articles': articles[:limit],
        }

    except ImportError:
        raise HTTPException(status_code=500, detail="AKShare not installed")
