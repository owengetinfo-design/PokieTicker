"""Layer 1: AI Analysis — 50 articles packed into 1 API call.

Supports:
- Anthropic Claude (default)
- Moonshot Kimi (alternative for CN users)

Strategy:
1. Local keyword extraction: for long descriptions (>500 chars), extract only
   sentences mentioning the company (ticker, name, CEO, products, etc.)
2. Pack 50 articles into a single prompt → 1 API call
3. Get back a compact JSON array
"""

import json
import os
import re
from typing import List, Dict, Any

from backend.config import settings
from backend.database import get_conn

# AI Provider config
AI_PROVIDER = settings.ai_provider.lower()  # "anthropic" or "kimi"

# Anthropic config (also used for Kimi Code compatibility)
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"

# Kimi Code config (Anthropic-compatible API)
KIMI_CODE_MODEL = "kimi-k2"  # or "kimi-latest" for Coding Plan
KIMI_CODE_BASE_URL = "https://api.kimi.com/coding"

# Legacy Kimi config (OpenAI-compatible)
KIMI_MODEL = "moonshot-v1-32k"
KIMI_BASE_URL = "https://api.moonshot.cn/v1"

BATCH_SIZE = 50  # articles per API call
MAX_OUTPUT_TOKENS = 4096  # enough for 50 articles (~70 tokens each)

# Comprehensive keyword mappings for extraction
# ticker, company name, short name, CEO, key products, subsidiaries
TICKER_KEYWORDS: Dict[str, List[str]] = {
    # US Stocks
    "BABA": ["alibaba", "ali baba", "baba", "daniel zhang", "joe tsai",
             "taobao", "tmall", "alipay", "ant group", "alicloud",
             "aliyun", "cainiao", "lazada", "ele.me", "阿里巴巴", "淘宝", "天猫", "支付宝", "阿里云"],
    "AAPL": ["apple", "aapl", "tim cook", "iphone", "ipad", "macbook",
             "apple watch", "vision pro", "app store", "ios", "macos", "苹果"],
    "TSLA": ["tesla", "tsla", "elon musk", "model 3", "model y",
             "model s", "model x", "cybertruck", "gigafactory",
             "supercharger", "autopilot", "full self-driving", "fsd", "特斯拉", "马斯克"],
    "NVDA": ["nvidia", "nvda", "jensen huang", "geforce", "rtx",
             "cuda", "a100", "h100", "h200", "b100", "b200",
             "dgx", "drive", "omniverse", "tensorrt", "英伟达", "黄仁勋"],
    "GLD": ["spdr gold", "gld", "gold trust", "gold etf", "gold shares", "黄金"],
    "MSFT": ["microsoft", "msft", "satya nadella", "windows", "azure",
             "office 365", "xbox", "linkedin", "github", "copilot", "微软"],
    "GOOGL": ["google", "alphabet", "googl", "goog", "sundar pichai",
              "youtube", "waymo", "deepmind", "gemini", "android",
              "google cloud", "pixel", "谷歌"],
    "AMZN": ["amazon", "amzn", "andy jassy", "aws", "prime",
             "alexa", "kindle", "whole foods", "亚马逊"],
    "META": ["meta platforms", "meta", "facebook", "zuckerberg",
             "instagram", "whatsapp", "threads", "oculus", "quest", "脸书", "脸书", "扎克伯格"],
    "AMD":  ["amd", "advanced micro", "lisa su", "radeon", "ryzen",
             "epyc", "xilinx", "instinct"],

    # A-Shares (CN)
    "600519.SH": ["茅台", "贵州茅台", "maotai", "飞天茅台", "酱香", "白酒", "moutai"],
    "600000.SH": ["浦发银行", "浦发", "spdb", "银行"],
    "000858.SZ": ["五粮液", "wuliangye", "浓香", "白酒"],
    "002594.SZ": ["比亚迪", "byd", "王传福", "新能源汽车", "刀片电池"],
    "600036.SH": ["招商银行", "招行"],
    "601398.SH": ["工商银行", "工行"],
    "601288.SH": ["农业银行", "农行"],
    "688981.SH": ["中芯国际", "smic"],
    "688256.SH": ["寒武纪", "cambricon"],
    "603501.SH": ["韦尔股份", "willsemi"],
    "300750.SZ": ["宁德时代", "catl", "曾毓群", "电池"],
    "601012.SH": ["隆基绿能", "longi", "光伏"],
    "000568.SZ": ["泸州老窖", "luzhoulaojiao", "白酒"],
    "600809.SH": ["山西汾酒", "fenjiu", "白酒"],

    # Hong Kong (HK)
    "00700.HK": ["腾讯", "tencent", "马化腾", "微信", "wechat", "qq", "王者荣耀", "吃鸡"],
    "01810.HK": ["小米", "xiaomi", "雷军", "miui", "红米", "redmi"],
    "09988.HK": ["阿里巴巴", "alibaba", "马云", "张勇", "淘宝", "天猫", "阿里云", "1688"],
    "09618.HK": ["京东", "jd.com", "刘强东", "618"],
    "02318.HK": ["中国平安", "pingan", "保险"],
    "03988.HK": ["中国银行", "boc", "中银"],
    "03690.HK": ["美团", "meituan", "王兴", "外卖"],
    "01024.HK": ["快手", "kuaishou", "短视频"],
}

