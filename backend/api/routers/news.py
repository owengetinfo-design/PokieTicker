from fastapi import APIRouter, Query
from typing import Optional

from backend.database import get_conn

router = APIRouter()


@router.get("/{symbol}")
def get_news_for_date(
    symbol: str,
    date: Optional[str] = None,
):
    """Get news for a symbol, optionally filtered to a specific trading day."""
    conn = get_conn()
    symbol = symbol.upper()

    if date:
        rows = conn.execute(
            """SELECT na.news_id, na.trade_date, na.published_utc,
                      na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5, na.ret_t10,
                      nr.title, nr.description, nr.publisher, nr.article_url, nr.image_url,
                      l1.relevance, l1.key_discussion, l1.chinese_summary,
                      l1.sentiment, l1.reason_growth, l1.reason_decrease
               FROM news_aligned na
               JOIN news_raw nr ON na.news_id = nr.id
               LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ?
               WHERE na.symbol = ? AND na.trade_date = ?
               ORDER BY na.published_utc DESC""",
            (symbol, symbol, date),
        ).fetchall()
    else:
        # Return recent news (last 30 days of aligned news)
        rows = conn.execute(
            """SELECT na.news_id, na.trade_date, na.published_utc,
                      na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5, na.ret_t10,
                      nr.title, nr.description, nr.publisher, nr.article_url, nr.image_url,
                      l1.relevance, l1.key_discussion, l1.chinese_summary,
                      l1.sentiment, l1.reason_growth, l1.reason_decrease
               FROM news_aligned na
               JOIN news_raw nr ON na.news_id = nr.id
               LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ?
               WHERE na.symbol = ?
               ORDER BY na.published_utc DESC
               LIMIT 100""",
            (symbol, symbol),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


@router.get("/{symbol}/range")
def get_news_for_range(
    symbol: str,
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    """Get news within a date range, with top bullish/bearish articles."""
    conn = get_conn()
    symbol = symbol.upper()

    rows = conn.execute(
        """SELECT na.news_id, na.trade_date, na.published_utc,
                  na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5, na.ret_t10,
                  nr.title, nr.description, nr.publisher, nr.article_url, nr.image_url,
                  l1.relevance, l1.key_discussion, l1.chinese_summary,
                  l1.sentiment, l1.reason_growth, l1.reason_decrease
           FROM news_aligned na
           JOIN news_raw nr ON na.news_id = nr.id
           LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ?
           WHERE na.symbol = ? AND na.trade_date BETWEEN ? AND ?
           ORDER BY na.published_utc DESC""",
        (symbol, symbol, start, end),
    ).fetchall()
    conn.close()

    articles = [dict(r) for r in rows]

    # Build top bullish / bearish lists
    top_bullish = sorted(
        [a for a in articles if a.get("sentiment") == "positive" and a.get("ret_t0") is not None],
        key=lambda a: a["ret_t0"],
        reverse=True,
    )[:5]

    top_bearish = sorted(
        [a for a in articles if a.get("sentiment") == "negative" and a.get("ret_t0") is not None],
        key=lambda a: a["ret_t0"],
    )[:5]

    return {
        "total": len(articles),
        "date_range": [start, end],
        "articles": articles,
        "top_bullish": top_bullish,
        "top_bearish": top_bearish,
    }


@router.get("/{symbol}/particles")
def get_news_particles(symbol: str):
    """Return lightweight per-article data for chart particle visualization."""
    conn = get_conn()
    symbol = symbol.upper()
    rows = conn.execute(
        """SELECT na.news_id, na.trade_date, na.ret_t1,
                  nr.title,
                  l1.sentiment, l1.relevance
           FROM news_aligned na
           JOIN news_raw nr ON na.news_id = nr.id
           LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ?
           WHERE na.symbol = ?
           ORDER BY na.trade_date ASC, l1.relevance DESC""",
        (symbol, symbol),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["news_id"],
            "d": r["trade_date"],
            "s": r["sentiment"],
            "r": r["relevance"],
            "t": (r["title"] or "")[:80],
            "rt1": r["ret_t1"],
        }
        for r in rows
    ]


@router.get("/{symbol}/categories")
def get_news_categories(symbol: str):
    """Categorize ALL news for a symbol by topic using keyword matching."""
    conn = get_conn()
    symbol = symbol.upper()

    rows = conn.execute(
        """SELECT na.news_id,
                  nr.title,
                  l1.key_discussion,
                  l1.reason_growth,
                  l1.reason_decrease,
                  l1.sentiment
           FROM news_aligned na
           JOIN news_raw nr ON na.news_id = nr.id
           LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ?
           WHERE na.symbol = ?
           ORDER BY na.trade_date DESC""",
        (symbol, symbol),
    ).fetchall()
    conn.close()

    CATEGORY_KEYWORDS = {
        "market": {
            "en": ["market", "stock", "rally", "sell-off", "selloff", "trading",
                   "wall street", "s&p", "nasdaq", "dow", "index", "bull", "bear",
                   "correction", "volatility"],
            "zh": ["市场", "股市", "大盘", "牛市", "熊市", "反弹", "下跌", "上涨",
                   "震荡", "成交量", "行情", "股指"],
        },
        "policy": {
            "en": ["regulation", "fed", "federal reserve", "tariff", "sanction",
                   "interest rate", "policy", "government", "congress", "sec",
                   "trade war", "ban", "legislation", "tax"],
            "zh": ["政策", "监管", "央行", "降准", "加息", "证监会", "银保监会",
                   "美联储", "关税", "制裁", "利率", "政府", "立法", "税收"],
        },
        "earnings": {
            "en": ["earnings", "revenue", "profit", "quarter", "eps", "guidance",
                   "forecast", "income", "sales", "beat", "miss", "outlook",
                   "financial results"],
            "zh": ["财报", "业绩", "营收", "利润", "净利润", "同比增长", "季度",
                   "年报", "中报", "一季报", "三季报", "预期", "盈利", "亏损"],
        },
        "product_tech": {
            "en": ["product", "ai", "chip", "cloud", "launch", "patent",
                   "technology", "innovation", "release", "platform", "model",
                   "software", "hardware", "gpu", "autonomous"],
            "zh": ["产品", "人工智能", "芯片", "云", "发布", "专利", "技术", "创新",
                   "平台", "模型", "软件", "硬件", "显卡", "自动驾驶", "研发"],
        },
        "competition": {
            "en": ["competitor", "rival", "market share", "overtake", "compete",
                   "competition", "vs", "versus", "battle", "challenge"],
            "zh": ["竞争", "竞争对手", "市场份额", "超越", "竞争", "对战", "挑战"],
        },
        "management": {
            "en": ["ceo", "executive", "resign", "layoff", "restructure",
                   "management", "leadership", "appoint", "hire", "board",
                   "chairman"],
            "zh": ["首席执行官", "高管", "辞职", "裁员", "重组", "管理层",
                   "领导", "任命", "招聘", "董事会", "董事长", "总经理"],
        },
    }

    # Flatten keywords for matching (combine en + zh)
    FLAT_KEYWORDS = {
        cat: data["en"] + data["zh"]
        for cat, data in CATEGORY_KEYWORDS.items()
    }

    categories = {}
    for cat, keywords in FLAT_KEYWORDS.items():
        categories[cat] = {
            "label": cat,
            "count": 0,
            "article_ids": [],
            "positive_ids": [],
            "negative_ids": [],
            "neutral_ids": [],
        }

    total = len(rows)
    for r in rows:
        text = " ".join([
            (r["title"] or ""),
            (r["key_discussion"] or ""),
            (r["reason_growth"] or ""),
            (r["reason_decrease"] or ""),
        ]).lower()
        sentiment = r["sentiment"]  # positive / negative / neutral / None
        for cat, keywords in FLAT_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                categories[cat]["count"] += 1
                categories[cat]["article_ids"].append(r["news_id"])
                if sentiment == "positive":
                    categories[cat]["positive_ids"].append(r["news_id"])
                elif sentiment == "negative":
                    categories[cat]["negative_ids"].append(r["news_id"])
                else:
                    categories[cat]["neutral_ids"].append(r["news_id"])

    return {"categories": categories, "total": total}


@router.get("/{symbol}/timeline")
def get_news_timeline(symbol: str):
    """Get dates that have news for a symbol (used for chart markers)."""
    conn = get_conn()
    symbol = symbol.upper()

    rows = conn.execute(
        """SELECT trade_date, COUNT(*) as news_count,
                  SUM(CASE WHEN l1.relevance = 'relevant' THEN 1 ELSE 0 END) as relevant_count
           FROM news_aligned na
           LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = na.symbol
           WHERE na.symbol = ?
           GROUP BY trade_date
           ORDER BY trade_date ASC""",
        (symbol,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
