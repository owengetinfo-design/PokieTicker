import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

interface CategoryInfo {
  label: string;
  count: number;
  article_ids: string[];
  positive_ids: string[];
  negative_ids: string[];
  neutral_ids: string[];
}

interface CategoriesResponse {
  categories: Record<string, CategoryInfo>;
  total: number;
}

interface Props {
  symbol: string;
  activeCategory: string | null;
  onCategoryChange: (category: string | null, articleIds: string[], color?: string) => void;
}

const CATEGORY_META: Record<string, { icon: string; labelKey: string; color: string }> = {
  market:       { icon: '\u{1F4C8}', labelKey: 'category.market',       color: '#667eea' },
  policy:       { icon: '\u{1F3DB}\uFE0F', labelKey: 'category.policy',       color: '#f59e0b' },
  earnings:     { icon: '\u{1F4B0}', labelKey: 'category.earnings',     color: '#10b981' },
  product_tech: { icon: '\u{1F680}', labelKey: 'category.productTech',  color: '#8b5cf6' },
  competition:  { icon: '\u2694\uFE0F',  labelKey: 'category.competition',  color: '#ef4444' },
  management:   { icon: '\u{1F464}', labelKey: 'category.management',   color: '#06b6d4' },
};

type SentimentFilter = 'all' | 'positive' | 'negative';

export default function NewsCategoryPanel({ symbol, activeCategory, onCategoryChange }: Props) {
  const { t } = useTranslation();
  const [categories, setCategories] = useState<Record<string, CategoryInfo>>({});
  const [sentimentFilter, setSentimentFilter] = useState<SentimentFilter>('all');

  useEffect(() => {
    if (!symbol) return;
    axios
      .get<CategoriesResponse>(`/api/news/${symbol}/categories`)
      .then((res) => setCategories(res.data.categories))
      .catch(() => setCategories({}));
  }, [symbol]);

  // Reset sentiment sub-filter when category changes
  useEffect(() => {
    setSentimentFilter('all');
  }, [activeCategory]);

  const keys = Object.keys(categories).filter((k) => categories[k].count > 0);
  if (keys.length === 0) return null;

  function handleSentimentClick(filter: SentimentFilter) {
    if (!activeCategory) return;
    const cat = categories[activeCategory];
    const meta = CATEGORY_META[activeCategory] || { color: '#667eea' };
    setSentimentFilter(filter);
    let ids: string[];
    let color: string;
    if (filter === 'positive') {
      ids = cat.positive_ids;
      color = '#00e676';
    } else if (filter === 'negative') {
      ids = cat.negative_ids;
      color = '#ff5252';
    } else {
      ids = cat.article_ids;
      color = meta.color;
    }
    onCategoryChange(activeCategory, ids, color);
  }

  const activeCat = activeCategory ? categories[activeCategory] : null;

  return (
    <div className="news-category-wrap">
      <div className="news-category-bar">
        {keys.map((key) => {
          const cat = categories[key];
          const meta = CATEGORY_META[key] || { icon: '\u{1F4CC}', labelKey: key, color: '#667eea' };
          const isActive = activeCategory === key;
          return (
            <button
              key={key}
              className={`category-tag ${isActive ? 'category-tag-active' : ''}`}
              style={{
                '--tag-color': meta.color,
                '--tag-color-bg': `${meta.color}18`,
                '--tag-color-bg-active': `${meta.color}30`,
              } as React.CSSProperties}
              onClick={() => {
                if (isActive) {
                  onCategoryChange(null, []);
                } else {
                  setSentimentFilter('all');
                  onCategoryChange(key, cat.article_ids, meta.color);
                }
              }}
            >
              <span className="category-tag-icon">{meta.icon}</span>
              <div className="category-tag-body">
                <span className="category-tag-label">{t(meta.labelKey)}</span>
                <span className="category-tag-count">{cat.count} {t('news.articles')}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Sentiment sub-filter row — only shown when a category is active */}
      {activeCat && (
        <div className="sentiment-sub-bar">
          <button
            className={`sentiment-sub-btn ${sentimentFilter === 'all' ? 'sentiment-sub-active' : ''}`}
            onClick={() => handleSentimentClick('all')}
          >
            {t('category.all')} <span className="sentiment-sub-count">{activeCat.count}</span>
          </button>
          <button
            className={`sentiment-sub-btn sentiment-sub-up ${sentimentFilter === 'positive' ? 'sentiment-sub-active' : ''}`}
            onClick={() => handleSentimentClick('positive')}
          >
            {t('category.bullish')} <span className="sentiment-sub-count">{activeCat.positive_ids.length}</span>
          </button>
          <button
            className={`sentiment-sub-btn sentiment-sub-down ${sentimentFilter === 'negative' ? 'sentiment-sub-active' : ''}`}
            onClick={() => handleSentimentClick('negative')}
          >
            {t('category.bearish')} <span className="sentiment-sub-count">{activeCat.negative_ids.length}</span>
          </button>
        </div>
      )}
    </div>
  );
}
