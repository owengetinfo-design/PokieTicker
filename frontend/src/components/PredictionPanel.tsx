import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';


interface Driver {
  name: string;
  value: number;
  importance: number;
  z_score: number;
  contribution: number;
}

interface HorizonPrediction {
  direction: 'up' | 'down';
  confidence: number;
  model_type?: string;
  top_drivers: Driver[];
  model_accuracy: number | null;
  baseline_accuracy: number | null;
}

interface SimilarPeriod {
  period_start: string;
  period_end: string;
  similarity: number;
  avg_sentiment: number;
  n_articles: number;
  ret_after_5d: number | null;
  ret_after_10d: number | null;
}

interface Headline {
  date: string;
  title: string;
  sentiment: string;
  summary: string;
}

interface ImpactArticle {
  news_id: string;
  date: string;
  title: string;
  sentiment: string;
  relevance: string | null;
  key_discussion: string;
  ret_t0: number | null;
  ret_t1: number | null;
}

interface NewsSummary {
  total: number;
  positive: number;
  negative: number;
  neutral: number;
  sentiment_ratio: number;
  top_headlines: Headline[];
  top_impact: ImpactArticle[];
}

interface SimilarStats {
  count: number;
  up_ratio_5d: number;
  up_ratio_10d: number;
  avg_ret_5d: number | null;
  avg_ret_10d: number | null;
}

interface DeepAnalysis {
  news_id: string;
  discussion: string;
  growth_reasons: string;
  decrease_reasons: string;
}

interface Forecast {
  symbol: string;
  window_days: number;
  forecast_date: string;
  news_summary: NewsSummary;
  prediction: Record<string, HorizonPrediction>;
  similar_periods: SimilarPeriod[];
  similar_stats: SimilarStats;
  conclusion: string;
}

interface Props {
  symbol: string;
}

function extractKeywords(headlines: Headline[]): string[] {
  const stopwords = new Set([
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
    'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'out', 'off', 'over', 'under', 'again', 'further',
    'then', 'once', 'and', 'but', 'or', 'nor', 'not', 'so', 'yet',
    'both', 'either', 'neither', 'each', 'every', 'all', 'any',
    'few', 'more', 'most', 'other', 'some', 'such', 'no', 'only',
    'own', 'same', 'than', 'too', 'very', 'just', 'because', 'about',
    'up', 'its', 'it', 'this', 'that', 'these', 'those', 'he', 'she',
    'they', 'them', 'their', 'what', 'which', 'who', 'whom', 'how',
    'new', 'says', 'said', 'also', 'like', 'now', 'one', 'two',
    'get', 'got', 'make', 'go', 'going', 'set', 'see', 'big', 'still',
  ]);

  const freq = new Map<string, number>();
  for (const h of headlines) {
    const words = h.title.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/);
    const seen = new Set<string>();
    for (const w of words) {
      if (w.length < 3 || stopwords.has(w) || seen.has(w)) continue;
      seen.add(w);
      freq.set(w, (freq.get(w) || 0) + 1);
    }
  }

  return Array.from(freq.entries())
    .filter(([, c]) => c >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([w]) => w);
}

/**
 * Parse conclusion text and return styled JSX:
 * - [ModelName] → bold purple badge
 * - bullish/leaning bullish → green bold
 * - bearish/leaning bearish → red bold
 * - +N% / -N% / N% → colored by sign
 * - positive → green, negative → red
 */
function renderStyledText(text: string): React.ReactNode[] {
  // Regex that matches all the patterns we want to style
  const pattern = /(\[[^\]]+\])|(bullish|leaning bullish|Bullish)|(bearish|leaning bearish|Bearish)|(positive)|(negative)|([+-]?\d+\.?\d*%)/gi;

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    // Push the plain text before this match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const [full, model, bullish, bearish, positive, negative, pct] = match;

    if (model) {
      // Hide model names like [XGBoost] — just skip them
      key++;
    } else if (bullish) {
      parts.push(
        <span key={key++} className="fc-text-bull">{full}</span>
      );
    } else if (bearish) {
      parts.push(
        <span key={key++} className="fc-text-bear">{full}</span>
      );
    } else if (positive) {
      parts.push(
        <span key={key++} className="fc-text-bull">{full}</span>
      );
    } else if (negative) {
      parts.push(
        <span key={key++} className="fc-text-bear">{full}</span>
      );
    } else if (pct) {
      const isNeg = pct.startsWith('-');
      parts.push(
        <span key={key++} className={isNeg ? 'fc-text-pct-down' : 'fc-text-pct-up'}>{full}</span>
      );
    }

    lastIndex = match.index + full.length;
  }

  // Remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

