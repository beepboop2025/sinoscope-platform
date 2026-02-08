import { memo } from "react";
const MiniSparkline = memo(({ data, color = "#06d6e0", height = 30, width = 80 }) => {
  if (!Array.isArray(data) || data.length === 0) return null;
  if (data.length === 1) {
    const y = height / 2;
    return (
      <svg width={width} height={height} style={{ display: "block" }}>
        <line x1="0" y1={y} x2={width} y2={y} stroke={color} strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * (height - 4) - 2}`).join(" ");
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
});
MiniSparkline.displayName = "MiniSparkline";
export default MiniSparkline;
