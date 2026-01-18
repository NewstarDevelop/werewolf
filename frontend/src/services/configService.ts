/**
 * API service for environment variable management
 */

import { EnvVariable, EnvUpdateRequest, EnvUpdateResult } from '@/types/config';
import { getAuthHeader } from '@/utils/token';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export const configService = {
  /**
   * Get all environment variables
   * GET /api/config/env
   */
  async getEnvVars(): Promise<EnvVariable[]> {
    const response = await fetch(`${API_BASE}/api/config/env`, {
      credentials: 'include',
      headers: {
        ...getAuthHeader(),
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch environment variables' }));
      throw new Error(error.detail || 'Failed to fetch environment variables');
    }

    return response.json();
  },

  /**
   * Update environment variables
   * PUT /api/config/env
   */
  async updateEnvVars(request: EnvUpdateRequest): Promise<EnvUpdateResult> {
    const response = await fetch(`${API_BASE}/api/config/env`, {
      method: 'PUT',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update environment variables' }));
      throw new Error(error.detail || 'Failed to update environment variables');
    }

    return response.json();
  },
};
