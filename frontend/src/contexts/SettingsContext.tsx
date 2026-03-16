import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';
import i18n from '../i18n';

export interface Settings {
  language: 'en' | 'zh';
  anthropicApiKey: string;
  polygonApiKey: string;
  layer1Model: string;
  layer1BatchSize: number;
  layer1MaxTokens: number;
  layer2Model: string;
  layer2MaxTokens: number;
  forecastWindow: number;
  similarPeriodsTopK: number;
  similarArticlesTopK: number;
}

export const DEFAULT_SETTINGS: Settings = {
  language: (i18n.language?.startsWith('zh') ? 'zh' : 'en') as 'en' | 'zh',
  anthropicApiKey: '',
  polygonApiKey: '',
  layer1Model: 'claude-haiku-4-5-20251001',
  layer1BatchSize: 50,
  layer1MaxTokens: 4096,
  layer2Model: 'claude-sonnet-4-5-20250929',
  layer2MaxTokens: 1024,
  forecastWindow: 7,
  similarPeriodsTopK: 10,
  similarArticlesTopK: 20,
};

const STORAGE_KEY = 'pokieticker-settings';

function loadSettings(): Settings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_SETTINGS };
}

interface SettingsContextType {
  settings: Settings;
  updateSettings: (partial: Partial<Settings>) => void;
  resetSettings: () => void;
  saveToBackend: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextType | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(loadSettings);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  function updateSettings(partial: Partial<Settings>) {
    setSettings((prev) => {
      const next = { ...prev, ...partial };
      if (partial.language && partial.language !== prev.language) {
        i18n.changeLanguage(partial.language);
      }
      return next;
    });
  }

  function resetSettings() {
    const defaults = { ...DEFAULT_SETTINGS, language: settings.language };
    setSettings(defaults);
  }

  async function saveToBackend() {
    const { language, ...backendSettings } = settings;
    void language;
    await axios.post('/api/settings', backendSettings);
  }

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, resetSettings, saveToBackend }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}
