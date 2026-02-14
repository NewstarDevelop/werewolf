/**
 * User profile page with stats and settings.
 */
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useAuth } from '@/contexts/AuthContext';
import { authService } from '@/services/authService';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { Loader2, User as UserIcon } from 'lucide-react';
import type { PlayerStats } from '@/types/user';
import { getErrorMessage, logError } from '@/utils/errorHandler';

const profileSchema = z.object({
  nickname: z.string().min(2).max(50).optional(),
  bio: z.string().max(500).optional(),
  avatar_url: z.string().url().optional().or(z.literal('')),
});

type ProfileFormData = z.infer<typeof profileSchema>;

export default function ProfilePage() {
  const { t } = useTranslation('profile');
  const { user, updateUser } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(true);

  const form = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      nickname: user?.nickname || '',
      bio: user?.bio || '',
      avatar_url: user?.avatar_url || '',
    },
  });

  useEffect(() => {
    const loadStats = async () => {
      try {
        const data = await authService.getStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to load stats:', error);
      } finally {
        setIsLoadingStats(false);
      }
    };

    if (user) {
      loadStats();
    }
  }, [user]);

  const onSubmit = async (data: ProfileFormData) => {
    setIsLoading(true);
    try {
      const updates: Partial<{ nickname: string; bio: string; avatar_url: string }> = {};
      if (data.nickname && data.nickname !== user?.nickname) updates.nickname = data.nickname;
      if (data.bio !== undefined && data.bio !== user?.bio) updates.bio = data.bio;
      if (data.avatar_url && data.avatar_url !== user?.avatar_url) updates.avatar_url = data.avatar_url;

      if (Object.keys(updates).length > 0) {
        const updatedUser = await authService.updateProfile(updates);
        updateUser(updatedUser);
        toast({
          title: t('toast.update_success'),
          description: t('toast.profile_updated'),
        });
      }
    } catch (error) {
      logError('ProfilePage.onSubmit', error);
      toast({
        variant: 'destructive',
        title: t('toast.update_failed'),
        description: getErrorMessage(error, t('toast.update_error')),
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-full relative">
      <div className="fixed inset-0 atmosphere-night z-0 pointer-events-none" />
      <div className="fixed inset-0 atmosphere-moonlight z-0 opacity-40 pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-6 md:py-10 animate-fade-in">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold font-display tracking-tight">{t('title')}</h1>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Profile Info - Left */}
          <div className="lg:col-span-1">
            <Card className="glass-panel border-border/30">
              <CardContent className="pt-6 flex flex-col items-center text-center">
                <Avatar className="h-24 w-24 border-2 border-accent/20 shadow-lg mb-4">
                  <AvatarImage src={user.avatar_url || undefined} alt={user.nickname} />
                  <AvatarFallback className="bg-accent/10 text-accent text-2xl font-bold">
                    <UserIcon className="h-10 w-10" />
                  </AvatarFallback>
                </Avatar>
                <h2 className="text-xl font-semibold">{user.nickname}</h2>
                <p className="text-sm text-muted-foreground mt-1">{user.email || t('avatar.email_not_bound')}</p>

                <Separator className="my-5" />

                {/* Quick Stats */}
                {isLoadingStats ? (
                  <div className="py-4">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                  </div>
                ) : stats ? (
                  <div className="w-full space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{t('stats.games_played')}</span>
                      <span className="text-lg font-bold tabular-nums">{stats.games_played}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{t('stats.games_won')}</span>
                      <span className="text-lg font-bold tabular-nums text-green-600 dark:text-green-400">{stats.games_won}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{t('stats.win_rate')}</span>
                      <span className="text-lg font-bold tabular-nums text-accent">{(stats.win_rate * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground py-4">{t('stats.no_data')}</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Edit Form - Right */}
          <div className="lg:col-span-2">
            <Card className="glass-panel border-border/30">
              <CardHeader>
                <CardTitle className="text-lg">{t('profile_card.title')}</CardTitle>
                <CardDescription className="text-sm">{t('profile_card.description')}</CardDescription>
              </CardHeader>
              <CardContent>
                <Form {...form}>
                  <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
                    <FormField
                      control={form.control}
                      name="nickname"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-foreground/80">{t('form.nickname')}</FormLabel>
                          <FormControl>
                            <Input className="h-11 bg-muted/30 border-border/40 focus:border-accent/60" {...field} disabled={isLoading} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="bio"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-foreground/80">{t('form.bio')}</FormLabel>
                          <FormControl>
                            <Textarea
                              {...field}
                              placeholder={t('form.bio_placeholder')}
                              className="resize-none bg-muted/30 border-border/40 focus:border-accent/60"
                              rows={3}
                              disabled={isLoading}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="avatar_url"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-foreground/80">{t('form.avatar_url')}</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder={t('form.avatar_url_placeholder')}
                              className="h-11 bg-muted/30 border-border/40 focus:border-accent/60"
                              disabled={isLoading}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <Button type="submit" disabled={isLoading} className="h-11 px-6 font-semibold shadow-lg hover:shadow-xl transition-all duration-300">
                      {isLoading ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          {t('form.saving')}
                        </>
                      ) : (
                        t('form.save')
                      )}
                    </Button>
                  </form>
                </Form>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
