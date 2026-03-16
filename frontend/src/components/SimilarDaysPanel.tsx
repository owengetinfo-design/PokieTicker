import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useSettings } from '../contexts/SettingsContext';

interface NewsSnippet {
  title: string;
  sentiment: string | null;
}

interface SimilarDay {
  date: string;
  similarity: number;
  sentiment_score: number;
  n_articles: number;
  ret_1d: number | null;
  rsi_14: number;
  ret_t1_after: number | null;
  ret_t5_after: number | null;
  news: NewsSnippet[];
}

interface SimilarDaysData {
  symbol: string;
  target_date: string;
  target_features: Record<string, number | null>;
  similar_days: SimilarDay[];
  stats: {
    up_ratio_t1: number | null;
    up_ratio_t5: number | null;
    avg_ret_t1: number | null;
    avg_ret_t5: number | null;
    count: number;
  };
}

interface Props {
  symbol: string;
  date: string;
  onClose: () => void;
}

export default function SimilarDaysPanel({ symbol, date, onClose }: Props) {
  const { t } = useTranslation();
  const { settings } = useSettings();
  const [data, setData] = useState<SimilarDaysData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    axios
      .get(`/api/predict/${symbol}/similar-days?date=${date}&top_k=${settings.similarPeriodsTopK}`)
      .then((res) => setData(res.data))
      .catch(() => setError(t('similar.failed')))
      .finally(() => setLoading(false));
  }, [symbol, date, settings.similarPeriodsTopK]);

  return (
    <div className="news-panel">
      <div className="news-panel-header">
        <h2>{t('similar.title')}</h2>
        <span className="news-date-badge">{date}</span>
        <button className="range-clear-btn" onClick={onClose}>{t('similar.close')}</button>
      </div>

      {loading ? (
        <div className="news-empty">
          <div className="range-loading">
            <div className="range-spinner" />
            <span>{t('similar.finding')}</span>
          </div>
        </div>
      ) : error ? (
        <div className="news-empty">{error}</div>
      ) : data ? (
        <div className="news-list">
          {/* Target day info */}
          <div className="sim-target-card">
            <div className="sim-section-label">{t('similar.targetFeatures')}</div>
            <div className="sim-feat-grid">
              <div className="sim-feat">
                <span className="sim-feat-label">{t('similar.sentiment')}</span>
                <span className={`sim-feat-val ${(data.target_features.sentiment_score ?? 0) >= 0 ? 'up' : 'down'}`}>
                  {(data.target_features.sentiment_score ?? 0).toFixed(2)}
                </span>
              </div>
              <div className="sim-feat">
                <span className="sim-feat-label">{t('similar.articles')}</span>
                <span className="sim-feat-val">{data.target_features.n_articles ?? 0}</span>
              </div>
              <div className="sim-feat">
                <span className="sim-feat-label">{t('similar.rsi')}</span>
                <span className="sim-feat-val">{(data.target_features.rsi_14 ?? 0).toFixed(0)}</span>
              </div>
              <div className="sim-feat">
                <span className="sim-feat-label">{t('similar.prev1d')}</span>
                <span className={`sim-feat-val ${(data.target_features.ret_1d ?? 0) >= 0 ? 'up' : 'down'}`}>
                  {((data.target_features.ret_1d ?? 0) * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* Stats summary */}
          <div className="sim-stats-card">
            <div className="sim-section-label">{t('similar.historicalPattern', { count: data.stats.count })}</div>
            <div className="sim-stats-grid">
              <div className="sim-stat-block">
                <span className="sim-stat-title">{t('similar.t1UpRatio')}</span>
                <span className={`sim-stat-big ${(data.stats.up_ratio_t1 ?? 0) >= 0.5 ? 'up' : 'down'}`}>
                  {data.stats.up_ratio_t1 !== null ? `${(data.stats.up_ratio_t1 * 100).toFixed(0)}%` : '-'}
                </span>
              </div>
              <div className="sim-stat-block">
                <span className="sim-stat-title">{t('similar.t5UpRatio')}</span>
                <span className={`sim-stat-big ${(data.stats.up_ratio_t5 ?? 0) >= 0.5 ? 'up' : 'down'}`}>
                  {data.stats.up_ratio_t5 !== null ? `${(data.stats.up_ratio_t5 * 100).toFixed(0)}%` : '-'}
                </span>
              </div>
              <div className="sim-stat-block">
                <span className="sim-stat-title">{t('similar.avgT1')}</span>
                <span className={`sim-stat-big ${(data.stats.avg_ret_t1 ?? 0) >= 0 ? 'up' : 'down'}`}>
                  {data.stats.avg_ret_t1 !== null ? `${data.stats.avg_ret_t1 >= 0 ? '+' : ''}${data.stats.avg_ret_t1.toFixed(2)}%` : '-'}
                </span>
              </div>
              <div className="sim-stat-block">
                <span className="sim-stat-title">{t('similar.avgT5')}</span>
                <span className={`sim-stat-big ${(data.stats.avg_ret_t5 ?? 0) >= 0 ? 'up' : 'down'}`}>
                  {data.stats.avg_ret_t5 !== null ? `${data.stats.avg_ret_t5 >= 0 ? '+' : ''}${data.stats.avg_ret_t5.toFixed(2)}%` : '-'}
                </span>
              </div>
            </div>
          </div>

          {/* Similar days list */}
          <div className="sim-section-label" style={{ padding: '8px 4px 4px' }}>{t('similar.similarDays')}</div>
          {data.similar_days.map((day) => (
            <div key={day.date} className="sim-day-card">
              <div className="sim-day-header">
                <span className="sim-day-date">{day.date}</span>
                <span className="sim-day-score">sim {(day.similarity * 100).toFixed(0)}%</span>
              </div>
              <div className="sim-day-details">
                <span className={`sim-day-chip ${day.sentiment_score >= 0 ? 'up' : 'down'}`}>
                  sent {day.sentiment_score.toFixed(2)}
                </span>
                <span className="sim-day-chip neutral">
                  {day.n_articles} news
                </span>
                <span className="sim-day-chip neutral">
                  RSI {day.rsi_14.toFixed(0)}
                </span>
              </div>
              <div className="sim-day-returns">
                <span className="sim-day-ret-label">After:</span>
                {day.ret_t1_after !== null && (
                  <span className={`sim-day-ret ${day.ret_t1_after >= 0 ? 'up' : 'down'}`}>
                    T+1 {day.ret_t1_after >= 0 ? '+' : ''}{day.ret_t1_after.toFixed(2)}%
                  </span>
                )}
                {day.ret_t5_after !== null && (
                  <span className={`sim-day-ret ${day.ret_t5_after >= 0 ? 'up' : 'down'}`}>
                    T+5 {day.ret_t5_after >= 0 ? '+' : ''}{day.ret_t5_after.toFixed(2)}%
                  </span>
                )}
              </div>
              {day.news && day.news.length > 0 && (
                <div className="sim-day-news">
                  {day.news.map((n, i) => (
                    <div key={i} className="sim-day-news-item">
                      <span className={`sentiment-dot ${n.sentiment || 'neutral'}`} />
                      <span className="sim-day-news-title">{n.title}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
