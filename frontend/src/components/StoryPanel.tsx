import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

interface Props {
  symbol: string;
}

export default function StoryPanel({ symbol }: Props) {
  const { t } = useTranslation();
  const [story, setStory] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function generateStory() {
    setLoading(true);
    setError('');
    try {
      const res = await axios.post('/api/analysis/story', { symbol });
      setStory(res.data.story);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate story');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="story-panel">
      <h2>{t('story.title')}</h2>
      <button className="generate-story-btn" onClick={generateStory} disabled={loading || !symbol}>
        {loading ? t('story.generating') : t('story.generate')}
      </button>
      {error && <div className="error-message">{error}</div>}
      {story ? (
        <div className="story-content" dangerouslySetInnerHTML={{ __html: story }} />
      ) : (
        <div className="story-placeholder">
          {t('story.placeholder', { symbol: symbol || '...' })}
        </div>
      )}
    </div>
  );
}
