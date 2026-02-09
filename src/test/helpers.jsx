import { render } from '@testing-library/react';
import { ThemeProvider } from '../components/shared/ThemeProvider';
import { ToastProvider } from '../components/shared/Toast';

export function renderWithProviders(ui, options = {}) {
  function Wrapper({ children }) {
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
