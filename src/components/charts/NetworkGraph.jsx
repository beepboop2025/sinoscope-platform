import { memo, useMemo, useState, useCallback } from 'react';

const NetworkGraph = memo(({ nodes = [], links = [], width = 400, height = 300, nodeRadius = 18, onNodeClick }) => {
  const [hoveredNode, setHoveredNode] = useState(null);

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

  // Set of node IDs connected to the hovered node
  const connectedIds = useMemo(() => {
    if (!hoveredNode) return null;
    const ids = new Set([hoveredNode]);
    links.forEach(l => {
      if (l.source === hoveredNode) ids.add(l.target);
      if (l.target === hoveredNode) ids.add(l.source);
    });
    return ids;
  }, [hoveredNode, links]);

  const handleNodeEnter = useCallback((id) => setHoveredNode(id), []);
  const handleNodeLeave = useCallback(() => setHoveredNode(null), []);
  const handleNodeClick = useCallback((node) => {
    if (onNodeClick) onNodeClick(node);
  }, [onNodeClick]);

  const isLinkConnected = (l) => {
    if (!connectedIds) return true;
    return connectedIds.has(l.source) && connectedIds.has(l.target);
  };

  const isNodeConnected = (id) => {
    if (!connectedIds) return true;
    return connectedIds.has(id);
  };

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} style={{ minHeight: height }}>
      {positioned.links.map((l, i) => (
        <line
          key={i}
          x1={l.sx} y1={l.sy} x2={l.tx} y2={l.ty}
          stroke={l.value > 0 ? 'var(--green)' : 'var(--red)'}
          strokeWidth={Math.max(0.5, Math.abs(l.value || 0) * 3)}
          opacity={isLinkConnected(l) ? 0.6 : 0.1}
          style={{ transition: 'opacity 0.15s' }}
        />
      ))}
      {positioned.nodes.map(n => {
        const connected = isNodeConnected(n.id);
        const isHovered = hoveredNode === n.id;
        return (
          <g
            key={n.id}
            style={{ cursor: 'pointer', transition: 'opacity 0.15s' }}
            opacity={connected ? 1 : 0.2}
            onMouseEnter={() => handleNodeEnter(n.id)}
            onMouseLeave={handleNodeLeave}
            onClick={() => handleNodeClick(n)}
          >
            <circle
              cx={n.x} cy={n.y} r={nodeRadius}
              fill={isHovered ? 'var(--bg-hover)' : 'var(--bg-3)'}
              stroke={isHovered ? 'var(--cyan)' : 'var(--border-2)'}
              strokeWidth={isHovered ? 2 : 1.5}
            />
            <text x={n.x} y={n.y + 1} textAnchor="middle" dominantBaseline="middle" fill="var(--text-1)" fontSize={8} fontWeight={600}>
              {(n.label || n.id).slice(0, 4)}
            </text>
          </g>
        );
      })}
    </svg>
  );
});
NetworkGraph.displayName = 'NetworkGraph';
export default NetworkGraph;
