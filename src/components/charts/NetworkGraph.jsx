import { memo, useMemo } from 'react';

const NetworkGraph = memo(({ nodes = [], links = [], width = 400, height = 300, nodeRadius = 18 }) => {
  const positioned = useMemo(() => {
    if (nodes.length === 0) return { nodes: [], links: [] };
    const cx = width / 2, cy = height / 2;
    const r = Math.min(cx, cy) - nodeRadius - 20;
    const posNodes = nodes.map((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
      return { ...n, x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });
    const posLinks = links.map(l => {
      const s = posNodes.find(n => n.id === l.source);
      const t = posNodes.find(n => n.id === l.target);
      return { ...l, sx: s?.x, sy: s?.y, tx: t?.x, ty: t?.y };
    }).filter(l => l.sx != null && l.tx != null);
    return { nodes: posNodes, links: posLinks };
  }, [nodes, links, width, height, nodeRadius]);

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} style={{ minHeight: height }}>
      {positioned.links.map((l, i) => (
        <line
          key={i}
          x1={l.sx} y1={l.sy} x2={l.tx} y2={l.ty}
          stroke={l.value > 0 ? 'var(--green)' : 'var(--red)'}
          strokeWidth={Math.max(0.5, Math.abs(l.value || 0) * 3)}
          opacity={0.5}
        />
      ))}
      {positioned.nodes.map(n => (
        <g key={n.id}>
          <circle cx={n.x} cy={n.y} r={nodeRadius} fill="var(--bg-3)" stroke="var(--border-2)" strokeWidth={1.5} />
          <text x={n.x} y={n.y + 1} textAnchor="middle" dominantBaseline="middle" fill="var(--text-1)" fontSize={8} fontWeight={600}>
            {(n.label || n.id).slice(0, 4)}
          </text>
        </g>
      ))}
    </svg>
  );
});
NetworkGraph.displayName = 'NetworkGraph';
export default NetworkGraph;
