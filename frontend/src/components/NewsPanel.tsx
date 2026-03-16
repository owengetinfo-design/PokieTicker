import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

interface NewsItem {
  news_id: string;
  trade_date: string;
  published_utc: string;
  title: string;
  description: string;
  publisher: string;
  article_url: string;
  image_url: string | null;
  relevance: string | null;
  key_discussion: string | null;
  sentiment: string | null;
  reason_growth: string | null;
  reason_decrease: string | null;
  ret_t0: number | null;
  ret_t1: number | null;
  ret_t3: number | null;
  ret_t5: number | null;
  ret_t10: number | null;
}

interface Props {
  symbol: string;
  hoveredDate: string | null;
  onFindSimilar?: (newsId: string) => void;
  highlightedNewsId?: string | null;
  isLocked?: boolean;
  onUnlock?: () => void;
  highlightedCategoryIds?: string[];
}

function sortBySentiment(items: NewsItem[]): NewsItem[] {
  const order: Record<string, number> = { positive: 0, negative: 1, neutral: 2 };
  return [...items].sort((a, b) => {
    const sa = order[a.sentiment || 'neutral'] ?? 2;
    const sb = order[b.sentiment || 'neutral'] ?? 2;
    return sa - sb;
  });
}

function pct(v: number | null) {
  if (v === null || v === undefined) return '-';
  const pctVal = v * 100;
  const color = pctVal > 0 ? '#26a69a' : pctVal < 0 ? '#ef5350' : '#888';
  return <span style={{ color, fontWeight: 600 }}>{pctVal > 0 ? '+' : ''}{pctVal.toFixed(2)}%</span>;
}

export default function NewsPanel({ symbol, hoveredDate, onFindSimilar, highlightedNewsId, isLocked, onUnlock, highlightedCategoryIds }: Props) {
  const { t } = useTranslation();
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [displayDate, setDisplayDate] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const cacheRef = useRef<Map<string, NewsItem[]>>(new Map());
  const listRef = useRef<HTMLDivElement>(null);

  // Debounced fetch on hover
  useEffect(() => {
    if (!symbol || !hoveredDate) return;
    // If locked and date hasn't changed, skip refetch
    if (isLocked && displayDate === hoveredDate) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      const cacheKey = `${symbol}_${hoveredDate}`;
      const cached = cacheRef.current.get(cacheKey);
      if (cached) {
        setNews(sortBySentiment(cached));
        setDisplayDate(hoveredDate);
        return;
      }

      setLoading(true);
      axios
        .get(`/api/news/${symbol}?date=${hoveredDate}`)
        .then((res) => {
          cacheRef.current.set(cacheKey, res.data);
          setNews(sortBySentiment(res.data));
          setDisplayDate(hoveredDate);
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    }, 120);
  }, [symbol, hoveredDate]);

  // Clear cache on symbol change
  useEffect(() => {
    cacheRef.current.clear();
    setNews([]);
    setDisplayDate(null);
  }, [symbol]);

  // Auto-scroll to highlighted article
  useEffect(() => {
    if (!highlightedNewsId || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-news-id="${highlightedNewsId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlightedNewsId, news]);

  const categorySet = highlightedCategoryIds && highlightedCategoryIds.length > 0
    ? new Set(highlightedCategoryIds)
    : null;

  // If category filter is active but NO articles on this date match, disable dimming
  const hasAnyMatch = categorySet != null && news.some((item) => categorySet.has(item.news_id));
  const effectiveCategorySet = (categorySet != null && !hasAnyMatch) ? null : categorySet;

  if (!displayDate) {
    return (
      <div className="news-panel">
        <div className="news-panel-header">
          <h2>{t('news.title')}</h2>
        </div>
        <div className="news-empty">{t('news.tapToSee')}</div>
      </div>
    );
  }

  return (
    <div className="news-panel">
      <div className="news-panel-header">
        <h2>{t('news.title')}</h2>
        <span className="news-date-badge">{displayDate}</span>
        <span className="news-count">{news.length} {t('news.articles')}</span>
        {isLocked && (
          <button className="lock-badge" onClick={onUnlock} title="Click to unlock">
            {t('news.locked')}
          </button>
        )}
      </div>

      {loading && news.length === 0 ? (
        <div className="news-empty">{t('news.loading')}</div>
      ) : news.length === 0 ? (
        <div className="news-empty">{t('news.noNews')}</div>
      ) : (
        <div className="news-list" ref={listRef}>
          {news.map((item) => {
            const isDimmed = effectiveCategorySet != null && !effectiveCategorySet.has(item.news_id);
            return (
              <div
                key={item.news_id}
                data-news-id={item.news_id}
                className={`news-card ${item.sentiment === 'positive' ? 'card-positive' : item.sentiment === 'negative' ? 'card-negative' : 'card-neutral'}${highlightedNewsId === item.news_id ? ' card-highlighted' : ''}${isDimmed ? ' card-dimmed' : ''}`}
              >
                <div className="news-card-top">
                  <span className={`sentiment-dot ${item.sentiment || 'neutral'}`} />
                  <a href={item.article_url} target="_blank" rel="noreferrer" className="news-title">
                    {item.title}
                  </a>
                </div>

                {item.image_url && (
                  <div className="news-image-wrap">
                    <img
                      src={item.image_url}
                      alt=""
                      className="news-image"
                      loading="lazy"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                  </div>
                )}

                {item.key_discussion && (
                  <p className="news-summary">{item.key_discussion}</p>
                )}

                {(item.reason_growth || item.reason_decrease) && (
                  <div className="news-reasons">
                    {item.reason_growth && (
                      <div className="reason up">
                        <span className="reason-icon">+</span> {item.reason_growth}
                      </div>
                    )}
                    {item.reason_decrease && (
                      <div className="reason down">
                        <span className="reason-icon">-</span> {item.reason_decrease}
                      </div>
                    )}
                  </div>
                )}

                <div className="news-card-footer">
                  <span className="news-publisher">{item.publisher}</span>
                  <div className="returns-chips">
                    <span className="ret-chip">T+1 {pct(item.ret_t1)}</span>
                    <span className="ret-chip">T+5 {pct(item.ret_t5)}</span>
                    {onFindSimilar && (
                      <button
                        className="find-similar-btn"
                        onClick={(e) => { e.stopPropagation(); onFindSimilar(item.news_id); }}
                      >
                        {t('news.findSimilar')}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
