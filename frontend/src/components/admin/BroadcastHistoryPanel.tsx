/**
 * BroadcastHistoryPanel - Admin broadcast history management panel
 *
 * Features:
 * - List historical broadcasts with pagination
 * - Filter by status, category, date range, and search
 * - View, edit, resend, and delete operations
 * - Responsive design (table on desktop, cards on mobile)
 */

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { History, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useIsMobile } from '@/hooks/use-mobile';
import { useBroadcastHistory } from '@/hooks/useBroadcastHistory';
import { getErrorMessage } from '@/utils/errorHandler';

import { BroadcastHistoryToolbar } from './BroadcastHistoryToolbar';
import { BroadcastHistoryTable } from './BroadcastHistoryTable';
import { BroadcastHistoryList } from './BroadcastHistoryList';
import { BroadcastDetailDialog } from './BroadcastDetailDialog';

import type { BroadcastListParams, BroadcastListItem } from '@/types/broadcast';
import { BroadcastStatus, NotificationCategory, DeleteMode } from '@/types/broadcast';

export interface BroadcastTemplate {
  title: string;
  body: string;
  category: string;
}

interface BroadcastHistoryPanelProps {
  token?: string;
  onUseTemplate?: (template: BroadcastTemplate) => void;
}

export function BroadcastHistoryPanel({
  token,
  onUseTemplate,
}: BroadcastHistoryPanelProps) {
  const { t } = useTranslation('common');
  const isMobile = useIsMobile();

  // Filter state
  const [filters, setFilters] = useState<BroadcastListParams>({
    page: 1,
    page_size: 10,
  });

  // Selected items for batch operations
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Detail dialog state
  const [detailId, setDetailId] = useState<string | null>(null);

  // Delete confirmation dialog state
  const [deleteConfirm, setDeleteConfirm] = useState<{
    open: boolean;
    item: BroadcastListItem | null;
    mode: DeleteMode;
  }>({ open: false, item: null, mode: DeleteMode.HISTORY });

  // Fetch data
  const {
    broadcasts,
    total,
    page,
    pageSize,
    isLoading,
    isError,
    refetch,
    deleteBroadcast,
    resendBroadcast,
    batchDelete,
  } = useBroadcastHistory({
    params: filters,
    token,
    enabled: true,
  });

  // Calculate pagination
  const totalPages = Math.ceil(total / pageSize);

  // Handlers
  const handleFilterChange = useCallback((newFilters: Partial<BroadcastListParams>) => {
    setFilters((prev) => ({
      ...prev,
      ...newFilters,
      page: 1, // Reset to first page on filter change
    }));
    setSelectedIds([]);
  }, []);

  const handlePageChange = useCallback((newPage: number) => {
    setFilters((prev) => ({ ...prev, page: newPage }));
    setSelectedIds([]);
  }, []);

  const handleView = useCallback((item: BroadcastListItem) => {
    setDetailId(item.id);
  }, []);

  const handleUseTemplate = useCallback(
    (item: BroadcastListItem) => {
      if (onUseTemplate) {
        onUseTemplate({
          title: item.title,
          body: '', // Body not in list item, need to fetch detail
          category: item.category,
        });
        toast.info(t('admin.template_copied', 'Template copied to broadcast form'));
      }
    },
    [onUseTemplate, t]
  );

  const handleResend = useCallback(
    async (item: BroadcastListItem) => {
      try {
        const idempotencyKey = `resend_${item.id}_${Date.now()}`;
        await resendBroadcast(item.id, idempotencyKey);
        toast.success(t('admin.resend_success', 'Broadcast queued for resending'));
      } catch (error) {
        toast.error(getErrorMessage(error, t('admin.resend_failed', 'Failed to resend')));
      }
    },
    [resendBroadcast, t]
  );

  const handleDelete = useCallback(
    (item: BroadcastListItem, mode: DeleteMode) => {
      setDeleteConfirm({ open: true, item, mode });
    },
    []
  );

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteConfirm.item) return;
    try {
      await deleteBroadcast(deleteConfirm.item.id, deleteConfirm.mode);
      const successKey = deleteConfirm.mode === DeleteMode.CASCADE
        ? 'admin.cascade_delete_success'
        : 'admin.delete_success';
      const successDefault = deleteConfirm.mode === DeleteMode.CASCADE
        ? 'Broadcast and all user notifications deleted'
        : 'Broadcast deleted';
      toast.success(t(successKey, successDefault));
    } catch (error) {
      toast.error(getErrorMessage(error, t('admin.delete_failed', 'Failed to delete')));
    } finally {
      setDeleteConfirm((prev) => ({ ...prev, open: false }));
    }
  }, [deleteConfirm, deleteBroadcast, t]);

  const handleBatchDelete = useCallback(async () => {
    if (selectedIds.length === 0) return;
    try {
      await batchDelete(selectedIds);
      setSelectedIds([]);
      toast.success(
        t('admin.batch_delete_success', '{{count}} broadcasts deleted', {
          count: selectedIds.length,
        })
      );
    } catch (error) {
      toast.error(getErrorMessage(error, t('admin.batch_delete_failed', 'Failed to delete')));
    }
  }, [selectedIds, batchDelete, t]);

  const handleSelectionChange = useCallback((ids: string[]) => {
    setSelectedIds(ids);
  }, []);

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                {t('admin.broadcast_history', 'Broadcast History')}
              </CardTitle>
              <CardDescription>
                {t(
                  'admin.broadcast_history_description',
                  'View and manage previously sent notifications.'
                )}
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="icon"
              onClick={() => refetch()}
              disabled={isLoading}
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Toolbar with filters */}
          <BroadcastHistoryToolbar
            filters={filters}
            onFilterChange={handleFilterChange}
            selectedCount={selectedIds.length}
            onBatchDelete={handleBatchDelete}
          />

          {/* Content */}
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center h-48 text-destructive">
              <p>{t('admin.load_error', 'Failed to load broadcast history')}</p>
              <Button variant="outline" className="mt-4" onClick={() => refetch()}>
                {t('common.retry', 'Retry')}
              </Button>
            </div>
          ) : broadcasts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
              <History className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('admin.no_broadcasts', 'No broadcasts found')}</p>
            </div>
          ) : isMobile ? (
            <BroadcastHistoryList
              items={broadcasts}
              onView={handleView}
              onResend={handleResend}
              onUseTemplate={handleUseTemplate}
              onDelete={handleDelete}
            />
          ) : (
            <BroadcastHistoryTable
              items={broadcasts}
              selectedIds={selectedIds}
              onSelectionChange={handleSelectionChange}
              onView={handleView}
              onResend={handleResend}
              onUseTemplate={handleUseTemplate}
              onDelete={handleDelete}
              page={page}
              totalPages={totalPages}
              onPageChange={handlePageChange}
            />
          )}

          {/* Mobile pagination */}
          {isMobile && broadcasts.length > 0 && totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => handlePageChange(page - 1)}
              >
                {t('common.previous', 'Previous')}
              </Button>
              <span className="flex items-center px-2 text-sm text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => handlePageChange(page + 1)}
              >
                {t('common.next', 'Next')}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <BroadcastDetailDialog
        broadcastId={detailId}
        token={token}
        open={!!detailId}
        onOpenChange={(open) => !open && setDetailId(null)}
        onUseTemplate={onUseTemplate}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        open={deleteConfirm.open}
        onOpenChange={(open) => setDeleteConfirm((prev) => ({ ...prev, open }))}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {deleteConfirm.mode === DeleteMode.CASCADE
                ? t('admin.dialog_delete_cascade_title', 'Permanently Delete?')
                : t('admin.dialog_delete_history_title', 'Delete History Record?')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {deleteConfirm.mode === DeleteMode.CASCADE
                ? t(
                    'admin.dialog_delete_cascade_desc',
                    'WARNING: This will remove the notification from ALL user inboxes. This action cannot be undone.'
                  )
                : t(
                    'admin.dialog_delete_history_desc',
                    'This will remove the record from the admin history. The message will remain in users\' inboxes.'
                  )}
              {deleteConfirm.item && (
                <div className="mt-2 p-2 bg-muted rounded text-sm font-medium">
                  {deleteConfirm.item.title}
                </div>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className={
                deleteConfirm.mode === DeleteMode.CASCADE
                  ? 'bg-destructive hover:bg-destructive/90'
                  : ''
              }
            >
              {t('common.confirm', 'Confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default BroadcastHistoryPanel;
