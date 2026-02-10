import { createContext, useContext, useCallback, type ReactElement, type ReactNode } from 'react';
import { Toaster, toast as sonnerToast } from 'sonner';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastContextValue {
  addToast: (message: string, type?: ToastType, duration?: number) => string | number;
}

const ToastContext = createContext<ToastContextValue | null>(null);

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps): ReactElement {
  const addToast = useCallback((message: string, type: ToastType = 'info', duration: number = 4000): string | number => {
    switch (type) {
      case 'success':
        return sonnerToast.success(message, { duration });
      case 'error':
        return sonnerToast.error(message, { duration });
      case 'warning':
        return sonnerToast.warning(message, { duration });
      case 'info':
      default:
        return sonnerToast.info(message, { duration });
    }
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'var(--glass-bg-heavy, rgba(20,20,30,0.92))',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid var(--glass-border, rgba(255,255,255,0.08))',
            color: 'var(--text-1)',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
          },
        }}
        richColors
        closeButton
      />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