export default function PredictionPanel({ symbol }: Props) {
  const { t } = useTranslation();
  const [forecast7, setForecast7] = useState<Forecast | null>(null);
  const [forecast30, setForecast30] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(true);

  // Deep analysis state
  const [deepLoading, setDeepLoading] = useState<string | null>(null);
  const [deepResults, setDeepResults] = useState<Record<string, DeepAnalysis>>({});

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError('');
    Promise.all([
      axios.get(`/api/predict/${symbol}/forecast?window=7`).then((res) => res.data as Forecast).catch(() => null),
      axios.get(`/api/predict/${symbol}/forecast?window=30`).then((res) => res.data as Forecast).catch(() => null),
    ])
      .then(([f7, f30]) => {
        setForecast7(f7);
        setForecast30(f30);
        if (!f7 && !f30) setError('No model available');
      })
      .finally(() => setLoading(false));
  }, [symbol]);

  const keywords = useMemo(() => {
    const fc = forecast7 || forecast30;
    if (!fc) return [];
    return extractKeywords(fc.news_summary.top_headlines);
  }, [forecast7, forecast30]);

  // Primary forecast for the header summary
  const primaryForecast = forecast7 || forecast30;
  const primary = primaryForecast
    ? (primaryForecast.prediction.t3 || primaryForecast.prediction.t1 || primaryForecast.prediction.t5)
    : null;
  const isUp = primary?.direction === 'up';
  const ns = primaryForecast?.news_summary;

  if (loading) {
    return (
      <div className="pred-panel">
        <div className="pred-header" onClick={() => setExpanded(!expanded)}>
          <span className="pred-title">{t('prediction.forecast')}</span>
          <span className="pred-loading-dot" />
          <span className="pred-loading-text">{t('prediction.analyzing')}</span>
        </div>
      </div>
    );
  }

  if (error || (!forecast7 && !forecast30)) {
    return (
      <div className="pred-panel">
        <div className="pred-header">
          <span className="pred-title">{t('prediction.forecast')}</span>
          <span className="pred-no-model">{error || t('prediction.noData')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`pred-panel ${expanded ? 'pred-expanded' : ''}`}>
      {/* Header bar */}
      <div className="pred-header" onClick={() => setExpanded(!expanded)}>
        <span className="pred-title">{t('prediction.forecast')}</span>

        {primary && (
          <>
            <div className={`pred-arrow ${isUp ? 'up' : 'down'}`}>
              {isUp ? '\u2191' : '\u2193'}
            </div>
            <span className={`pred-dir ${isUp ? 'up' : 'down'}`}>
              {primary.direction.toUpperCase()}
            </span>
            <div className="pred-conf-bar">
              <div
                className={`pred-conf-fill ${isUp ? 'up' : 'down'}`}
                style={{ width: `${primary.confidence * 100}%` }}
              />
              <span className="pred-conf-label">{(primary.confidence * 100).toFixed(0)}%</span>
            </div>
          </>
        )}

        {ns && (
          <span className="pred-news-badge">
            {ns.total} news · {ns.positive}+ {ns.negative}-
          </span>
        )}

        <span className="pred-expand-icon">{expanded ? '\u25B2' : '\u25BC'}</span>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="pred-details">
          {/* Keyword tags (shared, show once) */}
          {keywords.length > 0 && (
            <div className="fc-keywords-section">
              <div className="fc-section-title">{t('prediction.keyTopics')}</div>
              <div className="fc-keywords">
                {keywords.map((kw) => (
                  <span key={kw} className="fc-keyword-pill">{kw}</span>
                ))}
              </div>
            </div>
          )}

          {/* 7D Forecast Section */}
          {forecast7 && (
            <ForecastSection
              label={t('prediction.day7')}
              forecast={forecast7}
              symbol={symbol}
              deepLoading={deepLoading}
              deepResults={deepResults}
              setDeepLoading={setDeepLoading}
              setDeepResults={setDeepResults}
            />
          )}

          {/* 30D Forecast Section */}
          {forecast30 && (
            <ForecastSection
              label={t('prediction.day30')}
              forecast={forecast30}
              symbol={symbol}
              deepLoading={deepLoading}
              deepResults={deepResults}
              setDeepLoading={setDeepLoading}
              setDeepResults={setDeepResults}
            />
          )}
        </div>
      )}
    </div>
  );
}

