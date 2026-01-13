/**
 * AppSidebar - Main navigation sidebar component
 * Displays logo, navigation menu, and user info
 */
import {
  LayoutDashboard,
  Gamepad2,
  User,
  Settings,
  LogOut,
  History,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarSeparator,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { SidebarNavItem } from './SidebarNavItem';
import { toast } from 'sonner';
import { useActiveGame } from '@/hooks/useActiveGame';

/**
 * User info section at the top of sidebar
 */
function UserSection() {
  const { user } = useAuth();
  const { state } = useSidebar();
  const isCollapsed = state === 'collapsed';

  if (!user) return null;

  const initials = user.nickname
    ? user.nickname.slice(0, 2).toUpperCase()
    : user.email?.slice(0, 2).toUpperCase() || 'U';

  return (
    <div className="flex items-center gap-3 px-2 py-3">
      <Avatar className="h-9 w-9 border-2 border-primary/20">
        <AvatarImage src={user.avatar_url || undefined} alt={user.nickname} />
        <AvatarFallback className="bg-primary/10 text-primary font-semibold text-sm">
          {initials}
        </AvatarFallback>
      </Avatar>
      {!isCollapsed && (
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-sidebar-foreground truncate">
            {user.nickname || 'Player'}
          </p>
          <p className="text-xs text-sidebar-foreground/60 truncate">
            {user.email}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Current game indicator - shows when user has an active game
 */
function CurrentGameSection() {
  const { t } = useTranslation('common');
  const { hasActiveGame, activeUrl, badgeText } = useActiveGame();

  if (!hasActiveGame) {
    return (
      <SidebarNavItem
        title={t('nav.current_game', 'Current Game')}
        url="#"
        icon={Gamepad2}
        disabled
      />
    );
  }

  return (
    <SidebarNavItem
      title={t('nav.current_game', 'Current Game')}
      url={activeUrl!}
      icon={Gamepad2}
      badge={badgeText === 'Live' ? t('nav.live', 'Live') : t('nav.waiting', 'Waiting')}
    />
  );
}

/**
 * Footer section with logout button
 */
function FooterSection() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation('common');

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/auth/login');
    } catch (error) {
      console.error('Logout failed:', error);
      toast.error(t('auth.logout_failed', 'Logout failed. Please try again.'));
      // Still navigate to login page as local state has been cleared
      navigate('/auth/login');
    }
  };

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton onClick={handleLogout} tooltip={t('auth.logout', 'Logout')}>
          <LogOut className="h-4 w-4" />
          <span>{t('auth.logout', 'Logout')}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

/**
 * Main sidebar component
 */
export function AppSidebar() {
  const { t } = useTranslation('common');

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1">
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Gamepad2 className="size-4" />
          </div>
          <span className="truncate font-semibold tracking-tight text-sidebar-foreground">
            Werewolf
          </span>
        </div>
        <SidebarSeparator />
        <UserSection />
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t('nav.menu', 'Menu')}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarNavItem
                title={t('nav.lobby', 'Room Lobby')}
                url="/lobby"
                icon={LayoutDashboard}
              />
              <CurrentGameSection />
              <SidebarNavItem
                title={t('nav.profile', 'Profile')}
                url="/profile"
                icon={User}
              />
              <SidebarNavItem
                title={t('nav.history', 'History')}
                url="/history"
                icon={History}
              />
              <SidebarNavItem
                title={t('nav.settings', 'Settings')}
                url="/settings"
                icon={Settings}
              />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarSeparator />
      <SidebarFooter>
        <FooterSection />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
