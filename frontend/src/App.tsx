import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet, Navigate } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider } from "@/contexts/AuthContext";
import { SoundProvider } from "@/contexts/SoundContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AppLayout } from "@/layouts/AppLayout";
import { ThemeProvider } from "@/components/theme-provider";

// Lazy load pages to reduce main bundle size
const RoomLobby = lazy(() => import("./pages/RoomLobby"));
const RoomWaiting = lazy(() => import("./pages/RoomWaiting"));
const GamePage = lazy(() => import("./pages/GamePage"));
const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
const RegisterPage = lazy(() => import("./pages/auth/RegisterPage"));
const OAuthCallback = lazy(() => import("./pages/auth/OAuthCallback"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const NotFound = lazy(() => import("./pages/NotFound"));

// H1 FIX: Disable React Query retry to prevent double-retry with fetchApi
// All retry logic is handled by fetchApi (see api.ts)
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false, // Disable retry - fetchApi handles this
      staleTime: 0,
    },
  },
});

// Loading fallback component
// Note: Do NOT use useTranslation here - it may trigger Suspense before i18n is ready
const LoadingFallback = () => (
  <div className="flex items-center justify-center h-screen bg-background">
    <div className="text-center" role="status" aria-live="polite">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-4" aria-hidden="true"></div>
      <p className="text-muted-foreground">Loading...</p>
    </div>
  </div>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
      themes={["light", "dark"]}
    >
      <SoundProvider>
        <ErrorBoundary>
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <BrowserRouter>
              <AuthProvider>
                <Suspense fallback={<LoadingFallback />}>
                  <Routes>
                  {/* Public Auth routes - no sidebar */}
                  <Route path="/auth/login" element={<LoginPage />} />
                  <Route path="/auth/register" element={<RegisterPage />} />
                  <Route path="/auth/callback" element={<OAuthCallback />} />

                  {/* Protected routes with AppLayout (sidebar) */}
                  <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                    <Route index element={<Navigate to="/lobby" replace />} />
                    <Route path="/lobby" element={<RoomLobby />} />
                    <Route path="/room/:roomId/waiting" element={<RoomWaiting />} />
                    <Route path="/profile" element={<ProfilePage />} />
                    <Route path="/history" element={<HistoryPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                  </Route>

                  {/* Game page - protected but without sidebar for immersive experience */}
                  <Route element={<ProtectedRoute><Outlet /></ProtectedRoute>}>
                    <Route path="/game/:gameId" element={<GamePage />} />
                  </Route>

                  {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </AuthProvider>
          </BrowserRouter>
        </TooltipProvider>
      </ErrorBoundary>
      </SoundProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
