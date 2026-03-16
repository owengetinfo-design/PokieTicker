import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSettings, DEFAULT_SETTINGS } from '../contexts/SettingsContext';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function SettingsPanel({ open, onClose }: Props) {
  const { t } = useTranslation();
  const { settings, updateSettings, resetSettings, saveToBackend } = useSettings();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await saveToBackend();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch { /* ignore */ }
    setSaving(false);
  }

  function handleReset() {
    resetSettings();
  }

  return (
    <>
      {open && <div className="settings-overlay" onClick={onClose} />}
      <div className={`settings-panel ${open ? 'settings-panel-open' : ''}`}>
        <div className="settings-header">
          <h2>{t('settings.title')}</h2>
          <button className="settings-close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="settings-body">
          {/* Display */}
          <div className="settings-section">
            <div className="settings-section-title">{t('settings.display')}</div>
            <label className="settings-label">{t('settings.language')}</label>
            <div className="settings-lang-btns">
              <button
                className={`settings-lang-btn ${settings.language === 'en' ? 'active' : ''}`}
                onClick={() => updateSettings({ language: 'en' })}
              >
                {t('settings.english')}
              </button>
              <button
                className={`settings-lang-btn ${settings.language === 'zh' ? 'active' : ''}`}
                onClick={() => updateSettings({ language: 'zh' })}
              >
                {t('settings.chinese')}
              </button>
            </div>
          </div>

          {/* API Keys */}
          <div className="settings-section">
            <div className="settings-section-title">{t('settings.apiConfig')}</div>
            <label className="settings-label">{t('settings.anthropicKey')}</label>
            <input
              type="password"
              className="settings-input"
              value={settings.anthropicApiKey}
              onChange={(e) => updateSettings({ anthropicApiKey: e.target.value })}
              placeholder="sk-ant-..."
            />
            <label className="settings-label">{t('settings.polygonKey')}</label>
            <input
              type="password"
              className="settings-input"
              value={settings.polygonApiKey}
              onChange={(e) => updateSettings({ polygonApiKey: e.target.value })}
              placeholder="..."
            />
          </div>

          {/* AI Models */}
          <div className="settings-section">
            <div className="settings-section-title">{t('settings.aiModels')}</div>
            <div className="settings-subsection-title">{t('settings.layer1')}</div>
            <label className="settings-label">{t('settings.layer1Model')}</label>
            <input
              className="settings-input"
              value={settings.layer1Model}
              onChange={(e) => updateSettings({ layer1Model: e.target.value })}
            />
            <label className="settings-label">{t('settings.layer1BatchSize')}</label>
            <input
              type="number"
              className="settings-input"
              value={settings.layer1BatchSize}
              min={1}
              max={100}
              onChange={(e) => updateSettings({ layer1BatchSize: parseInt(e.target.value) || DEFAULT_SETTINGS.layer1BatchSize })}
            />
            <label className="settings-label">{t('settings.layer1MaxTokens')}</label>
            <input
              type="number"
              className="settings-input"
              value={settings.layer1MaxTokens}
              min={256}
              max={16384}
              onChange={(e) => updateSettings({ layer1MaxTokens: parseInt(e.target.value) || DEFAULT_SETTINGS.layer1MaxTokens })}
            />

            <div className="settings-subsection-title">{t('settings.layer2')}</div>
            <label className="settings-label">{t('settings.layer2Model')}</label>
            <input
              className="settings-input"
              value={settings.layer2Model}
              onChange={(e) => updateSettings({ layer2Model: e.target.value })}
            />
            <label className="settings-label">{t('settings.layer2MaxTokens')}</label>
            <input
              type="number"
              className="settings-input"
              value={settings.layer2MaxTokens}
              min={256}
              max={16384}
              onChange={(e) => updateSettings({ layer2MaxTokens: parseInt(e.target.value) || DEFAULT_SETTINGS.layer2MaxTokens })}
            />
          </div>

          {/* Prediction Parameters */}
          <div className="settings-section">
            <div className="settings-section-title">{t('settings.predictionParams')}</div>
            <label className="settings-label">{t('settings.forecastWindow')}</label>
            <input
              type="number"
              className="settings-input"
              value={settings.forecastWindow}
              min={3}
              max={60}
              onChange={(e) => updateSettings({ forecastWindow: parseInt(e.target.value) || DEFAULT_SETTINGS.forecastWindow })}
            />
            <label className="settings-label">{t('settings.similarPeriodsTopK')}</label>
            <input
              type="number"
              className="settings-input"
              value={settings.similarPeriodsTopK}
              min={1}
              max={30}
              onChange={(e) => updateSettings({ similarPeriodsTopK: parseInt(e.target.value) || DEFAULT_SETTINGS.similarPeriodsTopK })}
            />
            <label className="settings-label">{t('settings.similarArticlesTopK')}</label>
            <input
              type="number"
              className="settings-input"
              value={settings.similarArticlesTopK}
              min={1}
              max={50}
              onChange={(e) => updateSettings({ similarArticlesTopK: parseInt(e.target.value) || DEFAULT_SETTINGS.similarArticlesTopK })}
            />
          </div>
        </div>

        <div className="settings-footer">
          <button className="settings-reset-btn" onClick={handleReset}>
            {t('settings.resetDefaults')}
          </button>
          <button className="settings-save-btn" onClick={handleSave} disabled={saving}>
            {saved ? t('settings.saved') : t('settings.save')}
          </button>
        </div>
      </div>
    </>
  );
}
