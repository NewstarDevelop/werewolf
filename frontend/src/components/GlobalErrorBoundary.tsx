import { Component, ErrorInfo, ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCcw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class GlobalErrorBoundary extends Component<Props, State> {
  public state: State = { hasError: false, error: null };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Critical System Error:", error, errorInfo);
    // Optional: Report to Sentry if lib/sentry doesn't depend on React Context
    // captureError(error);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 text-foreground">
          <Alert variant="destructive" className="max-w-md border-destructive/50">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle className="mb-2 text-lg font-semibold">
              System Error / 系统错误
            </AlertTitle>
            <AlertDescription className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Unable to load application resources. Please try refreshing the page.
                <br />
                无法加载应用资源,请尝试刷新页面。
              </p>
              {/* Display technical details in development mode */}
              {import.meta.env.DEV && (
                 <pre className="max-h-[100px] overflow-auto rounded bg-secondary p-2 text-xs font-mono">
                   {this.state.error?.message}
                 </pre>
              )}
              <div className="flex justify-center pt-2">
                <Button
                  onClick={() => window.location.reload()}
                  className="gap-2"
                  variant="default"
                >
                  <RefreshCcw className="h-4 w-4" />
                  Reload / 刷新
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        </div>
      );
    }
    return this.props.children;
  }
}
