/**
 * Admin API service for admin panel operations
 */

import { getAuthHeader } from '@/utils/token';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

/**
 * Build headers with optional admin token.
 * All tokens use Authorization header with Bearer scheme.
 */
function buildHeaders(adminToken?: string): HeadersInit {
  const headers: HeadersInit = { ...getAuthHeader() };

  if (adminToken) {
    headers['Authorization'] = `Bearer ${adminToken}`;
  }

  return headers;
}

/**
 * API Error type with HTTP status code
 */
type ApiError = Error & { status?: number };

/**
 * Build an error object with HTTP status for better error handling
 */
async function buildApiError(response: Response, fallbackMessage: string): Promise<ApiError> {
  const error = await response.json().catch(() => ({ detail: fallbackMessage }));
  const message = error.detail || fallbackMessage;
  const apiError = new Error(message) as ApiError;
  apiError.status = response.status;
  return apiError;
}

/**
 * Broadcast notification request payload
 */
export interface BroadcastNotificationRequest {
  title: string;
  body: string;
  category?: 'GAME' | 'ROOM' | 'SOCIAL' | 'SYSTEM';
  data?: Record<string, unknown>;
  persist_policy?: 'DURABLE' | 'VOLATILE';
  idempotency_key: string;
}

/**
 * Broadcast notification response
 */
export interface BroadcastNotificationResponse {
  status: string;
  idempotency_key: string;
  total_targets: number;
  processed: number;
}

export const adminService = {
  /**
   * Login with admin password
   * POST /api/auth/admin-login
   * Returns JWT admin token on success
   */
  async adminLogin(password: string): Promise<{ access_token: string; token_type: string }> {
    const response = await fetch(`${API_BASE}/api/auth/admin-login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Admin login failed');
    }

    return response.json();
  },

  /**
   * Validate admin access by attempting to fetch env vars
   * Returns true if the token is valid, false otherwise
   */
  async validateAccess(adminToken?: string): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/api/config/env/merged`, {
        credentials: 'include',
        headers: buildHeaders(adminToken),
      });
      return response.ok;
    } catch {
      return false;
    }
  },

  /**
   * Broadcast a notification to all registered users
   * POST /api/admin/notifications/broadcast
   */
  async broadcastNotification(
    request: BroadcastNotificationRequest,
    adminToken?: string
  ): Promise<BroadcastNotificationResponse> {
    const response = await fetch(`${API_BASE}/api/admin/notifications/broadcast`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...buildHeaders(adminToken),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to broadcast notification');
    }

    return response.json();
  },
};
