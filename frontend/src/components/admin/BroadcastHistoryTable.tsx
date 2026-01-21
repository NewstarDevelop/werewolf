/**
 * BroadcastHistoryTable - Desktop table view for broadcast history
 */

import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import { parseServerDate } from '@/utils/date';
import {
  MoreHorizontal,
  Eye,
  Copy,
  RotateCcw,
  Trash2,
  CheckCircle,
  AlertCircle,
  Clock,
  XCircle,
} from 'lucide-react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';

import type { BroadcastListItem } from '@/types/broadcast';
import { BroadcastStatus } from '@/types/broadcast';

interface BroadcastHistoryTableProps {
  items: BroadcastListItem[];
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  onView: (item: BroadcastListItem) => void;
  onResend: (item: BroadcastListItem) => void;
  onUseTemplate: (item: BroadcastListItem) => void;
  onDelete: (item: BroadcastListItem) => void;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const statusConfig: Record<
  BroadcastStatus,
  { icon: typeof CheckCircle; variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }
> = {
  [BroadcastStatus.SENT]: {
    icon: CheckCircle,
    variant: 'default',
    label: 'Sent',
  },
  [BroadcastStatus.SENDING]: {
    icon: Clock,
    variant: 'secondary',
    label: 'Sending',
  },
  [BroadcastStatus.PARTIAL_FAILED]: {
    icon: AlertCircle,
    variant: 'outline',
    label: 'Partial',
  },
  [BroadcastStatus.FAILED]: {
    icon: XCircle,
    variant: 'destructive',
    label: 'Failed',
  },
  [BroadcastStatus.DRAFT]: {
    icon: Clock,
    variant: 'secondary',
    label: 'Draft',
  },
  [BroadcastStatus.DELETED]: {
    icon: Trash2,
    variant: 'outline',
    label: 'Deleted',
  },
};

export function BroadcastHistoryTable({
  items,
  selectedIds,
  onSelectionChange,
  onView,
  onResend,
  onUseTemplate,
  onDelete,
  page,
  totalPages,
  onPageChange,
}: BroadcastHistoryTableProps) {
  const { t } = useTranslation('common');

  const allSelected = items.length > 0 && selectedIds.length === items.length;
  const someSelected = selectedIds.length > 0 && selectedIds.length < items.length;

  const handleSelectAll = (checked: boolean) => {
    onSelectionChange(checked ? items.map((item) => item.id) : []);
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    onSelectionChange(
      checked
        ? [...selectedIds, id]
        : selectedIds.filter((selectedId) => selectedId !== id)
    );
  };

  const formatDate = (dateStr: string | null) => {
    const date = parseServerDate(dateStr);
    if (!date) return '-';
    try {
      return format(date, 'yyyy-MM-dd HH:mm');
    } catch {
      return dateStr || '-';
    }
  };

  const getStatusBadge = (status: BroadcastStatus) => {
    const config = statusConfig[status] || statusConfig[BroadcastStatus.SENT];
    const Icon = config.icon;
    return (
      <Badge variant={config.variant} className="gap-1">
        <Icon className="h-3 w-3" />
        {t(`admin.status_${status.toLowerCase()}`, config.label)}
      </Badge>
    );
  };

  const canResend = (status: BroadcastStatus) =>
    [BroadcastStatus.SENT, BroadcastStatus.PARTIAL_FAILED, BroadcastStatus.FAILED].includes(
      status
    );

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40px]">
                <Checkbox
                  checked={allSelected}
                  ref={(el) => {
                    if (el) (el as HTMLButtonElement & { indeterminate: boolean }).indeterminate = someSelected;
                  }}
                  onCheckedChange={(checked) => handleSelectAll(!!checked)}
                />
              </TableHead>
              <TableHead>{t('admin.column_status', 'Status')}</TableHead>
              <TableHead className="min-w-[200px]">{t('admin.column_title', 'Title')}</TableHead>
              <TableHead>{t('admin.column_category', 'Category')}</TableHead>
              <TableHead className="text-right">{t('admin.column_recipients', 'Recipients')}</TableHead>
              <TableHead>{t('admin.column_sent_at', 'Sent')}</TableHead>
              <TableHead className="w-[60px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.includes(item.id)}
                    onCheckedChange={(checked) => handleSelectOne(item.id, !!checked)}
                  />
                </TableCell>
                <TableCell>{getStatusBadge(item.status)}</TableCell>
                <TableCell className="font-medium max-w-[300px] truncate">
                  {item.title}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{item.category}</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <span className="text-green-600">{item.sent_count}</span>
                  {item.failed_count > 0 && (
                    <span className="text-destructive ml-1">/{item.failed_count}</span>
                  )}
                  <span className="text-muted-foreground ml-1">({item.total_targets})</span>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(item.sent_at || item.created_at)}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onView(item)}>
                        <Eye className="h-4 w-4 mr-2" />
                        {t('admin.action_view', 'View Details')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUseTemplate(item)}>
                        <Copy className="h-4 w-4 mr-2" />
                        {t('admin.action_use_template', 'Use as Template')}
                      </DropdownMenuItem>
                      {canResend(item.status) && (
                        <DropdownMenuItem onClick={() => onResend(item)}>
                          <RotateCcw className="h-4 w-4 mr-2" />
                          {t('admin.action_resend', 'Resend')}
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={() => onDelete(item)}
                        className="text-destructive focus:text-destructive"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        {t('admin.action_delete', 'Delete')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                onClick={() => page > 1 && onPageChange(page - 1)}
                className={page <= 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
              />
            </PaginationItem>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (page <= 3) {
                pageNum = i + 1;
              } else if (page >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = page - 2 + i;
              }
              return (
                <PaginationItem key={pageNum}>
                  <PaginationLink
                    onClick={() => onPageChange(pageNum)}
                    isActive={pageNum === page}
                    className="cursor-pointer"
                  >
                    {pageNum}
                  </PaginationLink>
                </PaginationItem>
              );
            })}
            <PaginationItem>
              <PaginationNext
                onClick={() => page < totalPages && onPageChange(page + 1)}
                className={page >= totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}
    </div>
  );
}

export default BroadcastHistoryTable;
