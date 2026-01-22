/**
 * Notification API Service
 * Handles notification-related API calls
 */
import { fetchApi } from './api';
import type {
  Notification,
  NotificationCategory,
  NotificationListResponse,
  UnreadCountResponse,
  MarkReadResponse,
  ReadAllResponse,
  ReadBatchRequest,
  ReadBatchResponse,
} from '@/types/notification';

export interface ListNotificationsParams {
  category?: NotificationCategory;
  unread_only?: boolean;
  page?: number;
  page_size?: number;
}

/**
 * List notifications with optional filtering and pagination
 */
export async function listNotifications(
  params: ListNotificationsParams = {}
): Promise<NotificationListResponse> {
  const searchParams = new URLSearchParams();

  if (params.category) {
    searchParams.set('category', params.category);
  }
  if (params.unread_only) {
    searchParams.set('unread_only', 'true');
  }
  if (params.page) {
    searchParams.set('page', String(params.page));
  }
  if (params.page_size) {
    searchParams.set('page_size', String(params.page_size));
  }

  const queryString = searchParams.toString();
  const endpoint = queryString
    ? `/api/notifications?${queryString}`
    : '/api/notifications';

  return fetchApi<NotificationListResponse>(endpoint, { skipRoomToken: true });
}

/**
 * Get unread notification count
 */
export async function getUnreadCount(): Promise<number> {
  const response = await fetchApi<UnreadCountResponse>(
    '/api/notifications/unread-count',
    { skipRoomToken: true }
  );
  return response.unread_count;
}

/**
 * Mark a single notification as read
 */
export async function markNotificationRead(
  notificationId: string
): Promise<MarkReadResponse> {
  return fetchApi<MarkReadResponse>(
    `/api/notifications/${notificationId}/read`,
    { method: 'POST', skipRoomToken: true }
  );
}

/**
 * Mark all notifications as read
 */
export async function markAllNotificationsRead(): Promise<ReadAllResponse> {
  return fetchApi<ReadAllResponse>('/api/notifications/read-all', {
    method: 'POST',
    skipRoomToken: true,
  });
}

/**
 * Mark multiple notifications as read by ID list
 */
export async function markNotificationsBatchRead(
  notificationIds: string[]
): Promise<ReadBatchResponse> {
  const body: ReadBatchRequest = { notification_ids: notificationIds };
  return fetchApi<ReadBatchResponse>('/api/notifications/read-batch', {
    method: 'POST',
    body: JSON.stringify(body),
    skipRoomToken: true,
  });
}

// Re-export types for convenience
export type { Notification, NotificationCategory };
