/**
 * AppLayout - Application shell with sidebar and main content area
 * Provides responsive layout with collapsible sidebar
 */
import { Outlet } from 'react-router-dom';
import {
  SidebarProvider,
  SidebarInset,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/navigation/AppSidebar';
import { Separator } from '@/components/ui/separator';

/**
 * AppLayout - Main application layout wrapper
 *
 * Features:
 * - Responsive sidebar (drawer on mobile, collapsible on desktop)
 * - Persistent state via cookies (handled by SidebarProvider)
 * - Keyboard shortcut (Cmd/Ctrl+B) to toggle (handled by SidebarProvider)
 */
export function AppLayout() {
  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset>
        {/* Mobile header with sidebar trigger */}
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-sidebar-border px-4 md:hidden">
          <SidebarTrigger className="-ml-1" aria-label="Toggle Sidebar" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <span className="font-semibold text-sidebar-foreground">Werewolf</span>
        </header>
        {/* Main content area */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

export default AppLayout;