# Minimum description length to trigger extraction (shorter ones sent in full)
EXTRACT_THRESHOLD = 500


def _get_keywords(symbol: str) -> List[str]:
    """Get all keywords for a ticker. Falls back to just the symbol."""
    kws = [symbol.lower()]
    kws.extend(TICKER_KEYWORDS.get(symbol, []))
    return kws


def _extract_relevant_text(description: str, symbol: str) -> str:
    """For long descriptions, extract only sentences mentioning the company.

    Short descriptions (<500 chars) are returned in full.
    Long descriptions are filtered to company-relevant sentences + 1 neighbor.
    """
    if not description:
        return ""

    desc = description.strip()
    if len(desc) < EXTRACT_THRESHOLD:
        return desc

    keywords = _get_keywords(symbol)
    sentences = re.split(r'(?<=[.!?])\s+', desc)

    # Find sentences with keyword matches
    relevant: set = set()
    for i, sent in enumerate(sentences):
        lower = sent.lower()
        if any(kw in lower for kw in keywords):
            # Keep this sentence + 1 before + 1 after for context
            for j in range(max(0, i - 1), min(len(sentences), i + 2)):
                relevant.add(j)

    if not relevant:
        # No keyword match — just return first 2 sentences
        return " ".join(sentences[:2])

    return " ".join(sentences[i] for i in sorted(relevant))


def _detect_language(text: str) -> str:
    """Detect if text is Chinese or English.

    Returns:
        'zh' if text contains Chinese characters, 'en' otherwise
    """
    if not text:
        return 'en'
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    return 'en'


def _build_batch_prompt(symbol: str, articles: List[Dict[str, Any]]) -> str:
    """Build a single prompt containing up to 50 articles (English)."""
    lines = []
    for i, art in enumerate(articles):
        extract = _extract_relevant_text(art.get("description") or "", symbol)
        lines.append(f"[{i}] {art['title']}")
        if extract:
            lines.append(f"  > {extract}")

    return f"""Rate these {len(articles)} articles for {symbol}. Return JSON array only.

{chr(10).join(lines)}

Format: [{{"i":0,"r":"y"|"n","s":"+"|"-"|"0","e":"summary","u":"up reason","d":"down reason"}}]
r: "y" = article specifically discusses {symbol}, "n" = irrelevant/brief mention
s: "+" positive, "-" negative, "0" neutral
e: 10-word summary of what happened (empty if irrelevant)
u: why this could push {symbol} stock UP, e.g. "strong earnings beat expectations" (empty if none or irrelevant)
d: why this could push {symbol} stock DOWN, e.g. "antitrust lawsuit threatens App Store revenue" (empty if none or irrelevant)
JSON:"""


def _build_cn_batch_prompt(symbol: str, articles: List[Dict[str, Any]]) -> str:
    """Build a Chinese prompt for articles containing Chinese text."""
    lines = []
    for i, art in enumerate(articles):
        extract = _extract_relevant_text(art.get("description") or "", symbol)
        lines.append(f"[{i}] {art['title']}")
        if extract:
            lines.append(f"  > {extract}")

    return f"""对以下 {len(articles)} 篇关于 {symbol} 的新闻进行评分，仅返回 JSON 数组。

{chr(10).join(lines)}

格式: [{{"i":0,"r":"y"|"n","s":"+"|"-"|"0","e":"摘要","u":"上涨原因","d":"下跌原因"}}]
r: "y"=文章专门讨论该股票, "n"=不相关/简单提及
s: "+" 正面, "-" 负面, "0" 中性
e: 一句话摘要（中文，如无关可空）
u: 为什么这个消息可能推动股价上涨（中文，如无可填空）
d: 为什么这个消息可能推动股价下跌（中文，如无可填空）
JSON:"""


