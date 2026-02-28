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

export const ChartSkeleton = memo(({ height = 200 }: { height?: number }): ReactElement => (
  <div className="skeleton-chart" style={{ height, width: '100%' }}>
    <div style={{ position: 'absolute', bottom: 8, left: 35, right: 10, display: 'flex', justifyContent: 'space-between' }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ width: 24, height: 8 }} />
      ))}
    </div>
    <div style={{ position: 'absolute', top: 10, left: 5, bottom: 24, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ width: 28, height: 8 }} />
      ))}
    </div>
  </div>
));
ChartSkeleton.displayName = "ChartSkeleton";
