export const TIMEZONES = {
  beijing: { label: 'Beijing', tz: 'Asia/Shanghai', abbr: 'CST' },
  nyc: { label: 'New York', tz: 'America/New_York', abbr: 'ET' },
  london: { label: 'London', tz: 'Europe/London', abbr: 'GMT' },
  mumbai: { label: 'Mumbai', tz: 'Asia/Kolkata', abbr: 'IST' },
};

export const getTimeInZone = (tz) => {
  return new Date().toLocaleTimeString('en-US', {
    timeZone: tz,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
};

export const isMarketOpen = (exchange) => {
  const now = new Date();
  const configs = {
    NYSE: { tz: 'America/New_York', open: 9.5, close: 16 },
    SSE: { tz: 'Asia/Shanghai', open: 9.5, close: 15 },
    LSE: { tz: 'Europe/London', open: 8, close: 16.5 },
    NSE: { tz: 'Asia/Kolkata', open: 9.25, close: 15.5 },
    HKEX: { tz: 'Asia/Hong_Kong', open: 9.5, close: 16 },
  };
  const cfg = configs[exchange];
  if (!cfg) return true;
  const localStr = now.toLocaleString('en-US', { timeZone: cfg.tz });
  const local = new Date(localStr);
  const day = local.getDay();
  if (day === 0 || day === 6) return false;
  const hour = local.getHours() + local.getMinutes() / 60;
  return hour >= cfg.open && hour < cfg.close;
};
