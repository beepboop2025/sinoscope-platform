import { createContext, useContext, useState, useCallback, useEffect, memo, type ReactElement, type ReactNode } from "react";
import { CheckCircle, AlertTriangle, AlertCircle, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: number;
  message: string;
  type: ToastType;
  duration: number;
}

interface ToastContextValue {
  addToast: (message: string, type?: ToastType, duration?: number) => number;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const ICONS: Record<ToastType, LucideIcon> = { success: CheckCircle, error: AlertTriangle, warning: AlertCircle, info: AlertCircle };
const COLORS: Record<ToastType, string> = { success: "var(--green)", error: "var(--red)", warning: "var(--amber)", info: "var(--cyan)" };

let toastId = 0;

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: number) => void;
}

const ToastItem = memo(({ toast, onDismiss }: ToastItemProps): ReactElement => {
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

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps): ReactElement {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: ToastType = "info", duration: number = 4000): number => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message, type, duration }].slice(-5));
    return id;
  }, []);

  const dismissToast = useCallback((id: number) => {
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

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
