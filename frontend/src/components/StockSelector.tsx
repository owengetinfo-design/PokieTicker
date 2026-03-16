import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

interface Ticker {
  symbol: string;
  name: string;
  sector?: string;
}

interface Props {
  activeTickers: string[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void;
}

const GROUP_KEYS = [
  'tech', 'aiChip', 'aiSoftware', 'evAuto', 'china', 'finance',
  'media', 'consumer', 'health', 'energy', 'telecom', 'other',
] as const;

const GROUP_SYMBOLS: Record<string, string[]> = {
  'tech': ['AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN', 'CRM', 'ORCL', 'IBM', 'CSCO', 'NOW', 'WDAY', 'SNOW', 'DELL', 'ADBE'],
  'aiChip': ['NVDA', 'AMD', 'TSM', 'AVGO', 'INTC', 'QCOM', 'ARM', 'AMAT', 'LRCX', 'MU', 'MRVL', 'SMCI', 'CRWV', 'TXN', 'ASML'],
  'aiSoftware': ['AI', 'SOUN', 'SOUNW', 'CRWD', 'ANET', 'IDCC'],
  'evAuto': ['TSLA', 'RIVN', 'LCID', 'NIO', 'LI', 'BYDDY', 'F', 'GM', 'STLA', 'TM'],
  'china': ['BABA', 'JD', 'BIDU', 'NIO', 'LI', 'BILI', 'NTES', 'SE', 'MCHI', 'FXI'],
  'finance': ['V', 'MA', 'GS', 'MS', 'BAC', 'WFC', 'C', 'BLK', 'COIN', 'HOOD', 'MARA'],
  'media': ['NFLX', 'DIS', 'ROKU', 'WBD', 'ZM'],
  'consumer': ['COST', 'WMT', 'HD', 'TGT', 'NKE', 'SBUX', 'MCD', 'CMG', 'KO', 'EBAY', 'MELI'],
  'health': ['UNH', 'JNJ', 'LLY', 'MRNA', 'NVO'],
  'energy': ['XOM', 'CVX', 'OXY', 'XLE', 'USO'],
  'telecom': ['T', 'VZ'],
  'other': ['BA', 'UBER', 'GME', 'AMC', 'MULN', 'SQ', 'FB', 'AMJB', 'GLD', 'XLU', 'XLY', 'DIDI'],
};

export default function StockSelector({ activeTickers, selectedSymbol, onSelect, onAdd }: Props) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Ticker[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearch(false);
      }
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowPanel(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleSearch(q: string) {
    setQuery(q);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (q.length < 1) {
      setResults([]);
      setShowSearch(false);
      return;
    }
    timerRef.current = setTimeout(async () => {
      try {
        const res = await axios.get(`/api/stocks/search?q=${encodeURIComponent(q)}`);
        setResults(res.data);
        setShowSearch(true);
      } catch {
        setResults([]);
      }
    }, 300);
  }

  function handlePick(ticker: Ticker) {
    setQuery('');
    setShowSearch(false);
    setShowPanel(false);
    if (!activeTickers.includes(ticker.symbol)) {
      onAdd(ticker.symbol);
    }
    onSelect(ticker.symbol);
  }

  function handleSelectTicker(sym: string) {
    setShowPanel(false);
    onSelect(sym);
  }

  // Build groups filtered to only tickers that exist in our data
  const activeSet = new Set(activeTickers);
  const renderedGroups = GROUP_KEYS
    .map((key) => ({
      key,
      label: t(`stock.${key}`),
      symbols: (GROUP_SYMBOLS[key] || []).filter((s) => activeSet.has(s)),
    }))
    .filter((g) => g.symbols.length > 0);

  const assigned = new Set(renderedGroups.flatMap((g) => g.symbols));
  const ungrouped = activeTickers.filter((s) => !assigned.has(s)).sort();
  if (ungrouped.length > 0) {
    const otherGroup = renderedGroups.find((g) => g.key === 'other');
    if (otherGroup) {
      otherGroup.symbols.push(...ungrouped);
    } else {
      renderedGroups.push({ key: 'other', label: t('stock.other'), symbols: ungrouped });
    }
  }

  return (
    <div className="stock-selector">
      {/* Current ticker button — click to open dropdown */}
      <div className="ticker-dropdown-wrapper" ref={panelRef}>
        <button
          className="ticker-current"
          onClick={() => setShowPanel((v) => !v)}
        >
          <span className="ticker-current-symbol">{selectedSymbol || '---'}</span>
          <span className={`ticker-arrow ${showPanel ? 'open' : ''}`}>&#9662;</span>
        </button>

        {showPanel && (
          <div className="ticker-panel">
            {renderedGroups.map((group) => (
              <div className="ticker-panel-group" key={group.key}>
                <div className="ticker-panel-group-label">{group.label}</div>
                <div className="ticker-panel-group-items">
                  {group.symbols.map((sym) => (
                    <button
                      key={sym}
                      className={`ticker-panel-item ${sym === selectedSymbol ? 'active' : ''}`}
                      onClick={() => handleSelectTicker(sym)}
                    >
                      {sym}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Search */}
      <div className="search-wrapper" ref={searchRef}>
        <input
          type="text"
          placeholder={t('stock.search')}
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => results.length > 0 && setShowSearch(true)}
        />
        {showSearch && results.length > 0 && (
          <ul className="search-dropdown">
            {results.map((t) => (
              <li key={t.symbol} onClick={() => handlePick(t)}>
                <strong>{t.symbol}</strong> <span>{t.name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
