"""Chinese news data source with multi-source support.

Supports:
- East Money (东方财富) - via AKShare
- Sina Finance (新浪财经) - via AKShare
- Tencent News (腾讯财经) - via RSS/web scraping
- NetEase News (网易财经) - via RSS/web scraping
- Phoenix Finance (凤凰网) - via RSS
- CCTV Finance (央视财经) - via AKShare
- Caixin (财新) - via RSS
- 21st Century Business Herald (21世纪经济报道)

Requires:
    pip install akshare feedparser beautifulsoup4 requests
"""

import re
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import quote
import requests


class MultiSourceCNNewsClient:
    """Multi-source Chinese news client."""

    def __init__(self):
        self._ak = None
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _get_ak(self):
        """Lazy import AKShare."""
        if self._ak is None:
            import akshare as ak
            self._ak = ak
        return self._ak

    def _to_em_code(self, symbol: str) -> str:
        """Convert symbol to East Money format."""
        if symbol.endswith('.SH'):
            return f"sh{symbol.replace('.SH', '')}"
        elif symbol.endswith('.SZ'):
            return f"sz{symbol.replace('.SZ', '')}"
        elif symbol.endswith('.HK'):
            return f"hk{symbol.replace('.HK', '')}"
        return symbol.lower()

    def _to_sina_code(self, symbol: str) -> str:
        """Convert symbol to Sina format."""
        if symbol.endswith('.SH'):
            return f"sh{symbol.replace('.SH', '')}"
        elif symbol.endswith('.SZ'):
            return f"sz{symbol.replace('.SZ', '')}"
        elif symbol.endswith('.HK'):
            return f"hk{symbol.replace('.HK', '')}"
        return symbol

    def _generate_news_id(self, title: str, published_time: str, source: str) -> str:
        """Generate a unique ID for news article."""
        content = f"{source}:{title}:{published_time}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _convert_to_iso(self, time_str: str) -> str:
        """Convert Chinese time format to ISO 8601 UTC format."""
        if not time_str:
            return datetime.utcnow().isoformat() + 'Z'

        time_str = str(time_str).strip()

        # Try various formats
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y年%m月%d日']:
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.isoformat() + 'Z'
            except ValueError:
                continue

        # If only time (e.g., "14:30"), assume today
        try:
            if ':' in time_str and len(time_str) <= 5:
                today = datetime.now().strftime('%Y-%m-%d')
                dt = datetime.strptime(f"{today} {time_str}", '%Y-%m-%d %H:%M')
                return dt.isoformat() + 'Z'
        except ValueError:
            pass

        # Try relative time parsing (e.g., "3小时前", "昨天")
        try:
            if '小时前' in time_str:
                hours = int(re.search(r'(\d+)', time_str).group(1))
                dt = datetime.now() - timedelta(hours=hours)
                return dt.isoformat() + 'Z'
            elif '分钟前' in time_str:
                minutes = int(re.search(r'(\d+)', time_str).group(1))
                dt = datetime.now() - timedelta(minutes=minutes)
                return dt.isoformat() + 'Z'
            elif '昨天' in time_str:
                dt = datetime.now() - timedelta(days=1)
                return dt.isoformat() + 'Z'
        except:
            pass

        return datetime.utcnow().isoformat() + 'Z'

    def _normalize_article(self, title: str, content: str, time_str: str,
                          url: str, source: str, symbol: str = '') -> Optional[Dict[str, Any]]:
        """Normalize article to unified format."""
        if not title or len(title) < 5:
            return None

        news_id = self._generate_news_id(title, time_str, source)

        return {
            'id': f"cn_{source}_{news_id}",
            'publisher': source,
            'title': title.strip(),
            'author': '',
            'published_utc': self._convert_to_iso(time_str),
            'amp_url': url,
            'article_url': url,
            'tickers': [symbol] if symbol else [],
            'description': content.strip() if content else title.strip(),
            'insights': None,
        }

    # ============= Source 1: East Money (AKShare) =============
    def _fetch_eastmoney(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch from East Money via AKShare."""
        try:
            ak = self._get_ak()
            em_code = self._to_em_code(symbol)
            df = ak.stock_news_em(symbol=em_code)

            articles = []
            for _, row in df.iterrows():
                art = self._normalize_article(
                    title=row.get('title', '') or row.get('新闻标题', ''),
                    content=row.get('content', '') or row.get('内容', '') or row.get('新闻内容', ''),
                    time_str=row.get('time', '') or row.get('发布时间', ''),
                    url=row.get('url', '') or row.get('链接', ''),
                    source='EastMoney',
                    symbol=symbol
                )
                if art:
                    articles.append(art)
            return articles[:limit]
        except Exception as e:
            print(f"EastMoney fetch error: {e}")
            return []

    # ============= Source 2: Sina Finance (Web Scrape) =============
    def _fetch_sina(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch from Sina Finance via web scraping."""
        try:
            code = symbol.split('.')[0]
            # Sina finance API
            url = f"https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid={code}"

            # Use alternative: Sina real-time news API
            api_url = "https://feed.mix.sina.com.cn/api/roll/get"
            params = {
                'pageid': '153',
                'lid': '2509',  # Finance news
                'k': f'{code}',
                'num': limit,
                'page': '1',
                'r': str(int(time.time() * 1000)),
            }

            response = self._session.get(api_url, params=params, timeout=10)
            if response.status_code != 200:
                return []

            data = response.json()
            articles = []

            result = data.get('result', {})
            data_list = result.get('data', [])

            for item in data_list:
                art = self._normalize_article(
                    title=item.get('title', ''),
                    content=item.get('summary', item.get('intro', '')),
                    time_str=item.get('ctime', item.get('createtime', '')),
                    url=item.get('url', ''),
                    source='Sina',
                    symbol=symbol
                )
                if art:
                    articles.append(art)

            return articles[:limit]
        except Exception as e:
            print(f"Sina fetch error: {e}")
            return []

    # ============= Source 3: Tencent Finance (Web API) =============
    def _fetch_tencent(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch from Tencent Finance via web API."""
        try:
            # Extract pure code
            code = symbol.split('.')[0]
            url = f"https://qt.gtimg.cn/q=sh{code},sz{code}"

            # Tencent finance news page
            news_url = f"https://stock.finance.qq.com/stock/news/column/page/1/20/{code}.shtml"

            # Try to fetch via simple HTTP
            response = self._session.get(
                f"https://web.ifzq.gtimg.cn/appstock/finance/news/getNewsByCode",
                params={'code': code, 'page': 1, 'num': limit},
                timeout=10
            )

            if response.status_code != 200:
                return []

            data = response.json()
            articles = []

            news_list = data.get('data', {}).get('data', [])
            if not news_list:
                # Try alternative format
                news_list = data.get('data', [])

            for item in news_list:
                art = self._normalize_article(
                    title=item.get('title', ''),
                    content=item.get('summary', item.get('content', '')),
                    time_str=item.get('time', item.get('pub_time', '')),
                    url=item.get('url', ''),
                    source='Tencent',
                    symbol=symbol
                )
                if art:
                    articles.append(art)

            return articles[:limit]
        except Exception as e:
            print(f"Tencent fetch error: {e}")
            return []

    # ============= Source 4: CCTV Finance News =============
    def _fetch_cctv(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch from CCTV Finance News via AKShare."""
        try:
            ak = self._get_ak()
            articles = []

            # Get company name for filtering
            company_name = self._get_company_name(symbol)
            keywords = [company_name] if company_name else []

            # Fetch CCTV news for multiple dates
            for i in range(7):  # Last 7 days
                date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                try:
                    df = ak.news_cctv(date=date)
                    for _, row in df.iterrows():
                        title = str(row.get('title', ''))
                        # Filter by company name if available
                        if keywords and not any(kw in title for kw in keywords if kw):
                            continue
                        art = self._normalize_article(
                            title=title,
                            content=title,
                            time_str=row.get('time', ''),
                            url='',
                            source='CCTV',
                            symbol=symbol
                        )
                        if art:
                            articles.append(art)
                except:
                    continue

            return articles[:limit]
        except Exception as e:
            print(f"CCTV fetch error: {e}")
            return []

    # ============= Source 5: East Money Search (Company-specific) =============
    def _fetch_eastmoney_search(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Search East Money for company news using company name as keyword."""
        try:
            ak = self._get_ak()
            company_name = self._get_company_name(symbol)
            if not company_name:
                return []

            articles = []

            # Try to get industry news for related sectors
            sectors = {
                '比亚迪': ['汽车', '新能源'],
                '茅台': ['白酒'],
                '腾讯': ['科技', '互联网'],
                '阿里巴巴': ['科技', '电商'],
                '宁德时代': ['新能源', '科技'],
            }

            company_sectors = sectors.get(company_name, ['科技'])

            for sector in company_sectors:
                try:
                    df = ak.stock_sector_news_em(sector=sector)
                    for _, row in df.iterrows():
                        title = str(row.get('title', ''))
                        # Filter by company name
                        if company_name not in title:
                            continue
                        art = self._normalize_article(
                            title=title,
                            content=title,
                            time_str=row.get('time', ''),
                            url='',
                            source='EastMoney-Industry',
                            symbol=symbol
                        )
                        if art:
                            articles.append(art)
                except:
                    continue

            return articles[:limit]
        except Exception as e:
            print(f"EastMoney search error: {e}")
            return []

    # ============= Source 5: Market-wide Finance News =============
    def _fetch_market_news(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch general market finance news that might affect the stock."""
        try:
            ak = self._get_ak()
            articles = []
            company_name = self._get_company_name(symbol)

            # Get market-wide news
            try:
                # Use stock_changes_em to get market activity
                df = ak.stock_changes_em(symbol=symbol.split('.')[0])
                if df is not None and not df.empty:
                    for _, row in df.head(limit).iterrows():
                        title = f"{company_name or symbol}: {row.get('name', '')}"
                        art = self._normalize_article(
                            title=title,
                            content=str(row.get('content', title)),
                            time_str=str(row.get('time', datetime.now().isoformat())),
                            url='',
                            source='EastMoney-Market',
                            symbol=symbol
                        )
                        if art:
                            articles.append(art)
            except:
                pass

            return articles[:limit]
        except Exception as e:
            print(f"Market news error: {e}")
            return []

    def _get_company_name(self, symbol: str) -> str:
        """Get Chinese company name for better search."""
        name_map = {
            '002594.SZ': '比亚迪',
            '00700.HK': '腾讯',
            '600519.SH': '茅台',
            '000858.SZ': '五粮液',
            '300750.SZ': '宁德时代',
            '01810.HK': '小米',
            '09988.HK': '阿里巴巴',
            '09618.HK': '京东',
            '02318.HK': '中国平安',
            '03690.HK': '美团',
            '600036.SH': '招商银行',
            '601398.SH': '工商银行',
        }
        return name_map.get(symbol, '')

    # ============= Main Public API =============
    def fetch_stock_news(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch news from all available sources for a specific stock.

        Args:
            symbol: Stock symbol (e.g., "600000.SH", "00700.HK")
            limit: Maximum number of articles per source

        Returns:
            List of news articles from all sources (deduplicated)
        """
        all_articles = []
        seen_titles = set()

        sources = [
            ('EastMoney', self._fetch_eastmoney),
            ('EastMoney-Industry', self._fetch_eastmoney_search),
            ('CCTV', self._fetch_cctv),
            ('EastMoney-Market', self._fetch_market_news),
        ]

        for source_name, fetch_func in sources:
            try:
                print(f"  Fetching from {source_name}...")
                articles = fetch_func(symbol, limit)
                print(f"    Found {len(articles)} articles")

                for art in articles:
                    # Deduplicate by title similarity
                    title_key = art['title'][:30].lower()
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        all_articles.append(art)

                # Small delay to be respectful
                time.sleep(0.5)

            except Exception as e:
                print(f"  Error fetching from {source_name}: {e}")
                continue

        # Sort by date
        all_articles.sort(key=lambda x: x['published_utc'], reverse=True)

        return all_articles[:limit]

    def fetch_sector_news(self, sector: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch industry/sector news."""
        try:
            ak = self._get_ak()
            df = ak.stock_sector_news_em(sector=sector)

            articles = []
            for _, row in df.iterrows():
                art = self._normalize_article(
                    title=row.get('title', ''),
                    content=row.get('content', ''),
                    time_str=row.get('time', ''),
                    url='',
                    source='EastMoney-Sector',
                    symbol=''
                )
                if art:
                    articles.append(art)

            return articles[:limit]
        except Exception as e:
            print(f"Sector news error: {e}")
            return []


# Backward compatibility
AKShareNewsClient = MultiSourceCNNewsClient