def get_pending_articles(symbol: str, limit: int = 10000) -> List[Dict[str, Any]]:
    """Get articles that passed Layer 0 but haven't been processed by Layer 1."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT nr.id, nr.title, nr.description
           FROM news_raw nr
           JOIN layer0_results l0 ON nr.id = l0.news_id AND l0.symbol = ?
           WHERE l0.passed = 1
           AND nr.id NOT IN (
               SELECT news_id FROM layer1_results WHERE symbol = ?
           )
           LIMIT ?""",
        (symbol, symbol, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _call_anthropic(prompt: str) -> str:
    """Call Anthropic Claude API."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text if message.content else "[]"


def _call_kimi(prompt: str) -> str:
    """Call Kimi Code API (Anthropic compatible format).

    Kimi Code (Coding Plan) uses Anthropic-compatible API:
    - Base URL: https://api.kimi.com/coding
    - Model: kimi-k2 or kimi-latest
    - Auth: ANTHROPIC_API_KEY format
    """
    import anthropic

    api_key = settings.kimi_api_key
    if not api_key:
        raise ValueError("kimi_api_key not set in settings")

    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=KIMI_CODE_BASE_URL,
    )

    message = client.messages.create(
        model=KIMI_CODE_MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text if message.content else "[]"


def _call_ai(prompt: str, lang: str = "en") -> str:
    """Call the configured AI provider."""
    if AI_PROVIDER == "kimi":
        return _call_kimi(prompt)
    else:
        return _call_anthropic(prompt)


def process_batch_group(
    symbol: str, articles: List[Dict[str, Any]]
) -> Dict[str, int]:
    """Process a group of up to 50 articles in a single API call."""
    conn = get_conn()

    stats = {"processed": 0, "relevant": 0, "irrelevant": 0, "errors": 0}

    # Detect language from first article's description
    sample_text = articles[0].get("description", "") if articles else ""
    lang = _detect_language(sample_text)

    # Build appropriate prompt based on language
    if lang == "zh":
        prompt = _build_cn_batch_prompt(symbol, articles)
    else:
        prompt = _build_batch_prompt(symbol, articles)

    try:
        text = _call_ai(prompt, lang)

        # Parse JSON array
        start = text.find("[")
        end = text.rfind("]") + 1
        if start < 0 or end <= start:
            stats["errors"] = len(articles)
            conn.close()
            return stats

        results = json.loads(text[start:end])

        for item in results:
            idx = item.get("i")
            if idx is None or idx >= len(articles):
                stats["errors"] += 1
                continue

            art = articles[idx]
            is_relevant = item.get("r") in ("y", "relevant")
            relevance = "relevant" if is_relevant else "irrelevant"
            raw_s = item.get("s", "0")
            sentiment = {"+": "positive", "-": "negative"}.get(raw_s, "neutral")

            conn.execute(
                """INSERT OR REPLACE INTO layer1_results
                   (news_id, symbol, relevance, key_discussion, sentiment,
                    reason_growth, reason_decrease)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    art["id"],
                    symbol,
                    relevance,
                    item.get("e", ""),
                    sentiment,
                    item.get("u", ""),
                    item.get("d", ""),
                ),
            )
            stats["processed"] += 1
            if is_relevant:
                stats["relevant"] += 1
            else:
                stats["irrelevant"] += 1

    except Exception as e:
        stats["errors"] = len(articles)
        print(f"Batch error for {symbol}: {e}")

    conn.commit()
    conn.close()
    return stats


def run_layer1(symbol: str, max_articles: int = 10000) -> Dict[str, Any]:
    """Run Layer 1 on all pending articles for a symbol.

    Processes in groups of 50 articles per API call.
    """
    articles = get_pending_articles(symbol, limit=max_articles)
    if not articles:
        return {"status": "no_pending", "total": 0}

    total_stats = {
        "total": len(articles), "processed": 0, "relevant": 0,
        "irrelevant": 0, "errors": 0, "api_calls": 0,
    }

    for i in range(0, len(articles), BATCH_SIZE):
        chunk = articles[i : i + BATCH_SIZE]
        stats = process_batch_group(symbol, chunk)

        total_stats["processed"] += stats["processed"]
        total_stats["relevant"] += stats["relevant"]
        total_stats["irrelevant"] += stats["irrelevant"]
        total_stats["errors"] += stats["errors"]
        total_stats["api_calls"] += 1

        print(f"  [{symbol}] Batch {total_stats['api_calls']}: "
              f"{stats['processed']}/{len(chunk)} ok, {stats['relevant']} relevant")

    return total_stats


