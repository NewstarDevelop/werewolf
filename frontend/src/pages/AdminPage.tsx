/**
 * AdminPage - Admin Panel main page
 *
 * Features:
 * - Page-level authentication via AdminAuthGuard
 * - Tabbed interface for different admin functions
 * - Broadcast notifications
 * - Broadcast history management
 * - Environment variables management
 */

import { useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ShieldAlert, Megaphone, Settings, Users } from 'lucide-react';
import { AdminAuthGuard } from '@/components/admin/AdminAuthGuard';
import { BroadcastCard } from '@/components/admin/BroadcastCard';
import { BroadcastHistoryPanel } from '@/components/admin/BroadcastHistoryPanel';
import { EnvManager } from '@/components/admin/EnvManager';
import { SystemMaintenancePanel } from '@/components/admin/SystemMaintenancePanel';
import { UserManagementPanel } from '@/components/admin/users';
import type { BroadcastTemplate } from '@/components/admin/BroadcastHistoryPanel';

export default function AdminPage() {
  const { t } = useTranslation('common');
  const broadcastCardRef = useRef<HTMLDivElement>(null);

  // State for template prefill
  const [templateValues, setTemplateValues] = useState<BroadcastTemplate | null>(null);

  // Handle "Use as Template" from history panel
  const handleUseTemplate = useCallback((template: BroadcastTemplate) => {
    setTemplateValues(template);
    // Scroll to the broadcast card
    broadcastCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  return (
    <div className="min-h-full relative">
      <div className="fixed inset-0 atmosphere-night z-0 pointer-events-none" />
      <div className="fixed inset-0 atmosphere-moonlight z-0 opacity-40 pointer-events-none" />

      <div className="relative z-10 max-w-5xl mx-auto px-4 py-6 md:py-10 animate-fade-in space-y-6">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2 font-display">
            <ShieldAlert className="h-6 w-6 text-primary" />
            {t('admin.page_title', 'Admin Panel')}
          </h2>
          <p className="text-muted-foreground">
            {t('admin.page_description', 'Manage system settings and broadcast notifications.')}
          </p>
        </div>

        <Separator className="bg-border/40" />

        <AdminAuthGuard>
        {(adminToken) => (
          <Tabs defaultValue="users" className="space-y-6">
            <TabsList className="grid w-full grid-cols-3 max-w-lg">
              <TabsTrigger value="users" className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                {t('admin.tab_users', 'Users')}
              </TabsTrigger>
              <TabsTrigger value="notifications" className="flex items-center gap-2">
                <Megaphone className="h-4 w-4" />
                {t('admin.tab_notifications', 'Notifications')}
              </TabsTrigger>
              <TabsTrigger value="config" className="flex items-center gap-2">
                <Settings className="h-4 w-4" />
                {t('admin.tab_config', 'Configuration')}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="users" className="space-y-6">
              <UserManagementPanel token={adminToken} />
            </TabsContent>

            <TabsContent value="notifications" className="space-y-6">
              <div ref={broadcastCardRef}>
                <BroadcastCard
                  token={adminToken}
                  initialValues={templateValues}
                  onValuesUsed={() => setTemplateValues(null)}
                />
              </div>
              <BroadcastHistoryPanel
                token={adminToken}
                onUseTemplate={handleUseTemplate}
              />
            </TabsContent>

            <TabsContent value="config" className="space-y-6">
              <SystemMaintenancePanel token={adminToken} />
              <EnvManager token={adminToken} />
            </TabsContent>
          </Tabs>
        )}
      </AdminAuthGuard>
      </div>
    </div>
  );
}
