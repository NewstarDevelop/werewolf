/**
 * Admin API service for admin panel operations
 */

import type {
  BroadcastBatchRequest,
  BroadcastBatchResponse,
  BroadcastCreateRequest,
  BroadcastCreateResponse,
  BroadcastDetail,
  BroadcastListParams,
  BroadcastListResponse,
  BroadcastResendRequest,
  BroadcastUpdateRequest,
} from '@/types/broadcast';
import type {
  AdminSetUserActiveRequest,
  AdminSetUserAdminRequest,
  AdminUpdateUserProfileRequest,
  AdminUserBatchRequest,
  AdminUserBatchResponse,
  AdminUserDetail,
  AdminUserListParams,
  AdminUserListResponse,
} from '@/types/adminUser';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

/**
 * Build headers with optional admin token.
 * All tokens use Authorization header with Bearer scheme.
 */
function buildHeaders(adminToken?: string): HeadersInit {
  const headers: HeadersInit = {};

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
   * Validate admin access by verifying JWT token has admin privileges
   * Uses dedicated admin-verify endpoint instead of env management endpoint
   * Returns true if the token is valid and has admin privileges, false otherwise
   */
  async validateAccess(adminToken?: string): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/api/auth/admin-verify`, {
        credentials: 'include',
        headers: buildHeaders(adminToken),
      });
      if (!response.ok) {
        return false;
      }
      const data = await response.json();
      return data.valid === true;
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

  // =========================================================================
  // Broadcast History Management
  // =========================================================================

  /**
   * List broadcast history with filtering and pagination
   * GET /api/admin/notifications/broadcasts
   */
  async listBroadcasts(
    params: BroadcastListParams = {},
    adminToken?: string
  ): Promise<BroadcastListResponse> {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.set('status', params.status);
    if (params.category) searchParams.set('category', params.category);
    if (params.date_from) searchParams.set('date_from', params.date_from);
    if (params.date_to) searchParams.set('date_to', params.date_to);
    if (params.q) searchParams.set('q', params.q);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));

    const url = `${API_BASE}/api/admin/notifications/broadcasts?${searchParams.toString()}`;
    const response = await fetch(url, {
      credentials: 'include',
      headers: buildHeaders(adminToken),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to fetch broadcast history');
    }

    return response.json();
  },

  /**
   * Get broadcast detail
   * GET /api/admin/notifications/broadcasts/{id}
   */
  async getBroadcast(
    broadcastId: string,
    adminToken?: string
  ): Promise<BroadcastDetail> {
    const response = await fetch(
      `${API_BASE}/api/admin/notifications/broadcasts/${broadcastId}`,
      {
        credentials: 'include',
        headers: buildHeaders(adminToken),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to fetch broadcast detail');
    }

    return response.json();
  },

  /**
   * Create and optionally send a broadcast
   * POST /api/admin/notifications/broadcasts
   */
  async createBroadcast(
    request: BroadcastCreateRequest,
    adminToken?: string
  ): Promise<BroadcastCreateResponse> {
    const response = await fetch(
      `${API_BASE}/api/admin/notifications/broadcasts`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...buildHeaders(adminToken),
        },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to create broadcast');
    }

    return response.json();
  },

  /**
   * Update a draft broadcast
   * PATCH /api/admin/notifications/broadcasts/{id}
   */
  async updateBroadcast(
    broadcastId: string,
    request: BroadcastUpdateRequest,
    adminToken?: string
  ): Promise<BroadcastDetail> {
    const response = await fetch(
      `${API_BASE}/api/admin/notifications/broadcasts/${broadcastId}`,
      {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...buildHeaders(adminToken),
        },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to update broadcast');
    }

    return response.json();
  },

  /**
   * Send a draft broadcast
   * POST /api/admin/notifications/broadcasts/{id}/send
   */
  async sendBroadcast(
    broadcastId: string,
    adminToken?: string
  ): Promise<BroadcastCreateResponse> {
    const response = await fetch(
      `${API_BASE}/api/admin/notifications/broadcasts/${broadcastId}/send`,
      {
        method: 'POST',
        credentials: 'include',
        headers: buildHeaders(adminToken),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to send broadcast');
    }

    return response.json();
  },

  /**
   * Resend a broadcast
   * POST /api/admin/notifications/broadcasts/{id}/resend
   */
  async resendBroadcast(
    broadcastId: string,
    request: BroadcastResendRequest,
    adminToken?: string
  ): Promise<BroadcastCreateResponse> {
    const response = await fetch(
      `${API_BASE}/api/admin/notifications/broadcasts/${broadcastId}/resend`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...buildHeaders(adminToken),
        },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to resend broadcast');
    }

    return response.json();
  },

  /**
   * Delete a broadcast
   * DELETE /api/admin/notifications/broadcasts/{id}
   */
  async deleteBroadcast(
    broadcastId: string,
    mode: 'history' | 'cascade' = 'history',
    adminToken?: string
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE}/api/admin/notifications/broadcasts/${broadcastId}?mode=${mode}`,
      {
        method: 'DELETE',
        credentials: 'include',
        headers: buildHeaders(adminToken),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to delete broadcast');
    }
  },

  /**
   * Batch operations on broadcasts
   * POST /api/admin/notifications/broadcasts/batch
   */
  async batchBroadcasts(
    request: BroadcastBatchRequest,
    adminToken?: string
  ): Promise<BroadcastBatchResponse> {
    const response = await fetch(
      `${API_BASE}/api/admin/notifications/broadcasts/batch`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...buildHeaders(adminToken),
        },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to perform batch operation');
    }

    return response.json();
  },

  // =========================================================================
  // User Management
  // =========================================================================

  /**
   * List users with filtering and pagination
   * GET /api/admin/users
   */
  async getUsers(
    params: AdminUserListParams = {},
    adminToken?: string
  ): Promise<AdminUserListResponse> {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.set('q', params.q);
    if (params.status) searchParams.set('status', params.status);
    if (params.admin) searchParams.set('admin', params.admin);
    if (params.sort) searchParams.set('sort', params.sort);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));

    const url = `${API_BASE}/api/admin/users?${searchParams.toString()}`;
    const response = await fetch(url, {
      credentials: 'include',
      headers: buildHeaders(adminToken),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to fetch users');
    }

    return response.json();
  },

  /**
   * Get user detail
   * GET /api/admin/users/{id}
   */
  async getUserDetail(
    userId: string,
    adminToken?: string
  ): Promise<AdminUserDetail> {
    const response = await fetch(
      `${API_BASE}/api/admin/users/${userId}`,
      {
        credentials: 'include',
        headers: buildHeaders(adminToken),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to fetch user detail');
    }

    return response.json();
  },

  /**
   * Update user profile
   * PATCH /api/admin/users/{id}/profile
   */
  async updateUserProfile(
    userId: string,
    data: AdminUpdateUserProfileRequest,
    adminToken?: string
  ): Promise<AdminUserDetail> {
    const response = await fetch(
      `${API_BASE}/api/admin/users/${userId}/profile`,
      {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...buildHeaders(adminToken),
        },
        body: JSON.stringify(data),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to update user profile');
    }

    return response.json();
  },

  /**
   * Set user active status (ban/unban)
   * PATCH /api/admin/users/{id}/status
   */
  async setUserStatus(
    userId: string,
    data: AdminSetUserActiveRequest,
    adminToken?: string
  ): Promise<AdminUserDetail> {
    const response = await fetch(
      `${API_BASE}/api/admin/users/${userId}/status`,
      {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...buildHeaders(adminToken),
        },
        body: JSON.stringify(data),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to update user status');
    }

    return response.json();
  },

  /**
   * Set user admin flag
   * PATCH /api/admin/users/{id}/admin
   */
  async setUserAdmin(
    userId: string,
    data: AdminSetUserAdminRequest,
    adminToken?: string
  ): Promise<AdminUserDetail> {
    const response = await fetch(
      `${API_BASE}/api/admin/users/${userId}/admin`,
      {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...buildHeaders(adminToken),
        },
        body: JSON.stringify(data),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to update user admin status');
    }

    return response.json();
  },

  /**
   * Batch operations on users
   * POST /api/admin/users/batch
   */
  async batchUsers(
    request: AdminUserBatchRequest,
    adminToken?: string
  ): Promise<AdminUserBatchResponse> {
    const response = await fetch(
      `${API_BASE}/api/admin/users/batch`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...buildHeaders(adminToken),
        },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to perform batch operation');
    }

    return response.json();
  },

  /**
   * Export users to CSV
   * GET /api/admin/users/export.csv
   */
  async exportUsers(
    params: AdminUserListParams = {},
    adminToken?: string
  ): Promise<Blob> {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.set('q', params.q);
    if (params.status) searchParams.set('status', params.status);
    if (params.admin) searchParams.set('admin', params.admin);
    if (params.sort) searchParams.set('sort', params.sort);

    const url = `${API_BASE}/api/admin/users/export.csv?${searchParams.toString()}`;
    const response = await fetch(url, {
      credentials: 'include',
      headers: buildHeaders(adminToken),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to export users');
    }

    return response.blob();
  },
};
