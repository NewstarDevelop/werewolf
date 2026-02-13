/**
 * NotificationCenter - Main notification panel container
 *
 * Features:
 * - Desktop: Popover from bell icon
 * - Mobile: Sheet from bottom
 * - Responsive design with useIsMobile hook
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { useIsMobile } from '@/hooks/use-mobile';
import { NotificationBell } from './NotificationBell';
import { NotificationList } from './NotificationList';
import { useNotifications } from '@/hooks/useNotifications';
import { useNotificationWebSocket } from '@/hooks/useNotificationWebSocket';
import type { Notification } from '@/types/notification';

interface NotificationCenterProps {
  onNotificationClick?: (notification: Notification) => void;
}

export function NotificationCenter({
  onNotificationClick,
}: NotificationCenterProps) {
  const [open, setOpen] = useState(false);
  const isMobile = useIsMobile();
  const { t } = useTranslation();

  // Get unread count from query
  const { unreadCount } = useNotifications({ pageSize: 1 });

  // Establish WebSocket connection for real-time updates
  useNotificationWebSocket({
    enabled: true,
  });

  const handleClose = () => {
    setOpen(false);
  };

  const handleNotificationClick = (notification: Notification) => {
    if (onNotificationClick) {
      onNotificationClick(notification);
    }
    handleClose();
  };

  const trigger = (
    <NotificationBell count={unreadCount} onClick={() => setOpen(true)} />
  );

  // Mobile: use Sheet (bottom drawer)
  if (isMobile) {
    return (
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>{trigger}</SheetTrigger>
        <SheetContent side="bottom" className="h-[80vh] p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>{t('notifications.title', '通知')}</SheetTitle>
          </SheetHeader>
          <NotificationList
            onNotificationClick={handleNotificationClick}
            onClose={handleClose}
          />
        </SheetContent>
      </Sheet>
    );
  }

  // Desktop: use Popover
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-[380px] p-0"
        sideOffset={8}
      >
        <NotificationList
          onNotificationClick={handleNotificationClick}
          onClose={handleClose}
        />
      </PopoverContent>
    </Popover>
  );
}

export default NotificationCenter;
