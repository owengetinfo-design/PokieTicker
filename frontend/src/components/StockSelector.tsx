import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

interface Ticker {
  symbol: string;
  name: string;
  sector?: string;
  market?: string;
}

// Hardcoded Chinese names for quick lookup
const CHINESE_NAMES: Record<string, string> = {
  '600519.SH': '贵州茅台',
  '000858.SZ': '五粮液',
  '000568.SZ': '泸州老窖',
  '600809.SH': '山西汾酒',
  '600036.SH': '招商银行',
  '601398.SH': '工商银行',
  '601288.SH': '农业银行',
  '600000.SH': '浦发银行',
  '002594.SZ': '比亚迪',
  '300750.SZ': '宁德时代',
  '601012.SH': '隆基绿能',
  '688981.SH': '中芯国际',
  '688256.SH': '寒武纪',
  '603501.SH': '韦尔股份',
  '00700.HK': '腾讯控股',
  '01810.HK': '小米集团',
  '09988.HK': '阿里巴巴',
  '09618.HK': '京东集团',
  '03690.HK': '美团',
  '01024.HK': '快手',
  '02318.HK': '中国平安',
  '03988.HK': '中国银行',
};

interface Props {
  activeTickers: string[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void;
}

const GROUPS: Record<string, string[]> = {
  // US Stocks
  'US Tech': ['AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN', 'CRM', 'ORCL', 'IBM', 'CSCO', 'NOW', 'WDAY', 'SNOW', 'DELL', 'ADBE'],
  'US AI / Chip': ['NVDA', 'AMD', 'TSM', 'AVGO', 'INTC', 'QCOM', 'ARM', 'AMAT', 'LRCX', 'MU', 'MRVL', 'SMCI', 'CRWV', 'TXN', 'ASML'],
  'US AI Software': ['AI', 'SOUN', 'SOUNW', 'CRWD', 'ANET', 'IDCC'],
  'US EV / Auto': ['TSLA', 'RIVN', 'LCID', 'NIO', 'LI', 'BYDDY', 'F', 'GM', 'STLA', 'TM'],
  'US China ADRs': ['BABA', 'JD', 'BIDU', 'NIO', 'LI', 'BILI', 'NTES', 'SE', 'MCHI', 'FXI'],
  'US Finance': ['V', 'MA', 'GS', 'MS', 'BAC', 'WFC', 'C', 'BLK', 'COIN', 'HOOD', 'MARA'],
  'US Media': ['NFLX', 'DIS', 'ROKU', 'WBD', 'ZM'],
  'US Consumer': ['COST', 'WMT', 'HD', 'TGT', 'NKE', 'SBUX', 'MCD', 'CMG', 'KO', 'EBAY', 'MELI'],
  'US Health': ['UNH', 'JNJ', 'LLY', 'MRNA', 'NVO'],
  'US Energy': ['XOM', 'CVX', 'OXY', 'XLE', 'USO'],
  'US Telecom': ['T', 'VZ'],
  'US Other': ['BA', 'UBER', 'GME', 'AMC', 'MULN', 'SQ', 'FB', 'AMJB', 'GLD', 'XLU', 'XLY', 'DIDI'],

  // A-Shares (CN) - 白酒/银行/新能源/科技
  'A股 白酒': ['600519.SH', '000858.SZ', '000568.SZ', '600809.SH'],
  'A股 银行': ['600036.SH', '601398.SH', '601288.SH', '600000.SH'],
  'A股 新能源': ['002594.SZ', '300750.SZ', '601012.SH'],
  'A股 科技': ['688981.SH', '688256.SH', '603501.SH'],

  // Hong Kong (HK) - 科技/金融
  '港股 科技': ['00700.HK', '01810.HK', '09988.HK', '09618.HK', '03690.HK', '01024.HK'],
  '港股 金融': ['02318.HK', '03988.HK'],
};

export default function StockSelector({ activeTickers, selectedSymbol, onSelect, onAdd }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Ticker[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const [tickerNames, setTickerNames] = useState<Record<string, string>>({});
  const searchRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Fetch ticker names when activeTickers changes
  useEffect(() => {
    if (activeTickers.length === 0) return;
    axios.get('/api/stocks').then((res) => {
      const nameMap: Record<string, string> = {};
      res.data.forEach((t: any) => {
        // Use Chinese name from database or hardcoded map
        const hardcodedName = CHINESE_NAMES[t.symbol];
        nameMap[t.symbol] = hardcodedName || t.name || t.symbol;
      });
      setTickerNames(nameMap);
    }).catch(console.error);
  }, [activeTickers]);

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
  const renderedGroups = Object.entries(GROUPS)
    .map(([label, symbols]) => ({
      label,
      symbols: symbols.filter((s) => activeSet.has(s)),
    }))
    .filter((g) => g.symbols.length > 0);

  const assigned = new Set(renderedGroups.flatMap((g) => g.symbols));
  const ungrouped = activeTickers.filter((s) => !assigned.has(s)).sort();
  if (ungrouped.length > 0) {
    const otherGroup = renderedGroups.find((g) => g.label === 'Other');
    if (otherGroup) {
      otherGroup.symbols.push(...ungrouped);
    } else {
      renderedGroups.push({ label: 'Other', symbols: ungrouped });
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
          {selectedSymbol && tickerNames[selectedSymbol] && (
            <span className="ticker-current-name">{tickerNames[selectedSymbol]}</span>
          )}
          <span className={`ticker-arrow ${showPanel ? 'open' : ''}`}>&#9662;</span>
        </button>

        {showPanel && (
          <div className="ticker-panel">
            {renderedGroups.map((group) => (
              <div className="ticker-panel-group" key={group.label}>
                <div className="ticker-panel-group-label">{group.label}</div>
                <div className="ticker-panel-group-items">
                  {group.symbols.map((sym) => (
                    <button
                      key={sym}
                      className={`ticker-panel-item ${sym === selectedSymbol ? 'active' : ''}`}
                      onClick={() => handleSelectTicker(sym)}
                      title={tickerNames[sym] || sym}
                    >
                      {sym}
                      {tickerNames[sym] && (
                        <span className="ticker-item-name">{tickerNames[sym]}</span>
                      )}
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
          placeholder="Search..."
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
