/**
 * API Client - Core HTTP functionality
 *
 * This module provides the base HTTP client with:
 * - Automatic cookie-based authentication (credentials: 'include')
 * - Timeout handling
 * - Retry logic for idempotent requests
 * - Unified error handling
 *
 * Security: Uses HttpOnly cookies for authentication.
 * Do NOT manually inject Authorization headers for user auth.
 */

// Default empty string (relative path), production uses nginx proxy
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

// Timeout configuration
export const DEFAULT_TIMEOUT_MS = 10000;  // 10 seconds
export const LLM_TIMEOUT_MS = 120000;     // 2 minutes for LLM operations

/**
 * API Error class with status code and detail message.
 */
export class ApiError extends Error {
  // Optional response object for axios-style error handling compatibility
  response?: {
    status: number;
    data?: { detail?: string };
  };

  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = 'ApiError';
    // For axios compatibility
    this.response = {
      status,
      data: { detail }
    };
  }
}

/**
 * Fetch configuration options.
 */
export interface FetchOptions extends RequestInit {
  /** Custom timeout in milliseconds. Default: 10000 */
  timeout?: number;
  /** Whether to skip automatic retry on 5xx errors. Default: false */
  skipRetry?: boolean;
}

/**
 * Core fetch wrapper with retry, timeout, and error handling.
 *
 * Features:
 * - Automatic cookie-based authentication (credentials: 'include')
 * - Configurable timeout with AbortSignal support
 * - Retry logic for idempotent methods (GET/HEAD) only
 * - Unified error handling via ApiError
 *
 * Security:
 * - Endpoint must be a relative path starting with '/'
 * - Rejects absolute URLs and protocol-relative URLs ('//')
 * - Does NOT manually inject Authorization headers (uses cookies)
 *
 * @param endpoint - Relative API path (must start with '/')
 * @param options - Extended fetch options with timeout support
 * @returns Promise resolving to the parsed JSON response
 * @throws {ApiError} When the request fails or endpoint is invalid
 */
export async function fetchApi<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  // Security: Validate endpoint to prevent token leakage to external domains
  if (!endpoint.startsWith('/')) {
    throw new ApiError(400, 'Endpoint must be a relative path starting with "/"');
  }
  if (endpoint.startsWith('//')) {
    throw new ApiError(400, 'Protocol-relative URLs are not allowed');
  }

  const url = `${API_BASE_URL}${endpoint}`;
  const timeout = options.timeout ?? DEFAULT_TIMEOUT_MS;

  // Headers: Content-Type only, auth is via cookies
  const defaultHeaders: HeadersInit = {
    'Content-Type': 'application/json',
  };

  // Retry configuration: only idempotent methods
  const method = (options.method || 'GET').toUpperCase();
  const isIdempotent = ['GET', 'HEAD'].includes(method);
  const MAX_RETRIES = (isIdempotent && !options.skipRetry) ? 3 : 0;
  let retryCount = 0;

  while (true) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    // Support external AbortSignal
    if (options.signal) {
      options.signal.addEventListener('abort', () => {
        controller.abort();
      }, { once: true });
    }

    try {
      const response = await fetch(url, {
        ...options,
        credentials: 'include',  // Send HttpOnly cookies for authentication
        headers: {
          ...defaultHeaders,
          ...options.headers,
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        // Retry on 5xx for idempotent requests
        if (response.status >= 500 && retryCount < MAX_RETRIES) {
          retryCount++;
          const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 5000);
          await new Promise(resolve => setTimeout(resolve, delay));
          continue;
        }

        let detail = 'Unknown error';
        try {
          const errorData = await response.json();
          detail = errorData.detail || errorData.message || JSON.stringify(errorData);
        } catch {
          detail = response.statusText;
        }
        throw new ApiError(response.status, detail);
      }

      // Handle empty responses
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        return undefined as T;
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      // Check abort source
      const isExternalAbort = options.signal?.aborted;
      const isTimeoutAbort = error instanceof Error && error.name === 'AbortError' && !isExternalAbort;

      if (isExternalAbort) {
        throw new ApiError(499, 'Request cancelled');
      }

      if (isTimeoutAbort) {
        if (retryCount < MAX_RETRIES) {
          retryCount++;
          continue;
        }
        throw new ApiError(408, 'Request timeout');
      }

      // Network error or other - retry if idempotent
      if (error instanceof Error && !(error instanceof ApiError)) {
        if (retryCount < MAX_RETRIES) {
          retryCount++;
          const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 5000);
          await new Promise(resolve => setTimeout(resolve, delay));
          continue;
        }
        throw new ApiError(0, error.message || 'Network error');
      }

      throw error;
    }
  }
}

/**
 * Convenience methods for common HTTP operations.
 */
export const apiClient = {
  get: <T>(endpoint: string, options?: FetchOptions) =>
    fetchApi<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, data?: unknown, options?: FetchOptions) =>
    fetchApi<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),

  put: <T>(endpoint: string, data?: unknown, options?: FetchOptions) =>
    fetchApi<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    }),

  patch: <T>(endpoint: string, data?: unknown, options?: FetchOptions) =>
    fetchApi<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    }),

  delete: <T>(endpoint: string, options?: FetchOptions) =>
    fetchApi<T>(endpoint, { ...options, method: 'DELETE' }),
};
