import { memo, type ReactElement, type CSSProperties } from "react";

interface SkeletonBoxProps {
  width?: string | number;
  height?: string | number;
  style?: CSSProperties;
}

const SkeletonBox = ({ width = "100%", height = 20, style }: SkeletonBoxProps): ReactElement => (
  <div className="skeleton" style={{ width, height, ...style }} />
);

export const CardSkeleton = memo((): ReactElement => (
  <div className="card" style={{ padding: 18 }}>
    <SkeletonBox height={14} width="40%" style={{ marginBottom: 12 }} />
    <SkeletonBox height={10} width="60%" style={{ marginBottom: 16 }} />
    <SkeletonBox height={160} />
  </div>
));
CardSkeleton.displayName = "CardSkeleton";

export const PanelSkeleton = memo((): ReactElement => (
  <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
    <SkeletonBox height={12} width="30%" />
    <SkeletonBox height={24} width="50%" />
    <SkeletonBox height={120} />
    <SkeletonBox height={10} width="40%" />
  </div>
));
PanelSkeleton.displayName = "PanelSkeleton";
