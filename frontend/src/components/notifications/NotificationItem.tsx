/**
 * NotificationItem - Single notification card component
 */
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { Gamepad2, Users, Bell, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { parseServerDate } from '@/utils/date';
import type { Notification, NotificationCategory } from '@/types/notification';

interface NotificationItemProps {
  notification: Notification;
  onClick?: (notification: Notification) => void;
}

// Category configuration
const CATEGORY_CONFIG: Record<
  NotificationCategory,
  {
    icon: React.ComponentType<{ className?: string }>;
    borderColor: string;
    iconColor: string;
  }
> = {
  GAME: {
    icon: Gamepad2,
    borderColor: 'border-l-blue-500',
    iconColor: 'text-blue-500',
  },
  ROOM: {
    icon: Users,
    borderColor: 'border-l-green-500',
    iconColor: 'text-green-500',
  },
  SOCIAL: {
    icon: Users,
    borderColor: 'border-l-purple-500',
    iconColor: 'text-purple-500',
  },
  SYSTEM: {
    icon: Info,
    borderColor: 'border-l-orange-500',
    iconColor: 'text-orange-500',
  },
};

export function NotificationItem({
  notification,
  onClick,
}: NotificationItemProps) {
  const isUnread = !notification.read_at;
  const config = CATEGORY_CONFIG[notification.category] || {
    icon: Bell,
    borderColor: 'border-l-gray-500',
    iconColor: 'text-gray-500',
  };
  const Icon = config.icon;

  const handleClick = () => {
    if (onClick) {
      onClick(notification);
    }
  };

  // Format relative time
  const date = parseServerDate(notification.created_at);
  const timeAgo = date 
    ? formatDistanceToNow(date, {
        addSuffix: true,
        locale: zhCN,
      })
    : '';

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-3 border-l-4 cursor-pointer transition-colors',
        'hover:bg-accent/50',
        config.borderColor,
        isUnread ? 'bg-accent/30' : 'bg-transparent'
      )}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      aria-label={`${isUnread ? '未读通知: ' : ''}${notification.title}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          handleClick();
        }
      }}
    >
      {/* Unread indicator */}
      <div className="flex-shrink-0 mt-1">
        {isUnread ? (
          <div className="w-2 h-2 rounded-full bg-blue-500" />
        ) : (
          <div className="w-2 h-2" />
        )}
      </div>

      {/* Icon */}
      <div className={cn('flex-shrink-0', config.iconColor)}>
        <Icon className="h-5 w-5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p
          className={cn(
            'text-sm font-medium truncate',
            isUnread ? 'text-foreground' : 'text-muted-foreground'
          )}
        >
          {notification.title}
        </p>
        <p className="text-sm text-muted-foreground line-clamp-2 mt-0.5">
          {notification.body}
        </p>
        <p className="text-xs text-muted-foreground/70 mt-1">{timeAgo}</p>
      </div>
    </div>
  );
}

export default NotificationItem;
