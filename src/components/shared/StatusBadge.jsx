import { memo } from "react";
const STATUS_CONFIG = {
  live: { bg: "rgba(16,185,129,0.12)", color: "var(--green)" },
  connected: { bg: "rgba(16,185,129,0.12)", color: "var(--green)" },
  delayed: { bg: "rgba(245,158,11,0.12)", color: "var(--amber)" },
  disconnected: { bg: "rgba(239,68,68,0.12)", color: "var(--red)" },
  error: { bg: "rgba(239,68,68,0.14)", color: "var(--red)" },
  mock: { bg: "rgba(59,130,246,0.1)", color: "var(--blue)" },
  loading: { bg: "rgba(59,130,246,0.1)", color: "var(--blue)" },
  open: { bg: "rgba(16,185,129,0.12)", color: "var(--green)" },
  closed: { bg: "rgba(100,116,139,0.12)", color: "var(--text-3)" },
  high: { bg: "rgba(239,68,68,0.14)", color: "var(--red)" },
  medium: { bg: "rgba(245,158,11,0.12)", color: "var(--amber)" },
  low: { bg: "rgba(16,185,129,0.12)", color: "var(--green)" },
};
const StatusBadge = memo(({ status }) => {
  const c = STATUS_CONFIG[status] || STATUS_CONFIG.loading;
  return <span className="badge mono" style={{ background: c.bg, color: c.color }}>{status}</span>;
});
StatusBadge.displayName = "StatusBadge";
export default StatusBadge;
