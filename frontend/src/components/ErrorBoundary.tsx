import { Component, type ErrorInfo, type ReactNode } from "react";

import { uiCopy } from "../copy";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("Werewolf UI error:", error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main className="app-shell">
          <div className="app-frame">
            <div className="error-fallback">
              <strong>{uiCopy.errorBoundary.title}</strong>
              <p>{uiCopy.errorBoundary.detail}</p>
              <button
                type="button"
                onClick={() => {
                  this.setState({ hasError: false });
                  window.location.reload();
                }}
              >
                {uiCopy.errorBoundary.reload}
              </button>
            </div>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
