import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { createPortal } from 'react-dom';

interface RangeSelection {
  startDate: string;
  endDate: string;
  priceChange?: number;
  popupX?: number;
  popupY?: number;
}

interface Props {
  range: RangeSelection;
  chartRect?: DOMRect;
  onAsk: (question: string) => void;
  onClose: () => void;
}

export default function RangeQueryPopup({ range, chartRect, onAsk, onClose }: Props) {
  const { t } = useTranslation();
  const [custom, setCustom] = useState('');
  const popupRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const PRESET_QUESTIONS = [
    t('rangeQuery.q1'),
    t('rangeQuery.q2'),
    t('rangeQuery.q3'),
  ];

  // Close on click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    // Delay to avoid the brush mouseup from closing immediately
    const timer = setTimeout(() => document.addEventListener('mousedown', handleClick), 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [onClose]);

  const change = range.priceChange ?? 0;
  const isUp = change >= 0;

  // Convert chart-relative coords to viewport-fixed coords
  const offsetLeft = chartRect ? chartRect.left : 0;
  const offsetTop = chartRect ? chartRect.top : 0;
  const left = Math.min((range.popupX ?? 200) + offsetLeft, window.innerWidth - 300);
  const top = Math.max((range.popupY ?? 100) + offsetTop, 10);

  const popup = (
    <div
      ref={popupRef}
      className="range-popup"
      style={{ left: `${left}px`, top: `${top}px` }}
    >
      <div className="range-popup-header">
        <span className="range-popup-dates">
          {range.startDate} - {range.endDate}
        </span>
        <span className={`range-popup-change ${isUp ? 'up' : 'down'}`}>
          {isUp ? '+' : ''}{change.toFixed(2)}%
        </span>
      </div>

      <div className="range-popup-label">{t('rangeQuery.askLabel')}</div>

      {PRESET_QUESTIONS.map((q) => (
        <button
          key={q}
          className="range-popup-preset"
          onClick={() => onAsk(q)}
        >
          <span>{q}</span>
          <span className="range-popup-arrow">&rsaquo;</span>
        </button>
      ))}

      <form
        className="range-popup-custom"
        onSubmit={(e) => {
          e.preventDefault();
          if (custom.trim()) onAsk(custom.trim());
        }}
      >
        <input
          ref={inputRef}
          type="text"
          placeholder={t('rangeQuery.placeholder')}
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
        />
        <button type="submit" className="range-popup-submit">&rsaquo;</button>
      </form>
    </div>
  );

  return createPortal(popup, document.body);
}
