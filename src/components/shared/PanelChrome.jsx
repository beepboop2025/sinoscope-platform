import { memo } from 'react';
import { Minus, Maximize2, X } from 'lucide-react';

const PanelChrome = memo(({ title, icon: Icon, iconColor = 'var(--text-3)', children, onClose, className = '' }) => (
  <div className={`panel ${className}`}>
    <div className="panel-titlebar">
      {Icon && <Icon size={12} color={iconColor} />}
      <span className="panel-title">{title}</span>
      {onClose && (
        <button className="panel-btn" onClick={onClose}><X size={10} /></button>
      )}
    </div>
    <div className="panel-body">
      {children}
    </div>
  </div>
));
PanelChrome.displayName = "PanelChrome";
export default PanelChrome;
