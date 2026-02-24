/**
 * System maintenance API service
 *
 * Handles system-level operations like update checks and deployments.
 * Separated from configService to maintain single responsibility.
 */

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
 * Update job state
 */
export type UpdateJobState = 'idle' | 'queued' | 'running' | 'success' | 'error';

/**
 * Response from GET /api/admin/update/check
 */
export interface UpdateCheckResponse {
  update_available: boolean;
  current_revision: string | null;
  remote_revision: string | null;
  blocked: boolean;
  blocking_reasons: string[];
  agent_reachable: boolean;
  agent_job_running: boolean;
  agent_job_id: string | null;
  agent_message: string | null;
}

/**
 * Request for POST /api/admin/update/run
 */
export interface UpdateRunRequest {
  force?: boolean;
  confirm_phrase?: string;
}

/**
 * Response from POST /api/admin/update/run
 */
export interface UpdateRunResponse {
  status: 'accepted';
  job_id: string;
  message: string;
}

/**
 * Response from GET /api/admin/update/status
 */
export interface UpdateStatusResponse {
  job_id: string | null;
  state: UpdateJobState;
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
  current_revision: string | null;
  remote_revision: string | null;
  last_log_lines: string[];
}

export const systemService = {
  /**
   * Check if updates are available
   * GET /api/admin/update/check
   */
  async checkUpdate(adminToken?: string): Promise<UpdateCheckResponse> {
    const response = await fetch(`${API_BASE}/api/admin/update/check`, {
      credentials: 'include',
      headers: buildHeaders(adminToken),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to check for updates');
    }

    return response.json();
  },

  /**
   * Trigger system update
   * POST /api/admin/update/run
   */
  async runUpdate(request: UpdateRunRequest = {}, adminToken?: string): Promise<UpdateRunResponse> {
    const response = await fetch(`${API_BASE}/api/admin/update/run`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...buildHeaders(adminToken),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to start update');
    }

    return response.json();
  },

  /**
   * Get update job status
   * GET /api/admin/update/status
   */
  async getUpdateStatus(jobId?: string, adminToken?: string): Promise<UpdateStatusResponse> {
    const url = new URL(`${API_BASE}/api/admin/update/status`);
    if (jobId) {
      url.searchParams.set('job_id', jobId);
    }

    const response = await fetch(url.toString(), {
      credentials: 'include',
      headers: buildHeaders(adminToken),
    });

    if (!response.ok) {
      throw await buildApiError(response, 'Failed to get update status');
    }

    return response.json();
  },
};
