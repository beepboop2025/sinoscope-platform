import { createContext, useContext, useState, useCallback, useEffect, memo } from "react";
import { CheckCircle, AlertTriangle, AlertCircle, X } from "lucide-react";

const ToastContext = createContext(null);

const ICONS = { success: CheckCircle, error: AlertTriangle, warning: AlertCircle, info: AlertCircle };
const COLORS = { success: "var(--green)", error: "var(--red)", warning: "var(--amber)", info: "var(--cyan)" };

let toastId = 0;

const ToastItem = memo(({ toast, onDismiss }) => {
  const Icon = ICONS[toast.type] || ICONS.info;
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), toast.duration || 4000);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div className={`toast ${toast.type}`} role="alert">
      <Icon size={16} color={COLORS[toast.type]} />
      <span style={{ flex: 1 }}>{toast.message}</span>
      <button onClick={() => onDismiss(toast.id)} style={{ background: "none", border: "none", cursor: "pointer", padding: 2 }}>
        <X size={12} color="var(--text-3)" />
      </button>
    </div>
  );
});
ToastItem.displayName = "ToastItem";

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = "info", duration = 4000) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message, type, duration }].slice(-5));
    return id;
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="toast-container" aria-live="polite">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={dismissToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
