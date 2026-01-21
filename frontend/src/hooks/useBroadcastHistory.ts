/**
 * useBroadcastHistory - Hook for broadcast history management
 *
 * Features:
 * - Fetch broadcast history with filtering and pagination
 * - CRUD operations with optimistic updates
 * - Integration with TanStack Query for caching
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo, useCallback } from 'react';
import { adminService } from '@/services/adminService';
import type {
  BroadcastListParams,
  BroadcastResendRequest,
  BroadcastUpdateRequest,
  BroadcastDetail,
} from '@/types/broadcast';
import { BatchAction, DeleteMode } from '@/types/broadcast';

// Query keys
export const broadcastKeys = {
  all: ['admin', 'broadcasts'] as const,
  lists: () => [...broadcastKeys.all, 'list'] as const,
  list: (params: BroadcastListParams) => [...broadcastKeys.lists(), params] as const,
  details: () => [...broadcastKeys.all, 'detail'] as const,
  detail: (id: string) => [...broadcastKeys.details(), id] as const,
};

export interface UseBroadcastHistoryOptions {
  params?: BroadcastListParams;
  token?: string;
  enabled?: boolean;
}

export interface UseBroadcastHistoryReturn {
  // Data
  broadcasts: BroadcastDetail[];
  total: number;
  page: number;
  pageSize: number;

  // State
  isLoading: boolean;
  isError: boolean;
  error: Error | null;

  // Actions
  refetch: () => void;
  deleteBroadcast: (id: string, mode?: DeleteMode) => Promise<void>;
  resendBroadcast: (id: string, idempotencyKey: string) => Promise<void>;
  batchDelete: (ids: string[], mode?: DeleteMode) => Promise<void>;
}

/**
 * Hook for fetching and managing broadcast history
 */
export function useBroadcastHistory(
  options: UseBroadcastHistoryOptions = {}
): UseBroadcastHistoryReturn {
  const { params = {}, token, enabled = true } = options;

  const queryClient = useQueryClient();

  // Build query params with defaults
  const queryParams: BroadcastListParams = useMemo(
    () => ({
      page: 1,
      page_size: 20,
      ...params,
    }),
    [params]
  );

  // Fetch broadcasts list
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: broadcastKeys.list(queryParams),
    queryFn: () => adminService.listBroadcasts(queryParams, token),
    enabled,
    staleTime: 30000,
    refetchOnWindowFocus: true,
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: ({ id, mode }: { id: string; mode: DeleteMode }) =>
      adminService.deleteBroadcast(id, mode, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: broadcastKeys.lists() });
    },
  });

  // Resend mutation
  const resendMutation = useMutation({
    mutationFn: ({ id, request }: { id: string; request: BroadcastResendRequest }) =>
      adminService.resendBroadcast(id, request, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: broadcastKeys.lists() });
    },
  });

  // Batch delete mutation
  const batchMutation = useMutation({
    mutationFn: ({ ids, mode }: { ids: string[]; mode: DeleteMode }) =>
      adminService.batchBroadcasts(
        { action: BatchAction.DELETE, ids, mode },
        token
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: broadcastKeys.lists() });
    },
  });

  // Action handlers
  const deleteBroadcast = useCallback(
    async (id: string, mode: DeleteMode = DeleteMode.HISTORY) => {
      await deleteMutation.mutateAsync({ id, mode });
    },
    [deleteMutation]
  );

  const resendBroadcast = useCallback(
    async (id: string, idempotencyKey: string) => {
      await resendMutation.mutateAsync({
        id,
        request: { idempotency_key: idempotencyKey },
      });
    },
    [resendMutation]
  );

  const batchDelete = useCallback(
    async (ids: string[], mode: DeleteMode = DeleteMode.HISTORY) => {
      await batchMutation.mutateAsync({ ids, mode });
    },
    [batchMutation]
  );

  return {
    broadcasts: (data?.items ?? []) as BroadcastDetail[],
    total: data?.total ?? 0,
    page: data?.page ?? 1,
    pageSize: data?.page_size ?? 20,
    isLoading,
    isError,
    error: error as Error | null,
    refetch,
    deleteBroadcast,
    resendBroadcast,
    batchDelete,
  };
}

/**
 * Hook for fetching a single broadcast detail
 */
export function useBroadcastDetail(
  broadcastId: string | null,
  token?: string
) {
  return useQuery({
    queryKey: broadcastKeys.detail(broadcastId ?? ''),
    queryFn: () => adminService.getBroadcast(broadcastId!, token),
    enabled: !!broadcastId,
    staleTime: 30000,
  });
}

/**
 * Hook for broadcast mutations (update, send)
 */
export function useBroadcastMutations(token?: string) {
  const queryClient = useQueryClient();

  const updateMutation = useMutation({
    mutationFn: ({ id, request }: { id: string; request: BroadcastUpdateRequest }) =>
      adminService.updateBroadcast(id, request, token),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: broadcastKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: broadcastKeys.lists() });
    },
  });

  const sendMutation = useMutation({
    mutationFn: (id: string) => adminService.sendBroadcast(id, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: broadcastKeys.lists() });
    },
  });

  return {
    updateBroadcast: updateMutation.mutateAsync,
    sendBroadcast: sendMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
    isSending: sendMutation.isPending,
  };
}
