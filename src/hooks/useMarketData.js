import { useState, useEffect, useRef } from 'react';

export function useMarketData(engine) {
  const [data, setData] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (!engine) return;

    const unsub = engine.subscribe((snapshot) => {
      setData(snapshot);
    });

    setData(engine.getSnapshot());

    return unsub;
  }, [engine]);

  return data;
}
