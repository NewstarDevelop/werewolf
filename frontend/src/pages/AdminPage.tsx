/**
 * AdminPage - Admin Panel main page
 *
 * Features:
 * - Page-level authentication via AdminAuthGuard
 * - Tabbed interface for different admin functions
 * - Broadcast notifications
 * - Environment variables management
 */

import { useTranslation } from 'react-i18next';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ShieldAlert, Megaphone, Settings } from 'lucide-react';
import { AdminAuthGuard } from '@/components/admin/AdminAuthGuard';
import { BroadcastCard } from '@/components/admin/BroadcastCard';
import { EnvManager } from '@/components/admin/EnvManager';

export default function AdminPage() {
  const { t } = useTranslation('common');

  return (
    <div className="flex flex-1 flex-col space-y-6 p-6 md:p-8 animate-fade-in">
      <div className="space-y-1">
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <ShieldAlert className="h-6 w-6" />
          {t('admin.page_title', 'Admin Panel')}
        </h2>
        <p className="text-muted-foreground">
          {t('admin.page_description', 'Manage system settings and broadcast notifications.')}
        </p>
      </div>

      <Separator className="bg-border" />

      <AdminAuthGuard>
        {(adminToken) => (
          <Tabs defaultValue="notifications" className="space-y-6">
            <TabsList className="grid w-full grid-cols-2 max-w-md">
              <TabsTrigger value="notifications" className="flex items-center gap-2">
                <Megaphone className="h-4 w-4" />
                {t('admin.tab_notifications', 'Notifications')}
              </TabsTrigger>
              <TabsTrigger value="config" className="flex items-center gap-2">
                <Settings className="h-4 w-4" />
                {t('admin.tab_config', 'Configuration')}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="notifications" className="space-y-6">
              <BroadcastCard token={adminToken} />
            </TabsContent>

            <TabsContent value="config" className="space-y-6">
              <EnvManager token={adminToken} />
            </TabsContent>
          </Tabs>
        )}
      </AdminAuthGuard>
    </div>
  );
}
