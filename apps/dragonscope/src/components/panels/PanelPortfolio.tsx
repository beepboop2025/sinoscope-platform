import { memo, useState, useCallback, type ReactElement, type FormEvent, type ChangeEvent, type KeyboardEvent } from 'react';
import { Briefcase, Plus, Trash2, TrendingUp, TrendingDown } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { usePortfolio } from '../../hooks/usePortfolio';
import { calculateHoldingPnL, calculateTotalValue, calculateAllocation } from '../../utils/portfolio';

interface Holding {
  id: string;
  symbol: string;
  quantity: number;
  avgCost: number;
  assetType: string;
}

interface Portfolio {
  id: string;
  name: string;
  holdings: Holding[];
}

interface MarketData {
  stocks?: Record<string, { price?: number }>;
  crypto?: Record<string, { price?: number }>;
  [key: string]: unknown;
}

interface AllocationEntry {
  symbol: string;
  pct: number;
}

interface AddHoldingFormProps {
  onAdd: (holding: { symbol: string; quantity: string; avgCost: string; assetType: string }) => void;
  onCancel: () => void;
}

interface AllocationBarProps {
  allocation: AllocationEntry[];
}

const COLORS = ['var(--cyan)', 'var(--purple)', 'var(--green)', 'var(--amber)', 'var(--blue)', 'var(--orange)', 'var(--pink)', 'var(--teal)'];

const AddHoldingForm = ({ onAdd, onCancel }: AddHoldingFormProps): ReactElement => {
  const [symbol, setSymbol] = useState<string>('');
  const [qty, setQty] = useState<string>('');
  const [cost, setCost] = useState<string>('');
  const [type, setType] = useState<string>('stock');

  const handleSubmit = (e: FormEvent): void => {
    e.preventDefault();
    if (!symbol || !qty || !cost) return;
    onAdd({ symbol, quantity: qty, avgCost: cost, assetType: type });
    setSymbol(''); setQty(''); setCost('');
  };

  const inputStyle = {
    background: 'var(--bg-0)', border: '1px solid var(--border-2)', borderRadius: 4,
    color: 'var(--text-1)', fontSize: 10, padding: '3px 6px', fontFamily: 'var(--font-mono)',
    outline: 'none', width: '100%',
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 4, alignItems: 'center', padding: '4px 0', flexWrap: 'wrap' }}>
      <input value={symbol} onChange={(e: ChangeEvent<HTMLInputElement>) => setSymbol(e.target.value)} placeholder="Symbol" style={{ ...inputStyle, width: 60 }} />
      <select value={type} onChange={(e: ChangeEvent<HTMLSelectElement>) => setType(e.target.value)} style={{ ...inputStyle, width: 60 }}>
        <option value="stock">Stock</option>
        <option value="crypto">Crypto</option>
      </select>
      <input value={qty} onChange={(e: ChangeEvent<HTMLInputElement>) => setQty(e.target.value)} placeholder="Qty" type="number" step="any" style={{ ...inputStyle, width: 50 }} />
      <input value={cost} onChange={(e: ChangeEvent<HTMLInputElement>) => setCost(e.target.value)} placeholder="Avg Cost" type="number" step="any" style={{ ...inputStyle, width: 70 }} />
      <button type="submit" className="btn-primary" style={{ padding: '3px 8px', fontSize: 9 }}>Add</button>
      <button type="button" className="btn-ghost" onClick={onCancel} style={{ padding: '3px 6px', fontSize: 9 }}>Cancel</button>
    </form>
  );
};

const AllocationBar = ({ allocation }: AllocationBarProps): ReactElement | null => {
  if (!allocation || allocation.length === 0) return null;
  return (
    <div style={{ display: 'flex', borderRadius: 4, overflow: 'hidden', height: 6, marginBottom: 6 }}>
      {allocation.map((a, i) => (
        <div
          key={a.symbol}
          title={`${a.symbol}: ${a.pct.toFixed(1)}%`}
          style={{ width: `${a.pct}%`, background: COLORS[i % COLORS.length], minWidth: 2 }}
        />
      ))}
    </div>
  );
};

