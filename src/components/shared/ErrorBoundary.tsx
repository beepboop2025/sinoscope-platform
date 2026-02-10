import { Component, type ReactNode, type ErrorInfo } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

interface ErrorBoundaryProps {
  label?: string;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="card" style={{ textAlign: "center", padding: "40px 24px", margin: "18px 0" }}>
          <AlertTriangle size={32} color="var(--amber)" style={{ marginBottom: 12 }} />
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8, color: "var(--text-1)" }}>
            {this.props.label || "Something went wrong"}
          </h3>
          <p style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 16, maxWidth: 400, margin: "0 auto 16px" }}>
            {this.state.error?.message || "An unexpected error occurred."}
          </p>
          <button className="btn-ghost" onClick={this.handleRetry} style={{ margin: "0 auto" }}>
            <RotateCcw size={12} /> Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
