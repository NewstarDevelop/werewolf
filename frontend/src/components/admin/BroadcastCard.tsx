/**
 * BroadcastCard - Notification broadcast component for admin panel
 *
 * Features:
 * - Broadcast system notifications to all users
 * - Title and body input
 * - Confirmation dialog before sending
 * - Feedback on broadcast result
 * - Support for prefilling from templates
 */

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
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
import { Megaphone, Loader2, Send } from 'lucide-react';
import { toast } from 'sonner';
import { adminService } from '@/services/adminService';
import { getErrorMessage } from '@/utils/errorHandler';

interface BroadcastTemplate {
  title: string;
  body: string;
  category: string;
}

interface BroadcastCardProps {
  token?: string;
  initialValues?: BroadcastTemplate | null;
  onValuesUsed?: () => void;
}

export function BroadcastCard({ token, initialValues, onValuesUsed }: BroadcastCardProps) {
  const { t } = useTranslation('common');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  // Apply initial values when provided (from template)
  useEffect(() => {
    if (initialValues) {
      setTitle(initialValues.title);
      setBody(initialValues.body);
      onValuesUsed?.();
    }
  }, [initialValues, onValuesUsed]);

  const generateIdempotencyKey = () => {
    const randomPart = crypto.randomUUID?.() ??
      Math.random().toString(36).substring(2, 11);
    return `broadcast_${Date.now()}_${randomPart}`;
  };

  const handleSend = async () => {
    setShowConfirm(false);
    setIsSending(true);

    try {
      const result = await adminService.broadcastNotification(
        {
          title: title.trim(),
          body: body.trim(),
          category: 'SYSTEM',
          persist_policy: 'DURABLE',
          idempotency_key: generateIdempotencyKey(),
        },
        token
      );

      toast.success(
        t('admin.broadcast_success', 'Notification sent to {{count}} users', {
          count: result.processed,
        })
      );

      // Reset form
      setTitle('');
      setBody('');
    } catch (error) {
      toast.error(getErrorMessage(error, t('admin.broadcast_failed', 'Failed to send notification')));
    } finally {
      setIsSending(false);
    }
  };

  const canSend = title.trim().length > 0 && body.trim().length > 0;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Megaphone className="h-5 w-5" />
            {t('admin.broadcast_title', 'Broadcast Notification')}
          </CardTitle>
          <CardDescription>
            {t('admin.broadcast_description', 'Send a system notification to all registered users.')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="broadcast-title">
              {t('admin.notification_title', 'Title')}
            </Label>
            <Input
              id="broadcast-title"
              placeholder={t('admin.notification_title_placeholder', 'Notification title...')}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              disabled={isSending}
            />
            <p className="text-xs text-muted-foreground text-right">
              {title.length}/200
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="broadcast-body">
              {t('admin.notification_body', 'Message')}
            </Label>
            <Textarea
              id="broadcast-body"
              placeholder={t('admin.notification_body_placeholder', 'Notification message...')}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              maxLength={2000}
              rows={4}
              disabled={isSending}
            />
            <p className="text-xs text-muted-foreground text-right">
              {body.length}/2000
            </p>
          </div>

          <Button
            onClick={() => setShowConfirm(true)}
            disabled={!canSend || isSending}
            className="w-full"
          >
            {isSending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('admin.sending', 'Sending...')}
              </>
            ) : (
              <>
                <Send className="mr-2 h-4 w-4" />
                {t('admin.send_broadcast', 'Send Broadcast')}
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      <AlertDialog open={showConfirm} onOpenChange={setShowConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('admin.confirm_broadcast_title', 'Confirm Broadcast')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('admin.confirm_broadcast_description', 'This will send a notification to all registered users. This action cannot be undone.')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="my-4 rounded-lg border p-4 space-y-2">
            <p className="font-medium">{title}</p>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">{body}</p>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleSend}>
              {t('admin.confirm_send', 'Send to All Users')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default BroadcastCard;