const PanelPortfolio = memo(({ data: marketData }: { data?: MarketData }): ReactElement => {
  const { portfolios, activePortfolio, activeId, setActiveId, createPortfolio, deletePortfolio, addHolding, removeHolding } = usePortfolio();
  const [showAdd, setShowAdd] = useState<boolean>(false);
  const [showNewPf, setShowNewPf] = useState<boolean>(false);
  const [newPfName, setNewPfName] = useState<string>('');

  const handleCreatePortfolio = useCallback(() => {
    if (!newPfName.trim()) return;
    createPortfolio(newPfName.trim());
    setNewPfName('');
    setShowNewPf(false);
  }, [newPfName, createPortfolio]);

  const handleAddHolding = useCallback((holding: { symbol: string; quantity: string; avgCost: string; assetType: string }) => {
    if (!activeId) return;
    addHolding(activeId, holding);
    setShowAdd(false);
  }, [activeId, addHolding]);

  const holdings = (activePortfolio as Portfolio | undefined)?.holdings || [];
  const typedHoldings = holdings as unknown as { symbol: string; quantity: number; avgCost: number; assetType: 'stock' | 'crypto' | 'etf' }[];
  const totals = calculateTotalValue(typedHoldings, marketData as never) as { totalValue: number; totalPnL: number; totalPnLPct: number };
  const allocation = calculateAllocation(typedHoldings, marketData as never) as AllocationEntry[];

  return (
    <PanelChrome title="Portfolio" icon={Briefcase} iconColor="var(--green)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Portfolio selector */}
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {(portfolios as Portfolio[]).length > 0 ? (
            <select
              value={activeId || ''}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => setActiveId(e.target.value)}
              style={{
                background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 4,
                color: 'var(--text-1)', fontSize: 10, padding: '2px 4px', fontFamily: 'var(--font-mono)', flex: 1,
              }}
            >
              {(portfolios as Portfolio[]).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          ) : (
            <span style={{ fontSize: 10, color: 'var(--text-3)', flex: 1 }}>No portfolios</span>
          )}
          <button className="btn-ghost" onClick={() => setShowNewPf(true)} style={{ padding: '2px 5px', fontSize: 9 }} title="New portfolio">
            <Plus size={10} />
          </button>
          {activePortfolio && (
            <button className="btn-ghost" onClick={() => deletePortfolio(activeId || '')} style={{ padding: '2px 5px', fontSize: 9, color: 'var(--text-4)' }} title="Delete portfolio">
              <Trash2 size={10} />
            </button>
          )}
        </div>

        {/* New portfolio form */}
        {showNewPf && (
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              autoFocus value={newPfName} onChange={(e: ChangeEvent<HTMLInputElement>) => setNewPfName(e.target.value)}
              onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => { if (e.key === 'Enter') handleCreatePortfolio(); if (e.key === 'Escape') setShowNewPf(false); }}
              placeholder="Portfolio name..."
              style={{ flex: 1, fontSize: 10, padding: '2px 6px', background: 'var(--bg-0)', color: 'var(--text-1)', border: '1px solid var(--border-2)', borderRadius: 3, fontFamily: 'var(--font-mono)', outline: 'none' }}
            />
            <button className="btn-primary" onClick={handleCreatePortfolio} style={{ padding: '2px 8px', fontSize: 9 }}>Create</button>
          </div>
        )}

        {/* Summary */}
        {holdings.length > 0 && (
          <div style={{ display: 'flex', gap: 12, padding: '4px 0', borderBottom: '1px solid var(--border-1)' }}>
            <div>
              <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>Value</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>
                ${totals.totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>P&L</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: totals.totalPnL >= 0 ? 'var(--green)' : 'var(--red)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 4 }}>
                {totals.totalPnL >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                {totals.totalPnL >= 0 ? '+' : ''}{totals.totalPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                <span style={{ fontSize: 10 }}>({totals.totalPnLPct >= 0 ? '+' : ''}{totals.totalPnLPct.toFixed(2)}%)</span>
              </div>
            </div>
          </div>
        )}

        {/* Allocation bar */}
        <AllocationBar allocation={allocation} />

        {/* Add holding button/form */}
        {activePortfolio && !showAdd && (
          <button className="btn-ghost" onClick={() => setShowAdd(true)} style={{ padding: '3px 8px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 4, alignSelf: 'flex-start' }}>
            <Plus size={10} /> Add Holding
          </button>
        )}
        {showAdd && <AddHoldingForm onAdd={handleAddHolding} onCancel={() => setShowAdd(false)} />}

        {/* Holdings table */}
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {holdings.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-3)', fontSize: 11 }}>
              {activePortfolio ? 'No holdings yet. Add your first position above.' : 'Create a portfolio to get started.'}
            </div>
          ) : (
            <table className="dense-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Symbol</th>
                  <th style={{ textAlign: 'right' }}>Qty</th>
                  <th style={{ textAlign: 'right' }}>Avg Cost</th>
                  <th style={{ textAlign: 'right' }}>Value</th>
                  <th style={{ textAlign: 'right' }}>P&L</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {holdings.map(h => {
                  const price = getHoldingPrice(h, marketData);
                  const { currentValue, pnl, pnlPct } = calculateHoldingPnL(h as unknown as { symbol: string; quantity: number; avgCost: number; assetType: 'stock' | 'crypto' | 'etf' }, price) as { currentValue: number; pnl: number; pnlPct: number };
                  return (
                    <tr key={h.id}>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{h.symbol}</span>
                        <span style={{ fontSize: 8, color: 'var(--text-4)', marginLeft: 4 }}>{h.assetType}</span>
                      </td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{h.quantity}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>${h.avgCost.toFixed(2)}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>${currentValue.toFixed(2)}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                        {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%)
                      </td>
                      <td>
                        <button className="btn-ghost" onClick={() => removeHolding(activeId || '', h.id)} style={{ padding: '1px 3px' }}>
                          <Trash2 size={9} color="var(--text-4)" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelPortfolio.displayName = 'PanelPortfolio';

function getHoldingPrice(holding: Holding, marketData?: MarketData): number {
  if (!marketData) return 0;
  if (holding.assetType === 'crypto') {
    const d = marketData.crypto?.[holding.symbol] || marketData.crypto?.[holding.symbol + 'USDT'];
    return d?.price || 0;
  }
  return marketData.stocks?.[holding.symbol]?.price || 0;
}

export default PanelPortfolio;