function ForecastSection({
  label,
  forecast,
  symbol,
  deepLoading,
  deepResults,
  setDeepLoading,
  setDeepResults,
}: {
  label: string;
  forecast: Forecast;
  symbol: string;
  deepLoading: string | null;
  deepResults: Record<string, DeepAnalysis>;
  setDeepLoading: (id: string | null) => void;
  setDeepResults: React.Dispatch<React.SetStateAction<Record<string, DeepAnalysis>>>;
}) {
  const { t } = useTranslation();
  const t1 = forecast.prediction.t1;
  const t3 = forecast.prediction.t3;
  const t5 = forecast.prediction.t5;
  const primary = t3 || t1 || t5;
  const isUp = primary?.direction === 'up';
  const ns = forecast.news_summary;
  const stats = forecast.similar_stats;

  const conclusionBullets = forecast.conclusion
    ? forecast.conclusion.split(/(?<=[.!?])\s+/).filter((s) => s.trim().length > 0)
    : [];

  return (
    <div className="fc-section-block">
      <div className="fc-section-divider">{label} {t('prediction.forecastSuffix')}</div>

      {/* AI Prediction Hero */}
      {primary && (
        <div className={`fc-hero ${isUp ? 'fc-hero-up' : 'fc-hero-down'}`}>
          <span className="fc-hero-arrow">{isUp ? '\u2191' : '\u2193'}</span>
          <div className="fc-hero-text">
            <span className="fc-hero-label">{label}:</span>
            <span className="fc-hero-dir">{isUp ? t('prediction.bullish') : t('prediction.bearish')}</span>
          </div>
          <span className="fc-hero-conf">{(primary.confidence * 100).toFixed(0)}%</span>
        </div>
      )}

      {/* Structured analysis bullets */}
      {conclusionBullets.length > 0 && (
        <div className="fc-analysis">
          <div className="fc-section-title">{t('prediction.analysis')}</div>
          <ul className="fc-bullet-list">
            {conclusionBullets.map((bullet, i) => (
              <li key={i} className="fc-bullet-item">{renderStyledText(bullet)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Prediction cards */}
      <div className="fc-predictions">
        {t1 && <PredictionCard label="T+1" pred={t1} />}
        {t3 && <PredictionCard label="T+3" pred={t3} />}
        {t5 && <PredictionCard label="T+5" pred={t5} />}
      </div>

      {/* Top Impact News */}
      {ns.top_impact && ns.top_impact.length > 0 && (
        <div className="fc-impact-section">
          <div className="fc-section-title">{t('prediction.keyImpactNews')}</div>
          {ns.top_impact.map((article) => {
            const retClass = (article.ret_t0 ?? 0) >= 0 ? 'up' : 'down';
            const deep = deepResults[article.news_id];
            const isAnalyzing = deepLoading === article.news_id;
            return (
              <div key={article.news_id} className={`fc-impact-card fc-impact-${retClass}`}>
                <div className="fc-impact-header">
                  <span className={`fc-impact-ret ${retClass}`}>
                    {article.ret_t0 != null ? `${article.ret_t0 >= 0 ? '+' : ''}${article.ret_t0.toFixed(2)}%` : '-'}
                  </span>
                  <span className={`fc-impact-sentiment ${article.sentiment || 'unknown'}`}>
                    {t(`sentiment.${article.sentiment || 'neutral'}`)}
                  </span>
                  <span className="fc-impact-date">{article.date}</span>
                </div>
                <div className="fc-impact-title">{article.title}</div>
                {article.key_discussion && (
                  <div className="fc-impact-summary">{article.key_discussion}</div>
                )}
                {deep ? (
                  <div className="fc-deep-result">
                    <div className="fc-deep-discussion">{deep.discussion}</div>
                    {deep.growth_reasons && (
                      <div className="fc-deep-reasons fc-deep-bull">
                        <span className="fc-deep-reasons-label">{t('prediction.bullishFactors')}</span>
                        <div className="fc-deep-reasons-text">{deep.growth_reasons}</div>
                      </div>
                    )}
                    {deep.decrease_reasons && (
                      <div className="fc-deep-reasons fc-deep-bear">
                        <span className="fc-deep-reasons-label">{t('prediction.riskFactors')}</span>
                        <div className="fc-deep-reasons-text">{deep.decrease_reasons}</div>
                      </div>
                    )}
                  </div>
                ) : (
                  <button
                    className="fc-deep-btn"
                    disabled={isAnalyzing}
                    onClick={() => {
                      setDeepLoading(article.news_id);
                      axios
                        .post('/api/analysis/deep', { news_id: article.news_id, symbol })
                        .then((res) => {
                          setDeepResults((prev) => ({ ...prev, [article.news_id]: res.data }));
                        })
                        .catch(() => {})
                        .finally(() => setDeepLoading(null));
                    }}
                  >
                    {isAnalyzing ? t('prediction.analyzingArticle') : t('prediction.deepAnalysis')}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Similar historical periods */}
      {stats.count > 0 && (
        <div className="fc-similar-section">
          <div className="fc-section-title">{t('prediction.similarPeriods', { count: stats.count })}</div>
          <div className="fc-similar-stats">
            <div className="fc-stat">
              <span className="fc-stat-label">{t('prediction.upRate5d')}</span>
              <span className={`fc-stat-value ${stats.up_ratio_5d > 0.5 ? 'up' : 'down'}`}>
                {(stats.up_ratio_5d * 100).toFixed(0)}%
              </span>
            </div>
            <div className="fc-stat">
              <span className="fc-stat-label">{t('prediction.avgRet5d')}</span>
              <span className={`fc-stat-value ${(stats.avg_ret_5d ?? 0) >= 0 ? 'up' : 'down'}`}>
                {stats.avg_ret_5d != null ? `${stats.avg_ret_5d >= 0 ? '+' : ''}${stats.avg_ret_5d.toFixed(1)}%` : '-'}
              </span>
            </div>
            <div className="fc-stat">
              <span className="fc-stat-label">{t('prediction.upRate10d')}</span>
              <span className={`fc-stat-value ${stats.up_ratio_10d > 0.5 ? 'up' : 'down'}`}>
                {(stats.up_ratio_10d * 100).toFixed(0)}%
              </span>
            </div>
            <div className="fc-stat">
              <span className="fc-stat-label">{t('prediction.avgRet10d')}</span>
              <span className={`fc-stat-value ${(stats.avg_ret_10d ?? 0) >= 0 ? 'up' : 'down'}`}>
                {stats.avg_ret_10d != null ? `${stats.avg_ret_10d >= 0 ? '+' : ''}${stats.avg_ret_10d.toFixed(1)}%` : '-'}
              </span>
            </div>
          </div>

          <div className="fc-periods-list">
            {forecast.similar_periods.slice(0, 5).map((p, i) => (
              <div key={i} className="fc-period-card">
                <div className="fc-period-header">
                  <span className="fc-period-dates">{p.period_start} ~ {p.period_end}</span>
                  <span className="fc-period-sim">{(p.similarity * 100).toFixed(0)}% {t('prediction.match')}</span>
                </div>
                <div className="fc-period-detail">
                  <span>{p.n_articles} {t('news.articles')}</span>
                  <span>{t('prediction.sentiment')}: {p.avg_sentiment >= 0 ? '+' : ''}{p.avg_sentiment.toFixed(2)}</span>
                  {p.ret_after_5d != null && (
                    <span className={p.ret_after_5d >= 0 ? 'up' : 'down'}>
                      5D: {p.ret_after_5d >= 0 ? '+' : ''}{p.ret_after_5d.toFixed(1)}%
                    </span>
                  )}
                  {p.ret_after_10d != null && (
                    <span className={p.ret_after_10d >= 0 ? 'up' : 'down'}>
                      10D: {p.ret_after_10d >= 0 ? '+' : ''}{p.ret_after_10d.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PredictionCard({ label, pred }: { label: string; pred: HorizonPrediction }) {
  const isUp = pred.direction === 'up';
  const hasAccuracy = pred.model_accuracy != null && pred.baseline_accuracy != null;
  const lift = hasAccuracy ? (pred.model_accuracy! - pred.baseline_accuracy!) : 0;
  const maxContrib = pred.top_drivers.length > 0
    ? Math.max(...pred.top_drivers.map((d) => d.contribution), 0.01)
    : 0.01;

  return (
    <div className={`fc-pred-card ${isUp ? 'up' : 'down'}`}>
      <div className="fc-pred-header">
        <span className="fc-pred-label">{label}</span>
        {/* model_type hidden — show generic "AI" label */}
        <span className={`fc-pred-dir ${isUp ? 'up' : 'down'}`}>
          {isUp ? '\u2191' : '\u2193'} {pred.direction.toUpperCase()}
        </span>
        <span className="fc-pred-conf">{(pred.confidence * 100).toFixed(0)}%</span>
      </div>
      {hasAccuracy && (
        <div className="fc-pred-meta">
          Acc {(pred.model_accuracy! * 100).toFixed(1)}% / Base {(pred.baseline_accuracy! * 100).toFixed(1)}% / Lift {lift >= 0 ? '+' : ''}{(lift * 100).toFixed(1)}pp
        </div>
      )}
      {pred.top_drivers.length > 0 && (
        <div className="fc-drivers">
          {pred.top_drivers.slice(0, 4).map((d) => (
            <div key={d.name} className="fc-driver-row">
              <span className="fc-driver-name">{d.name}</span>
              <div className="fc-driver-bar-track">
                <div
                  className={`fc-driver-bar-fill ${d.z_score > 0 ? 'up' : 'down'}`}
                  style={{ width: `${(d.contribution / maxContrib) * 100}%` }}
                />
              </div>
              <span className="fc-driver-val">
                {d.value.toFixed(2)} ({d.z_score > 0 ? '+' : ''}{d.z_score.toFixed(1)}\u03C3)
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
