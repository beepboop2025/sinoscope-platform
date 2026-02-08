import { memo } from "react";

const SkeletonBox = ({ width = "100%", height = 20, style }) => (
  <div className="skeleton" style={{ width, height, ...style }} />
);

export const CardSkeleton = memo(() => (
  <div className="card" style={{ padding: 18 }}>
    <SkeletonBox height={14} width="40%" style={{ marginBottom: 12 }} />
    <SkeletonBox height={10} width="60%" style={{ marginBottom: 16 }} />
    <SkeletonBox height={160} />
  </div>
));
CardSkeleton.displayName = "CardSkeleton";

export const PanelSkeleton = memo(() => (
  <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
    <SkeletonBox height={12} width="30%" />
    <SkeletonBox height={24} width="50%" />
    <SkeletonBox height={120} />
    <SkeletonBox height={10} width="40%" />
  </div>
));
PanelSkeleton.displayName = "PanelSkeleton";
