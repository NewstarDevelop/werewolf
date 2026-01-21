/**
 * Broadcast history types for admin notification management.
 */

export enum BroadcastStatus {
  DRAFT = 'DRAFT',
  SENDING = 'SENDING',
  SENT = 'SENT',
  PARTIAL_FAILED = 'PARTIAL_FAILED',
  FAILED = 'FAILED',
  DELETED = 'DELETED',
}

export enum NotificationCategory {
  GAME = 'GAME',
  ROOM = 'ROOM',
  SOCIAL = 'SOCIAL',
  SYSTEM = 'SYSTEM',
}

export enum ResendScope {
  ALL_ACTIVE = 'all_active',
  FAILED_ONLY = 'failed_only',
}

export enum DeleteMode {
  HISTORY = 'history',
  CASCADE = 'cascade',
}

export enum BatchAction {
  DELETE = 'delete',
}

/**
 * Broadcast list item (summary view)
 */
export interface BroadcastListItem {
  id: string;
  title: string;
  category: NotificationCategory;
  status: BroadcastStatus;
  total_targets: number;
  sent_count: number;
  failed_count: number;
  created_at: string;
  sent_at: string | null;
}

/**
 * Full broadcast detail
 */
export interface BroadcastDetail {
  id: string;
  idempotency_key: string;
  title: string;
  body: string;
  category: NotificationCategory;
  data: Record<string, unknown>;
  persist_policy: 'DURABLE' | 'VOLATILE';
  status: BroadcastStatus;
  total_targets: number;
  processed: number;
  sent_count: number;
  failed_count: number;
  created_by: string | null;
  resend_of_id: string | null;
  created_at: string;
  updated_at: string;
  sent_at: string | null;
  deleted_at: string | null;
  last_error: string | null;
}

/**
 * List response with pagination
 */
export interface BroadcastListResponse {
  items: BroadcastListItem[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * Create response
 */
export interface BroadcastCreateResponse {
  id: string;
  status: BroadcastStatus;
  total_targets: number;
  processed: number;
}

/**
 * Batch response
 */
export interface BroadcastBatchResponse {
  accepted: number;
  updated: number;
  failed: string[];
}

/**
 * List query params
 */
export interface BroadcastListParams {
  status?: BroadcastStatus;
  category?: NotificationCategory;
  date_from?: string;
  date_to?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

/**
 * Create request
 */
export interface BroadcastCreateRequest {
  title: string;
  body: string;
  category?: NotificationCategory;
  data?: Record<string, unknown>;
  persist_policy?: 'DURABLE' | 'VOLATILE';
  idempotency_key: string;
  send_now?: boolean;
}

/**
 * Update request (for drafts)
 */
export interface BroadcastUpdateRequest {
  title?: string;
  body?: string;
  category?: NotificationCategory;
  data?: Record<string, unknown>;
  persist_policy?: 'DURABLE' | 'VOLATILE';
}

/**
 * Resend request
 */
export interface BroadcastResendRequest {
  scope?: ResendScope;
  idempotency_key: string;
}

/**
 * Batch request
 */
export interface BroadcastBatchRequest {
  action: BatchAction;
  ids: string[];
  mode?: DeleteMode;
}
