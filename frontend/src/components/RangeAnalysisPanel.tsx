import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

interface RangeAnalysis {
  symbol: string;
  start_date: string;
  end_date: string;
  price_change_pct: number;
  open_price: number;
  close_price: number;
  high_price: number;
  low_price: number;
  news_count: number;
  trading_days: number;
  question?: string;
  analysis: {
    summary: string;
    key_events: string[];
    bullish_factors: string[];
    bearish_factors: string[];
    trend_analysis: string;
  };
  error?: string;
}

interface Props {
  symbol: string;
  startDate: string;
  endDate: string;
  question?: string;
  onClear: () => void;
}

export default function RangeAnalysisPanel({ symbol, startDate, endDate, question, onClear }: Props) {
  const { t } = useTranslation();
  const [data, setData] = useState<RangeAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setData(null);

    axios
      .post<RangeAnalysis>(
        '/api/analysis/range',
        { symbol, start_date: startDate, end_date: endDate, question },
        { signal: controller.signal }
      )
      .then((res) => {
        if (res.data.error) {
          setError(res.data.error);
        } else {
          setData(res.data);
        }
      })
      .catch((err) => {
        if (!axios.isCancel(err)) {
          setError('Analysis failed');
        }
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [symbol, startDate, endDate, question]);

  const changePct = data?.price_change_pct ?? 0;
  const isUp = changePct >= 0;

  return (
    <div className="news-panel range-panel">
      <div className="news-panel-header">
        <h2>{t('range.title')}</h2>
        <button className="range-clear-btn" onClick={onClear}>{t('range.clear')}</button>
      </div>

      {loading ? (
        <div className="news-list" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32 }}>
          <div className="range-spinner" />
          <span style={{ color: '#aab', fontSize: 15 }}>{t('range.aiAnalyzing', { start: startDate, end: endDate })}</span>
          <div className="ai-loading-skeleton">
            <div className="skeleton-line" style={{ width: '90%' }} />
            <div className="skeleton-line" style={{ width: '75%' }} />
            <div className="skeleton-line" style={{ width: '60%' }} />
            <div className="skeleton-line" style={{ width: '80%' }} />
          </div>
        </div>
      ) : error ? (
        <div className="news-empty">{error}</div>
      ) : data ? (
        <div className="news-list">
          {/* Question asked */}
          {question && (
            <div className="range-question-card">
              <span className="range-question-icon">?</span>
              <span className="range-question-text">{question}</span>
            </div>
          )}

          {/* Price summary card */}
          <div className="range-price-card">
            <div className="range-dates">{data.start_date} to {data.end_date}</div>
            <div className="range-price-row">
              <span className="range-price">${data.open_price.toFixed(2)} → ${data.close_price.toFixed(2)}</span>
              <span className={`range-change ${isUp ? 'up' : 'down'}`}>
                {isUp ? '+' : ''}{changePct.toFixed(2)}%
              </span>
            </div>
            <div className="range-meta">
              {data.trading_days} {t('range.tradingDays')} · {data.news_count} {t('range.newsArticles')}
            </div>
          </div>

          {/* Summary */}
          {data.analysis.summary && (
            <div className="range-section">
              <p className="range-summary">{data.analysis.summary}</p>
            </div>
          )}

          {/* Key events */}
          {data.analysis.key_events?.length > 0 && (
            <div className="range-section">
              <h3 className="range-section-title">{t('range.keyEvents')}</h3>
              <ul className="range-events">
                {data.analysis.key_events.map((evt, i) => (
                  <li key={i}>{evt}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Bullish factors */}
          {data.analysis.bullish_factors?.length > 0 && (
            <div className="range-section">
              <h3 className="range-section-title">{t('range.bullishFactors')}</h3>
              {data.analysis.bullish_factors.map((f, i) => (
                <div key={i} className="reason up">
                  <span className="reason-icon">+</span> {f}
                </div>
              ))}
            </div>
          )}

          {/* Bearish factors */}
          {data.analysis.bearish_factors?.length > 0 && (
            <div className="range-section">
              <h3 className="range-section-title">{t('range.bearishFactors')}</h3>
              {data.analysis.bearish_factors.map((f, i) => (
                <div key={i} className="reason down">
                  <span className="reason-icon">-</span> {f}
                </div>
              ))}
            </div>
          )}

          {/* Trend analysis */}
          {data.analysis.trend_analysis && (
            <div className="range-section">
              <h3 className="range-section-title">{t('range.trendAnalysis')}</h3>
              <p className="range-trend">{data.analysis.trend_analysis}</p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
