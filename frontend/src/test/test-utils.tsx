/* eslint-disable react-refresh/only-export-components */
/**
 * Test Utilities
 *
 * T-01: Provides wrapper components and utilities for testing.
 * Includes all necessary providers for rendering components.
 */
import React, { ReactElement, ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@/components/theme-provider';

// Create a fresh QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// Mock AuthContext for testing
const mockAuthContext = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: async () => {},
  logout: async () => {},
  register: async () => {},
  refreshUser: async () => {},
};

// Mock AuthProvider that doesn't make real API calls
function MockAuthProvider({ children }: { children: ReactNode }) {
  const AuthContext = React.createContext(mockAuthContext);
  return (
    <AuthContext.Provider value={mockAuthContext}>
      {children}
    </AuthContext.Provider>
  );
}

// Mock SoundProvider
function MockSoundProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

interface AllTheProvidersProps {
  children: ReactNode;
}

/**
 * Wrapper component with all providers for testing.
 * Use this when you need full app context.
 */
function AllTheProviders({ children }: AllTheProvidersProps) {
  const queryClient = createTestQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="dark"
        disableTransitionOnChange
      >
        <BrowserRouter>
          <MockAuthProvider>
            <MockSoundProvider>
              {children}
            </MockSoundProvider>
          </MockAuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

/**
 * Minimal wrapper with just QueryClient and Router.
 * Use this for simpler component tests.
 */
function MinimalProviders({ children }: AllTheProvidersProps) {
  const queryClient = createTestQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </QueryClientProvider>
  );
}

/**
 * Custom render function that wraps component with all providers.
 */
function customRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllTheProviders, ...options });
}

/**
 * Minimal render with just QueryClient and Router.
 */
function minimalRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: MinimalProviders, ...options });
}

// Re-export everything from testing-library
export * from '@testing-library/react';
export { userEvent } from '@testing-library/user-event';

// Export custom render functions
export { customRender as render, minimalRender };

// Export utilities
export { createTestQueryClient, AllTheProviders, MinimalProviders };
