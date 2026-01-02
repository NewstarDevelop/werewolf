import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet, Navigate } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";

// 路由懒加载，减少主包体积
const RoomLobby = lazy(() => import("./pages/RoomLobby"));
const RoomWaiting = lazy(() => import("./pages/RoomWaiting"));
const GamePage = lazy(() => import("./pages/GamePage"));
const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
const RegisterPage = lazy(() => import("./pages/auth/RegisterPage"));
const OAuthCallback = lazy(() => import("./pages/auth/OAuthCallback"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
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

// C-H1 FIX: Use English comment to avoid encoding issues
// Loading fallback component
const LoadingFallback = () => (
  <div className="flex items-center justify-center h-screen bg-black">
    <div className="text-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-4"></div>
      <p className="text-muted-foreground">Loading...</p>
    </div>
  </div>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ErrorBoundary>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AuthProvider>
            <Suspense fallback={<LoadingFallback />}>
              <Routes>
                {/* Public Auth routes */}
                <Route path="/auth/login" element={<LoginPage />} />
                <Route path="/auth/register" element={<RegisterPage />} />
                <Route path="/auth/callback" element={<OAuthCallback />} />

                {/* Protected routes - using Outlet to reduce duplication */}
                <Route element={<ProtectedRoute><Outlet /></ProtectedRoute>}>
                  <Route path="/" element={<Navigate to="/lobby" replace />} />
                  <Route path="/lobby" element={<RoomLobby />} />
                  <Route path="/room/:roomId/waiting" element={<RoomWaiting />} />
                  <Route path="/game/:gameId" element={<GamePage />} />
                  <Route path="/profile" element={<ProfilePage />} />
                </Route>

                {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </AuthProvider>
        </BrowserRouter>
      </TooltipProvider>
    </ErrorBoundary>
  </QueryClientProvider>
);

export default App;
