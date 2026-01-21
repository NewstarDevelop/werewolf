/**
 * BroadcastHistoryList - Mobile card list view for broadcast history
 */

import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
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
  Users,
} from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

import type { BroadcastListItem } from '@/types/broadcast';
import { BroadcastStatus } from '@/types/broadcast';

interface BroadcastHistoryListProps {
  items: BroadcastListItem[];
  onView: (item: BroadcastListItem) => void;
  onResend: (item: BroadcastListItem) => void;
  onUseTemplate: (item: BroadcastListItem) => void;
  onDelete: (item: BroadcastListItem) => void;
}

const statusConfig: Record<
  BroadcastStatus,
  { icon: typeof CheckCircle; color: string; label: string }
> = {
  [BroadcastStatus.SENT]: {
    icon: CheckCircle,
    color: 'text-green-600',
    label: 'Sent',
  },
  [BroadcastStatus.SENDING]: {
    icon: Clock,
    color: 'text-blue-600',
    label: 'Sending',
  },
  [BroadcastStatus.PARTIAL_FAILED]: {
    icon: AlertCircle,
    color: 'text-yellow-600',
    label: 'Partial',
  },
  [BroadcastStatus.FAILED]: {
    icon: XCircle,
    color: 'text-destructive',
    label: 'Failed',
  },
  [BroadcastStatus.DRAFT]: {
    icon: Clock,
    color: 'text-muted-foreground',
    label: 'Draft',
  },
  [BroadcastStatus.DELETED]: {
    icon: Trash2,
    color: 'text-muted-foreground',
    label: 'Deleted',
  },
};

export function BroadcastHistoryList({
  items,
  onView,
  onResend,
  onUseTemplate,
  onDelete,
}: BroadcastHistoryListProps) {
  const { t } = useTranslation('common');

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    try {
      return format(new Date(dateStr), 'MM-dd HH:mm');
    } catch {
      return dateStr;
    }
  };

  const canResend = (status: BroadcastStatus) =>
    [BroadcastStatus.SENT, BroadcastStatus.PARTIAL_FAILED, BroadcastStatus.FAILED].includes(
      status
    );

  return (
    <div className="space-y-3">
      {items.map((item) => {
        const statusInfo = statusConfig[item.status] || statusConfig[BroadcastStatus.SENT];
        const StatusIcon = statusInfo.icon;

        return (
          <Card key={item.id} className="overflow-hidden">
            <CardContent className="p-4">
              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <StatusIcon className={`h-4 w-4 flex-shrink-0 ${statusInfo.color}`} />
                  <span className="font-medium truncate">{item.title}</span>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 flex-shrink-0">
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => onView(item)}>
                      <Eye className="h-4 w-4 mr-2" />
                      {t('admin.action_view', 'View')}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onUseTemplate(item)}>
                      <Copy className="h-4 w-4 mr-2" />
                      {t('admin.action_use_template', 'Template')}
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
              </div>

              {/* Footer */}
              <div className="flex items-center gap-3 mt-3 text-sm text-muted-foreground">
                <Badge variant="outline" className="text-xs">
                  {item.category}
                </Badge>
                <span className="text-xs">
                  {formatDate(item.sent_at || item.created_at)}
                </span>
                <span className="flex items-center gap-1 ml-auto text-xs">
                  <Users className="h-3 w-3" />
                  <span className="text-green-600">{item.sent_count}</span>
                  {item.failed_count > 0 && (
                    <span className="text-destructive">/{item.failed_count}</span>
                  )}
                </span>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

export default BroadcastHistoryList;
