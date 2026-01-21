/**
 * BroadcastDetailDialog - Dialog for viewing broadcast details
 */

import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import { parseServerDate } from '@/utils/date';
import { Copy, Loader2, Users, CheckCircle, XCircle } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';

import { useBroadcastDetail } from '@/hooks/useBroadcastHistory';
import type { BroadcastTemplate } from './BroadcastHistoryPanel';
import { BroadcastStatus } from '@/types/broadcast';

interface BroadcastDetailDialogProps {
  broadcastId: string | null;
  token?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUseTemplate?: (template: BroadcastTemplate) => void;
}

export function BroadcastDetailDialog({
  broadcastId,
  token,
  open,
  onOpenChange,
  onUseTemplate,
}: BroadcastDetailDialogProps) {
  const { t } = useTranslation('common');
  const { data: broadcast, isLoading } = useBroadcastDetail(
    open ? broadcastId : null,
    token
  );

  const formatDate = (dateStr: string | null | undefined) => {
    const date = parseServerDate(dateStr);
    if (!date) return '-';
    try {
      return format(date, 'yyyy-MM-dd HH:mm:ss');
    } catch {
      return dateStr || '-';
    }
  };

  const handleUseTemplate = () => {
    if (broadcast && onUseTemplate) {
      onUseTemplate({
        title: broadcast.title,
        body: broadcast.body,
        category: broadcast.category,
      });
      onOpenChange(false);
    }
  };

  const getStatusColor = (status: BroadcastStatus) => {
    switch (status) {
      case BroadcastStatus.SENT:
        return 'text-green-600';
      case BroadcastStatus.PARTIAL_FAILED:
        return 'text-yellow-600';
      case BroadcastStatus.FAILED:
        return 'text-destructive';
      default:
        return 'text-muted-foreground';
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh]">
        <DialogHeader>
          <DialogTitle>{t('admin.broadcast_detail', 'Broadcast Details')}</DialogTitle>
          <DialogDescription>
            {t('admin.broadcast_detail_description', 'View the full details of this broadcast.')}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : broadcast ? (
          <ScrollArea className="max-h-[60vh] pr-4">
            <div className="space-y-4">
              {/* Status and Category */}
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={getStatusColor(broadcast.status)}>
                  {t(`admin.status_${broadcast.status.toLowerCase()}`, broadcast.status)}
                </Badge>
                <Badge variant="secondary">{broadcast.category}</Badge>
              </div>

              {/* Title */}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">
                  {t('admin.notification_title', 'Title')}
                </h4>
                <p className="font-medium">{broadcast.title}</p>
              </div>

              <Separator />

              {/* Body */}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">
                  {t('admin.notification_body', 'Message')}
                </h4>
                <p className="whitespace-pre-wrap text-sm bg-muted/50 p-3 rounded-md">
                  {broadcast.body}
                </p>
              </div>

              <Separator />

              {/* Statistics */}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                  {t('admin.delivery_stats', 'Delivery Statistics')}
                </h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center p-3 bg-muted/50 rounded-md">
                    <Users className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                    <p className="text-lg font-semibold">{broadcast.total_targets}</p>
                    <p className="text-xs text-muted-foreground">
                      {t('admin.stat_targets', 'Targets')}
                    </p>
                  </div>
                  <div className="text-center p-3 bg-muted/50 rounded-md">
                    <CheckCircle className="h-4 w-4 mx-auto mb-1 text-green-600" />
                    <p className="text-lg font-semibold text-green-600">{broadcast.sent_count}</p>
                    <p className="text-xs text-muted-foreground">
                      {t('admin.stat_sent', 'Sent')}
                    </p>
                  </div>
                  <div className="text-center p-3 bg-muted/50 rounded-md">
                    <XCircle className="h-4 w-4 mx-auto mb-1 text-destructive" />
                    <p className="text-lg font-semibold text-destructive">{broadcast.failed_count}</p>
                    <p className="text-xs text-muted-foreground">
                      {t('admin.stat_failed', 'Failed')}
                    </p>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Timestamps */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">{t('admin.created_at', 'Created')}</p>
                  <p>{formatDate(broadcast.created_at)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">{t('admin.sent_at', 'Sent')}</p>
                  <p>{formatDate(broadcast.sent_at)}</p>
                </div>
              </div>

              {/* Error message if any */}
              {broadcast.last_error && (
                <>
                  <Separator />
                  <div>
                    <h4 className="text-sm font-medium text-destructive mb-1">
                      {t('admin.last_error', 'Last Error')}
                    </h4>
                    <p className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                      {broadcast.last_error}
                    </p>
                  </div>
                </>
              )}

              {/* Resend info */}
              {broadcast.resend_of_id && (
                <>
                  <Separator />
                  <div className="text-sm text-muted-foreground">
                    {t('admin.resend_of', 'This is a resend of broadcast:')} {broadcast.resend_of_id}
                  </div>
                </>
              )}
            </div>
          </ScrollArea>
        ) : null}

        {/* Actions */}
        {broadcast && (
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={handleUseTemplate}>
              <Copy className="h-4 w-4 mr-2" />
              {t('admin.action_use_template', 'Use as Template')}
            </Button>
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              {t('common.close', 'Close')}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default BroadcastDetailDialog;
