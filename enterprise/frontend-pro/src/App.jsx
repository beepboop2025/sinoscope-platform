import React, { useEffect } from 'react';
import TerminalLayout from './components/TerminalLayout';
import './styles/index.css';

/**
 * DragonScope Enterprise Terminal
 * Bloomberg-grade professional trading interface
 */
const App = () => {
  // Load Lightweight Charts from CDN
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js';
    script.async = true;
    script.onload = () => {
      console.log('Lightweight Charts loaded');
    };
    document.body.appendChild(script);

    return () => {
      document.body.removeChild(script);
    };
  }, []);

  return (
    <div className="h-screen w-screen overflow-hidden bg-slate-950 text-slate-200">
      <TerminalLayout />
    </div>
  );
};

export default App;
