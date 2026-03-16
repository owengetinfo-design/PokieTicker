import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useSettings } from '../contexts/SettingsContext';

interface SimilarArticle {
  news_id: string;
  symbol: string;
  title: string;
  trade_date: string | null;
  similarity: number;
  sentiment: string | null;
  ret_t0: number | null;
  ret_t1: number | null;
  ret_t3: number | null;
  ret_t5: number | null;
  ret_t10: number | null;
}

interface SimilarStats {
  total: number;
  cross_ticker_count: number;
  positive_t1_pct: number | null;
  positive_t5_pct: number | null;
  avg_ret_t1: number | null;
  avg_ret_t5: number | null;
  median_ret_t1: number | null;
  median_ret_t5: number | null;
}

interface SimilarResponse {
  query: { news_id: string; symbol: string; title: string | null; trade_date: string | null } | null;
  stats: SimilarStats;
  similar_articles: SimilarArticle[];
}

interface Props {
  newsId: string;
  symbol: string;
  onClose: () => void;
}

function pct(v: number | null) {
  if (v === null || v === undefined) return <span style={{ color: '#666' }}>-</span>;
  const pctVal = v * 100;
  const color = pctVal > 0 ? '#26a69a' : pctVal < 0 ? '#ef5350' : '#888';
  return <span style={{ color, fontWeight: 600 }}>{pctVal > 0 ? '+' : ''}{pctVal.toFixed(2)}%</span>;
}

function statPct(v: number | null) {
  if (v === null) return '-';
  return `${v.toFixed(1)}%`;
}

export default function SimilarNewsPanel({ newsId, symbol, onClose }: Props) {
  const { t } = useTranslation();
  const { settings } = useSettings();
  const [data, setData] = useState<SimilarResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    axios
      .post<SimilarResponse>('/api/analysis/similar', { news_id: newsId, symbol, top_k: settings.similarArticlesTopK })
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [newsId, symbol, settings.similarArticlesTopK]);

  return (
    <div className="news-panel similar-panel">
      <div className="news-panel-header">
        <h2>{t('similarNews.title')}</h2>
        <button className="range-clear-btn" onClick={onClose}>{t('similarNews.close')}</button>
      </div>

      {loading ? (
        <div className="news-empty">{t('similarNews.finding')}</div>
      ) : !data || data.similar_articles.length === 0 ? (
        <div className="news-empty">{t('similarNews.noResults')}</div>
      ) : (
        <div className="news-list">
          {/* Query article */}
          {data.query?.title && (
            <div className="similar-query-card">
              <div className="similar-query-label">{t('similarNews.queryArticle')}</div>
              <div className="similar-query-title">{data.query.title}</div>
              <div className="similar-query-meta">
                {data.query.symbol} · {data.query.trade_date || 'N/A'}
              </div>
            </div>
          )}

          {/* Stats card */}
          <div className="similar-stats-card">
            <div className="similar-stats-header">
              {t('similarNews.similarAcross', { total: data.stats.total, count: data.stats.cross_ticker_count })}
            </div>
            <div className="similar-stats-grid">
              <div className="similar-stat">
                <span className="similar-stat-label">{t('similarNews.t1Positive')}</span>
                <span className={`similar-stat-val ${(data.stats.positive_t1_pct ?? 0) > 50 ? 'up' : 'down'}`}>
                  {statPct(data.stats.positive_t1_pct)}
                </span>
              </div>
              <div className="similar-stat">
                <span className="similar-stat-label">{t('similarNews.t5Positive')}</span>
                <span className={`similar-stat-val ${(data.stats.positive_t5_pct ?? 0) > 50 ? 'up' : 'down'}`}>
                  {statPct(data.stats.positive_t5_pct)}
                </span>
              </div>
              <div className="similar-stat">
                <span className="similar-stat-label">{t('similarNews.avgT1')}</span>
                <span className="similar-stat-val">{pct(data.stats.avg_ret_t1)}</span>
              </div>
              <div className="similar-stat">
                <span className="similar-stat-label">{t('similarNews.avgT5')}</span>
                <span className="similar-stat-val">{pct(data.stats.avg_ret_t5)}</span>
              </div>
            </div>
          </div>

          {/* Similar articles list */}
          {data.similar_articles.map((art) => (
            <div key={`${art.news_id}-${art.symbol}`} className="news-card similar-card">
              <div className="similar-card-top">
                <span className="similar-ticker-badge">{art.symbol}</span>
                <span className="similar-score">{(art.similarity * 100).toFixed(0)}% {t('prediction.match')}</span>
              </div>
              <div className="news-title similar-title">{art.title}</div>
              <div className="news-card-footer">
                <span className="news-publisher">{art.trade_date || 'N/A'}</span>
                <div className="returns-chips">
                  <span className="ret-chip">T+1 {pct(art.ret_t1)}</span>
                  <span className="ret-chip">T+5 {pct(art.ret_t5)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
