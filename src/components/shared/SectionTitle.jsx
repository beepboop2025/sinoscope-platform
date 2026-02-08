import { memo } from "react";
const SectionTitle = memo(({ icon: Icon, title, subtitle, color = "var(--cyan)", badge, right }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
        {Icon && <Icon size={15} color={color} />} {title}
        {badge && <span className="badge mono" style={{ background: `${color}18`, color }}>{badge}</span>}
      </h3>
      {subtitle && <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 3 }}>{subtitle}</p>}
    </div>
    {right}
  </div>
));
SectionTitle.displayName = "SectionTitle";
export default SectionTitle;
