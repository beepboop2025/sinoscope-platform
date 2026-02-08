import { memo } from "react";
const StatBox = memo(({ label, value, sub, color, icon: Icon, small }) => (
  <div style={{ background: "var(--bg-1)", borderRadius: 8, padding: small ? "10px 12px" : "14px 16px", border: "1px solid var(--border-1)" }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: small ? 4 : 8 }}>
      <span style={{ fontSize: 10, color: "var(--text-4)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
      {Icon && <Icon size={small ? 12 : 14} color={color || "var(--text-3)"} />}
    </div>
    <div className="mono" style={{ fontSize: small ? 16 : 22, fontWeight: 700, color: color || "var(--text-0)", lineHeight: 1.1 }}>{value}</div>
    {sub && <div style={{ fontSize: 10, color: "var(--text-3)", marginTop: 4 }}>{sub}</div>}
  </div>
));
StatBox.displayName = "StatBox";
export default StatBox;
