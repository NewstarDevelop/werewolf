/**
 * Settings Page - User preferences and game settings
 */
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { ThemeSwitcher } from '@/components/ThemeSwitcher';
import { SoundSettings } from '@/components/settings/SoundSettings';
import { NotificationSettings } from '@/components/settings/NotificationSettings';
import { Moon, Globe } from 'lucide-react';

export default function SettingsPage() {
  const { t } = useTranslation('common');

  return (
    <div className="min-h-full relative">
      <div className="fixed inset-0 atmosphere-night z-0 pointer-events-none" />
      <div className="fixed inset-0 atmosphere-moonlight z-0 opacity-40 pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-6 md:py-10 animate-fade-in space-y-6">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight font-display">
            {t('settings.title', 'Settings')}
          </h2>
          <p className="text-muted-foreground">
            {t('settings.description', 'Manage your game preferences and account settings.')}
          </p>
        </div>

        <Separator className="bg-border/40" />

        <div className="grid gap-6 md:grid-cols-2">
        {/* Appearance Settings */}
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-primary">
              <Moon className="h-5 w-5" aria-hidden="true" />
              {t('settings.appearance', 'Appearance')}
            </CardTitle>
            <CardDescription>
              {t('settings.appearance_desc', 'Customize the interface look and feel.')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">
                  {t('settings.theme', 'Theme')}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t('settings.theme_desc', 'Choose your preferred color theme')}
                </p>
              </div>
              <ThemeSwitcher />
            </div>
          </CardContent>
        </Card>

        {/* Language Settings */}
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-primary">
              <Globe className="h-5 w-5" aria-hidden="true" />
              {t('settings.language', 'Language')}
            </CardTitle>
            <CardDescription>
              {t('settings.language_desc', 'Choose your preferred language.')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">
                  {t('settings.current_language', 'Current Language')}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t('settings.language_hint', 'Switch between Chinese and English')}
                </p>
              </div>
              <LanguageSwitcher />
            </div>
          </CardContent>
        </Card>

        {/* Sound Settings */}
        <SoundSettings />

        {/* Notification Settings */}
        <NotificationSettings />
        </div>
      </div>
    </div>
  );
}
