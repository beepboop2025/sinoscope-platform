import { useEffect, useState, useCallback } from 'react';
import type { ChartOptions, DeepPartial } from 'lightweight-charts';

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function buildTheme(): DeepPartial<ChartOptions> {
  const bg = getCSSVar('--bg-1') || '#0a0f1a';
  const text = getCSSVar('--text-3') || '#64748b';
  const border = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';
  const grid = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';
  const crosshair = getCSSVar('--cyan') || '#06d6e0';

  return {
    layout: {
      background: { color: bg },
      textColor: text,
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: 10,
    },
    grid: {
      vertLines: { color: grid },
      horzLines: { color: grid },
    },
    crosshair: {
      mode: 0,
      vertLine: { color: crosshair, width: 1, style: 2 },
      horzLine: { color: crosshair, width: 1, style: 2 },
    },
    rightPriceScale: {
      borderColor: border,
    },
    timeScale: {
      borderColor: border,
    },
  };
}

export function useChartTheme(): DeepPartial<ChartOptions> {
  const [theme, setTheme] = useState<DeepPartial<ChartOptions>>(buildTheme);

  const updateTheme = useCallback(() => {
    setTheme(buildTheme());
  }, []);

  useEffect(() => {
    // Watch for data-theme changes
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.attributeName === 'data-theme') {
          updateTheme();
          break;
        }
      }
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    return () => observer.disconnect();
  }, [updateTheme]);

  return theme;
}

export function getAccentColors() {
  return {
    green: getCSSVar('--green') || '#00DC82',
    red: getCSSVar('--red') || '#FF4458',
    cyan: getCSSVar('--cyan') || '#06d6e0',
    purple: getCSSVar('--purple') || '#8B5CF6',
    blue: getCSSVar('--blue') || '#3B82F6',
    amber: getCSSVar('--amber') || '#F59E0B',
  };
}
