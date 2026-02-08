import { memo } from 'react';
import { Coins } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import MiniSparkline from '../shared/MiniSparkline';
import { priceChangeColor } from '../../constants/colors';
import { formatPrice, formatVolume } from '../../utils/formatters';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

const PanelCrypto = memo(({ data }) => {
  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Crypto Markets" icon={Coins} iconColor="var(--orange)"><PanelSkeleton /></PanelChrome>;
  }

  const coins = Object.entries(data);

  return (
    <PanelChrome title="Crypto Markets" icon={Coins} iconColor="var(--orange)">
      <table className="dense-table">
        <thead>
          <tr>
            <th>Coin</th>
            <th style={{ textAlign: 'right' }}>Price</th>
            <th style={{ textAlign: 'right' }}>24h</th>
            <th style={{ textAlign: 'right' }}>MCap</th>
          </tr>
        </thead>
        <tbody>
          {coins.map(([sym, d]) => (
            <tr key={sym}>
              <td>
                <div style={{ fontWeight: 500, color: 'var(--text-1)', fontFamily: 'Outfit' }}>{sym}</div>
                {d.name && <div style={{ fontSize: 9, color: 'var(--text-4)' }}>{d.name}</div>}
              </td>
              <td style={{ textAlign: 'right' }}>${formatPrice(d.price)}</td>
              <td style={{ textAlign: 'right', color: priceChangeColor(d.changePct) }}>
                {(Number(d.changePct) || 0) >= 0 ? '+' : ''}{(Number(d.changePct) || 0).toFixed(2)}%
              </td>
              <td style={{ textAlign: 'right', color: 'var(--text-3)' }}>${formatVolume(d.marketCap)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </PanelChrome>
  );
});
PanelCrypto.displayName = "PanelCrypto";
export default PanelCrypto;
