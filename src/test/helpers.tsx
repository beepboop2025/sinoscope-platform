import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import { ThemeProvider } from '../components/shared/ThemeProvider';
import { ToastProvider } from '../components/shared/Toast';
import type { ReactElement, ReactNode } from 'react';

export function renderWithProviders(ui: ReactElement, options: RenderOptions = {}): RenderResult {
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <ThemeProvider>
        <ToastProvider>
          {children}
        </ToastProvider>
      </ThemeProvider>
    );
  }
  return render(ui, { wrapper: Wrapper, ...options });
}

export { render };
export { default as userEvent } from '@testing-library/user-event';
