import { memo, useState, useEffect, useRef } from 'react';
import { Share2 } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';

const PanelNetwork = memo(({ pairs = [], symbols = [] }) => {
  const svgRef = useRef(null);
  const [nodes, setNodes] = useState([]);
  const [links, setLinks] = useState([]);

  useEffect(() => {
    if (symbols.length === 0) return;

    const cx = 200, cy = 150;
    const r = 100;
    const newNodes = symbols.map((s, i) => {
      const angle = (2 * Math.PI * i) / symbols.length - Math.PI / 2;
      return { id: s, x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });

    const newLinks = pairs.map(p => ({
      source: p.symbol1,
      target: p.symbol2,
      value: p.correlation,
      color: p.correlation > 0 ? 'var(--green)' : 'var(--red)',
      width: Math.abs(p.correlation) * 3,
    }));

    setNodes(newNodes);
    setLinks(newLinks);
  }, [pairs, symbols]);

  if (symbols.length === 0) {
    return (
      <PanelChrome title="Network Graph" icon={Share2} iconColor="var(--blue)">
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>
          Collecting data for network visualization...
        </div>
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="Correlation Network" icon={Share2} iconColor="var(--blue)">
      <svg ref={svgRef} width="100%" height="100%" viewBox="0 0 400 300" style={{ minHeight: 250 }}>
        {links.map((l, i) => {
          const s = nodes.find(n => n.id === l.source);
          const t = nodes.find(n => n.id === l.target);
          if (!s || !t) return null;
          return (
            <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke={l.color} strokeWidth={l.width} opacity={0.5} />
          );
        })}
        {nodes.map(n => (
          <g key={n.id}>
            <circle cx={n.x} cy={n.y} r={18} fill="var(--bg-3)" stroke="var(--border-2)" strokeWidth={1.5} />
            <text x={n.x} y={n.y + 1} textAnchor="middle" dominantBaseline="middle" fill="var(--text-1)" fontSize={8} fontWeight={600}>
              {n.id.slice(0, 4)}
            </text>
          </g>
        ))}
      </svg>
    </PanelChrome>
  );
});
PanelNetwork.displayName = "PanelNetwork";
export default PanelNetwork;
