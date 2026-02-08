import { memo } from 'react';

const TickerItem = ({ symbol, price, change }) => {
  const isUp = (Number(change) || 0) >= 0;
  return (
    <span className="ticker-item">
      <span className="ticker-symbol">{symbol}</span>
      <span className="ticker-price">{(Number(price) || 0).toFixed(price > 100 ? 2 : 4)}</span>
      <span className={`ticker-change ${isUp ? 'up' : 'down'}`}>
        {isUp ? '+' : ''}{(Number(change) || 0).toFixed(2)}%
      </span>
    </span>
  );
};

const RateTicker = memo(({ forex = {}, crypto = {}, stocks = {} }) => {
  const items = [];

  for (const [pair, data] of Object.entries(forex)) {
    if (items.length >= 20) break;
    items.push({ symbol: pair, price: data.price, change: data.changePct });
  }
  for (const [sym, data] of Object.entries(crypto)) {
    if (items.length >= 28) break;
    items.push({ symbol: sym, price: data.price, change: data.changePct });
  }
  for (const [sym, data] of Object.entries(stocks)) {
    if (items.length >= 36) break;
    items.push({ symbol: sym, price: data.price, change: data.changePct });
  }

  if (items.length === 0) return null;

  const doubled = [...items, ...items];

  return (
    <div className="ticker-bar">
      <div className="ticker-scroll">
        {doubled.map((item, i) => (
          <TickerItem key={`${item.symbol}_${i}`} {...item} />
        ))}
      </div>
    </div>
  );
});
RateTicker.displayName = "RateTicker";
export default RateTicker;
