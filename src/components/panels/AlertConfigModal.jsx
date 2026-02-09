import { memo, useState } from 'react';
import { X, Bell } from 'lucide-react';

const CONDITIONS = [
  { value: 'price_above', label: 'Price Above' },
  { value: 'price_below', label: 'Price Below' },
  { value: 'pct_change_above', label: '% Change Above' },
  { value: 'pct_change_below', label: '% Change Below' },
];

const AlertConfigModal = memo(({ isOpen, onClose, onAdd }) => {
  const [symbol, setSymbol] = useState('');
  const [condition, setCondition] = useState('price_above');
  const [threshold, setThreshold] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!symbol || !threshold) return;
    onAdd({ symbol, condition, threshold });
    setSymbol('');
    setThreshold('');
    onClose();
  };

  const inputStyle = {
    background: 'var(--bg-0)', border: '1px solid var(--border-2)', borderRadius: 4,
    color: 'var(--text-1)', fontSize: 11, padding: '5px 8px', fontFamily: 'var(--font-mono)',
    outline: 'none', width: '100%', boxSizing: 'border-box',
  };

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.6)', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: 'var(--bg-1)', border: '1px solid var(--border-2)',
        borderRadius: 10, padding: 20, width: 320, maxWidth: '90vw',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bell size={16} color="var(--amber)" />
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>New Alert</span>
          </div>
          <button onClick={onClose} className="btn-ghost" style={{ padding: 4 }}>
            <X size={14} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <label style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 3, display: 'block' }}>Symbol</label>
            <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} placeholder="AAPL, BTC, etc." style={inputStyle} autoFocus />
          </div>
          <div>
            <label style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 3, display: 'block' }}>Condition</label>
            <select value={condition} onChange={e => setCondition(e.target.value)} style={inputStyle}>
              {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 3, display: 'block' }}>
              {condition.includes('pct') ? 'Threshold (%)' : 'Threshold ($)'}
            </label>
            <input value={threshold} onChange={e => setThreshold(e.target.value)} type="number" step="any" placeholder={condition.includes('pct') ? '5' : '150.00'} style={inputStyle} />
          </div>
          <button type="submit" className="btn-primary" style={{ padding: '6px 12px', fontSize: 11, marginTop: 4 }}>
            Create Alert
          </button>
        </form>
      </div>
    </div>
  );
});
AlertConfigModal.displayName = 'AlertConfigModal';
export default AlertConfigModal;
