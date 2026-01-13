/**
 * SidebarNavItem - Navigation item component for sidebar
 * Handles active state, disabled state, and tooltip display
 */
import { LucideIcon } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar';
import { cn } from '@/lib/utils';

interface SidebarNavItemProps {
  title: string;
  url: string;
  icon: LucideIcon;
  disabled?: boolean;
  badge?: string;
}

export function SidebarNavItem({
  title,
  url,
  icon: Icon,
  disabled,
  badge,
}: SidebarNavItemProps) {
  const location = useLocation();
  const isActive =
    location.pathname === url ||
    (url !== '/' && url !== '#' && location.pathname.startsWith(url));

  if (disabled) {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          disabled
          className="text-muted-foreground/50 cursor-not-allowed"
          tooltip={`${title} (unavailable)`}
        >
          <Icon className="text-muted-foreground/50" />
          <span>{title}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={isActive} tooltip={title}>
        <Link to={url}>
          <Icon
            className={cn(
              'transition-colors',
              isActive ? 'text-primary' : 'text-sidebar-foreground'
            )}
          />
          <span>{title}</span>
          {badge && (
            <span className="ml-auto text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded">
              {badge}
            </span>
          )}
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}
