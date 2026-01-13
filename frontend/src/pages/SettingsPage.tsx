/**
 * Settings Page - User preferences and game settings
 */
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { Moon, Globe, Volume2, Bell } from 'lucide-react';

export default function SettingsPage() {
  const { t } = useTranslation('common');

  return (
    <div className="flex flex-1 flex-col space-y-6 p-6 md:p-8 animate-fade-in">
      <div className="space-y-1">
        <h2 className="text-2xl font-bold tracking-tight">
          {t('settings.title', 'Settings')}
        </h2>
        <p className="text-muted-foreground">
          {t('settings.description', 'Manage your game preferences and account settings.')}
        </p>
      </div>

      <Separator className="bg-border" />

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
                  {t('settings.theme_desc', 'Dark mode is currently active')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 rounded-full bg-primary" />
                <span className="text-sm text-muted-foreground">{t("settings.dark_theme", "Dark")}</span>
              </div>
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
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-accent-foreground">
              <Volume2 className="h-5 w-5" aria-hidden="true" />
              {t('settings.sound', 'Sound')}
            </CardTitle>
            <CardDescription>
              {t('settings.sound_desc', 'Configure audio preferences.')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">
                  {t('settings.sound_effects', 'Sound Effects')}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t('settings.sound_effects_desc', 'Game sound effects and notifications')}
                </p>
              </div>
              <span className="text-sm text-muted-foreground">
                {t('settings.coming_soon', 'Coming Soon')}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Notification Settings */}
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-accent-foreground">
              <Bell className="h-5 w-5" aria-hidden="true" />
              {t('settings.notifications', 'Notifications')}
            </CardTitle>
            <CardDescription>
              {t('settings.notifications_desc', 'Manage notification preferences.')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">
                  {t('settings.game_notifications', 'Game Notifications')}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t('settings.game_notifications_desc', 'Receive alerts for game events')}
                </p>
              </div>
              <span className="text-sm text-muted-foreground">
                {t('settings.coming_soon', 'Coming Soon')}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