# === Batch API support (for very large jobs, 50% cheaper) ===

def submit_batch_api(symbol: str, articles: List[Dict[str, Any]]) -> str:
    """Submit to Anthropic Batch API for async processing."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Detect language from first article
    sample_text = articles[0].get("description", "") if articles else ""
    lang = _detect_language(sample_text)
    use_cn_prompt = (lang == "zh")

    requests = []
    for i in range(0, len(articles), BATCH_SIZE):
        chunk = articles[i : i + BATCH_SIZE]
        chunk_ids = "|".join(a["id"] for a in chunk)

        # Use appropriate prompt based on language
        if use_cn_prompt:
            prompt = _build_cn_batch_prompt(symbol, chunk)
        else:
            prompt = _build_batch_prompt(symbol, chunk)

        requests.append(
            {
                "custom_id": f"{symbol}|{i}|{chunk_ids}",
                "params": {
                    "model": MODEL,
                    "max_tokens": MAX_OUTPUT_TOKENS,
                    "messages": [{"role": "user", "content": prompt}],
                },
            }
        )

    batch = client.messages.batches.create(requests=requests)

    conn = get_conn()
    conn.execute(
        """INSERT INTO batch_jobs (batch_id, symbol, status, total, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (batch.id, symbol, batch.processing_status, len(articles)),
    )
    conn.commit()
    conn.close()
    return batch.id


def check_batch_status(batch_id: str) -> Dict[str, Any]:
    """Check the status of a batch job."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    batch = client.messages.batches.retrieve(batch_id)

    conn = get_conn()
    conn.execute(
        "UPDATE batch_jobs SET status = ? WHERE batch_id = ?",
        (batch.processing_status, batch_id),
    )
    conn.commit()
    conn.close()

    return {
        "batch_id": batch.id,
        "status": batch.processing_status,
        "request_counts": {
            "processing": batch.request_counts.processing,
            "succeeded": batch.request_counts.succeeded,
            "errored": batch.request_counts.errored,
            "canceled": batch.request_counts.canceled,
            "expired": batch.request_counts.expired,
        },
    }


def collect_batch_results(batch_id: str) -> Dict[str, int]:
    """Collect results from a completed batch API job."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    conn = get_conn()

    stats = {"processed": 0, "relevant": 0, "irrelevant": 0, "errors": 0}

    for result in client.messages.batches.results(batch_id):
        custom_id = result.custom_id
        parts = custom_id.split("|", 2)
        if len(parts) < 3:
            stats["errors"] += 1
            continue

        symbol = parts[0]
        article_ids = parts[2].split("|")

        if result.result.type != "succeeded":
            stats["errors"] += len(article_ids)
            continue

        message = result.result.message
        text = message.content[0].text if message.content else "[]"

        try:
            start = text.find("[")
            end = text.rfind("]") + 1
            if start < 0 or end <= start:
                stats["errors"] += len(article_ids)
                continue

            items = json.loads(text[start:end])

            for item in items:
                idx = item.get("i")
                if idx is None or idx >= len(article_ids):
                    stats["errors"] += 1
                    continue

                is_relevant = item.get("r") in ("y", "relevant")
                relevance = "relevant" if is_relevant else "irrelevant"
                raw_s = item.get("s", "0")
                sentiment = {"+": "positive", "-": "negative"}.get(raw_s, "neutral")

                conn.execute(
                    """INSERT OR REPLACE INTO layer1_results
                       (news_id, symbol, relevance, key_discussion, sentiment,
                        reason_growth, reason_decrease)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        article_ids[idx],
                        symbol,
                        relevance,
                        item.get("e", ""),
                        sentiment,
                        item.get("u", ""),
                        item.get("d", ""),
                    ),
                )
                stats["processed"] += 1
                if is_relevant:
                    stats["relevant"] += 1
                else:
                    stats["irrelevant"] += 1

        except (json.JSONDecodeError, KeyError):
            stats["errors"] += len(article_ids)

    conn.execute(
        "UPDATE batch_jobs SET status = 'collected', finished_at = datetime('now') WHERE batch_id = ?",
        (batch_id,),
    )
    conn.commit()
    conn.close()
    return stats
