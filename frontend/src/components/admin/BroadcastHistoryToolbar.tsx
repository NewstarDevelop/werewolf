/**
 * BroadcastHistoryToolbar - Filter and search toolbar for broadcast history
 */

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, X, Trash2, Filter } from 'lucide-react';

import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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

import type { BroadcastListParams } from '@/types/broadcast';
import { BroadcastStatus, NotificationCategory } from '@/types/broadcast';

interface BroadcastHistoryToolbarProps {
  filters: BroadcastListParams;
  onFilterChange: (filters: Partial<BroadcastListParams>) => void;
  selectedCount: number;
  onBatchDelete: () => Promise<void>;
}

export function BroadcastHistoryToolbar({
  filters,
  onFilterChange,
  selectedCount,
  onBatchDelete,
}: BroadcastHistoryToolbarProps) {
  const { t } = useTranslation('common');
  const [searchInput, setSearchInput] = useState(filters.q ?? '');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Debounced search
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchInput(value);
      // Debounce search to avoid too many requests
      const timer = setTimeout(() => {
        onFilterChange({ q: value || undefined });
      }, 300);
      return () => clearTimeout(timer);
    },
    [onFilterChange]
  );

  const handleClearSearch = useCallback(() => {
    setSearchInput('');
    onFilterChange({ q: undefined });
  }, [onFilterChange]);

  const handleStatusChange = useCallback(
    (value: string) => {
      onFilterChange({
        status: value === 'all' ? undefined : (value as BroadcastStatus),
      });
    },
    [onFilterChange]
  );

  const handleCategoryChange = useCallback(
    (value: string) => {
      onFilterChange({
        category: value === 'all' ? undefined : (value as NotificationCategory),
      });
    },
    [onFilterChange]
  );

  const handleBatchDelete = useCallback(async () => {
    setIsDeleting(true);
    try {
      await onBatchDelete();
    } finally {
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  }, [onBatchDelete]);

  return (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('admin.search_broadcasts', 'Search broadcasts...')}
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9 pr-9"
          />
          {searchInput && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
              onClick={handleClearSearch}
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <Select
            value={filters.status ?? 'all'}
            onValueChange={handleStatusChange}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder={t('admin.filter_status', 'Status')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('admin.all_status', 'All Status')}</SelectItem>
              <SelectItem value={BroadcastStatus.SENT}>
                {t('admin.status_sent', 'Sent')}
              </SelectItem>
              <SelectItem value={BroadcastStatus.PARTIAL_FAILED}>
                {t('admin.status_partial', 'Partial')}
              </SelectItem>
              <SelectItem value={BroadcastStatus.FAILED}>
                {t('admin.status_failed', 'Failed')}
              </SelectItem>
              <SelectItem value={BroadcastStatus.DRAFT}>
                {t('admin.status_draft', 'Draft')}
              </SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={filters.category ?? 'all'}
            onValueChange={handleCategoryChange}
          >
            <SelectTrigger className="w-[130px]">
              <SelectValue placeholder={t('admin.filter_category', 'Category')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('admin.all_categories', 'All')}</SelectItem>
              <SelectItem value={NotificationCategory.SYSTEM}>
                {t('notifications.category_system', 'System')}
              </SelectItem>
              <SelectItem value={NotificationCategory.GAME}>
                {t('notifications.category_game', 'Game')}
              </SelectItem>
              <SelectItem value={NotificationCategory.ROOM}>
                {t('notifications.category_room', 'Room')}
              </SelectItem>
              <SelectItem value={NotificationCategory.SOCIAL}>
                {t('notifications.category_social', 'Social')}
              </SelectItem>
            </SelectContent>
          </Select>

          {/* Batch delete button */}
          {selectedCount > 0 && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDeleteConfirm(true)}
            >
              <Trash2 className="h-4 w-4 mr-1" />
              {t('admin.delete_selected', 'Delete ({{count}})', { count: selectedCount })}
            </Button>
          )}
        </div>
      </div>

      {/* Batch delete confirmation */}
      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('admin.confirm_batch_delete_title', 'Delete Selected Broadcasts')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                'admin.confirm_batch_delete_description',
                'Are you sure you want to delete {{count}} selected broadcasts? This action cannot be undone.',
                { count: selectedCount }
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>
              {t('common.cancel', 'Cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBatchDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? t('common.deleting', 'Deleting...') : t('common.delete', 'Delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default BroadcastHistoryToolbar;
