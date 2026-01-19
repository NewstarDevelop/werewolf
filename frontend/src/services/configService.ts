/**
 * API service for environment variable management
 */

import { EnvVariable, EnvUpdateRequest, EnvUpdateResult } from '@/types/config';
import { getAuthHeader } from '@/utils/token';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

/**
 * Build headers with optional admin token.
 * JWT tokens (starting with 'ey') use Authorization header.
 * Other tokens use X-Admin-Key header.
 */
function buildHeaders(adminToken?: string): HeadersInit {
  const headers: HeadersInit = { ...getAuthHeader() };

  if (adminToken) {
    // JWT tokens start with 'ey', otherwise treat as X-Admin-Key
    if (adminToken.startsWith('ey')) {
      headers['Authorization'] = `Bearer ${adminToken}`;
    } else {
      headers['X-Admin-Key'] = adminToken;
    }
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

export const configService = {
  /**
   * Get all environment variables
   * GET /api/config/env
   */
  async getEnvVars(adminToken?: string): Promise<EnvVariable[]> {
    const response = await fetch(`${API_BASE}/api/config/env`, {
      credentials: 'include',
      headers: buildHeaders(adminToken),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to fetch environment variables');
    }

    return response.json();
  },

  /**
   * Get merged environment variables (from .env and .env.example)
   * GET /api/config/env/merged
   */
  async getMergedEnvVars(adminToken?: string): Promise<EnvVariable[]> {
    const response = await fetch(`${API_BASE}/api/config/env/merged`, {
      credentials: 'include',
      headers: buildHeaders(adminToken),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to fetch merged environment variables');
    }

    return response.json();
  },

  /**
   * Update environment variables
   * PUT /api/config/env
   */
  async updateEnvVars(request: EnvUpdateRequest, adminToken?: string): Promise<EnvUpdateResult> {
    const response = await fetch(`${API_BASE}/api/config/env`, {
      method: 'PUT',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...buildHeaders(adminToken),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to update environment variables');
    }

    return response.json();
  },

  /**
   * Restart the backend service
   * POST /api/admin/restart
   */
  async restartService(adminToken?: string): Promise<{ status: string; message: string; delay_seconds: number }> {
    const response = await fetch(`${API_BASE}/api/admin/restart`, {
      method: 'POST',
      credentials: 'include',
      headers: buildHeaders(adminToken),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to restart service');
    }

    return response.json();
  },
};
