import { Suspense } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import "./i18n/config";  // Initialize i18n before app starts
import { initSentry } from "./lib/sentry";
import { GlobalErrorBoundary } from "./components/GlobalErrorBoundary";

initSentry();

createRoot(document.getElementById("root")!).render(
  <GlobalErrorBoundary>
    <Suspense fallback={<div className="flex items-center justify-center h-screen bg-background text-foreground">Loading...</div>}>
      <App />
    </Suspense>
  </GlobalErrorBoundary>
);
