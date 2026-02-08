/**
 * PanelCNYTracker - CNY/CNH Onshore vs Offshore Spread
 * Tracks the difference between onshore (CNY) and offshore (CNH) yuan
 */
import { useState, useEffect, useMemo } from 'react';
import { ArrowLeftRight, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';
import { ChinaAPI } from '../../../services/api/chinaApi';
import { CNY_MARKET } from '../../../constants/china';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, ReferenceLine } from 'recharts';

export default function PanelCNYTracker() {
  const [fxData, setFxData] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      const data = await ChinaAPI.fetchCNYCNHRates();
      setFxData(data);
      
      // Add to history (keep last 50 points)
      setHistory(prev => {
        const newPoint = {
          time: new Date().toLocaleTimeString(),
          cny: data.cnyUsd,
          cnh: data.cnhUsd,
          spread: data.cnhUsd - data.cnyUsd,
        };
        return [...prev.slice(-49), newPoint];
      });
      
      setLoading(false);
    }

    fetchData();
    const interval = setInterval(fetchData, 30000); // Every 30s
    return () => clearInterval(interval);
  }, []);

  const spread = useMemo(() => {
    if (!fxData) return 0;
    return fxData.cnhUsd - fxData.cnyUsd;
  }, [fxData]);

  const spreadBps = useMemo(() => spread * 10000, [spread]);

  const getSpreadInterpretation = () => {
    if (spreadBps > 100) return {
      text: 'Offshore yuan weaker - capital outflow pressure',
      color: 'var(--red)',
      level: 'high',
    };
    if (spreadBps < -100) return {
      text: 'Offshore yuan stronger - inflow demand',
      color: 'var(--green)',
      level: 'high',
    };
    return {
      text: 'Normal spread range',
      color: 'var(--text-2)',
      level: 'normal',
    };
  };

  const interpretation = getSpreadInterpretation();

  if (loading && !fxData) {
    return (
      <div className="panel-content" style={{ padding: 20 }}>
        <div style={{ color: 'var(--text-2)' }}>Loading FX data...</div>
      </div>
    );
  }

  return (
    <div className="panel-content" style={{ padding: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <ArrowLeftRight size={18} color="var(--cyan)" />
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>CNY/CNH Tracker</h3>
      </div>

      {/* Rates Display */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
        {/* Onshore CNY */}
        <div
          style={{
            padding: 12,
            background: 'var(--surface-2)',
            borderRadius: 8,
            border: '1px solid var(--divider)',
          }}
        >
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
            {CNY_MARKET.onshore.symbol} - {CNY_MARKET.onshore.name}
          </div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>
            {fxData?.cnyUsd?.toFixed(4) || 'N/A'}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>
            {CNY_MARKET.onshore.exchange}
          </div>
        </div>

        {/* Offshore CNH */}
        <div
          style={{
            padding: 12,
            background: 'var(--surface-2)',
            borderRadius: 8,
            border: '1px solid var(--divider)',
          }}
        >
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
            {CNY_MARKET.offshore.symbol} - {CNY_MARKET.offshore.name}
          </div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>
            {fxData?.cnhUsd?.toFixed(4) || 'N/A'}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>
            {CNY_MARKET.offshore.exchange}
          </div>
        </div>
      </div>

      {/* Spread Alert */}
      <div
        style={{
          padding: 12,
          background: interpretation.level === 'high' ? 'var(--red-alpha)' : 'var(--surface-1)',
          borderRadius: 8,
          border: `1px solid ${interpretation.level === 'high' ? 'var(--red)' : 'var(--divider)'}`,
          marginBottom: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          {Math.abs(spreadBps) > 50 ? (
            <AlertCircle size={14} color={interpretation.color} />
          ) : null}
          <span style={{ fontSize: 12, fontWeight: 500, color: interpretation.color }}>
            Spread: {spreadBps > 0 ? '+' : ''}{spreadBps.toFixed(0)} bps
          </span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-2)' }}>
          {interpretation.text}
        </div>
      </div>

      {/* Spread Chart */}
      {history.length > 1 && (
        <div style={{ height: 150, marginTop: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 8 }}>
            Spread History (CNH - CNY)
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history}>
              <XAxis dataKey="time" hide />
              <YAxis domain={['auto', 'auto']} tickFormatter={(v) => `${(v * 10000).toFixed(0)}bps`} />
              <ReferenceLine y={0} stroke="var(--divider)" strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="spread"
                stroke={spread >= 0 ? 'var(--red)' : 'var(--green)'}
                strokeWidth={2}
                dot={false}
                animationDuration={300}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Explanation */}
      <div
        style={{
          marginTop: 12,
          padding: 10,
          background: 'var(--surface-1)',
          borderRadius: 6,
          fontSize: 11,
          color: 'var(--text-3)',
          lineHeight: 1.5,
        }}
      >
        <strong>CNY vs CNH:</strong> {CNY_MARKET.spread.description}
        <br />
        Normal range: {CNY_MARKET.spread.normalRange}
      </div>
    </div>
  );
}
