/**
 * User profile page with stats and settings.
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
import { Loader2, User as UserIcon, TrendingUp } from 'lucide-react';
import type { PlayerStats } from '@/types/user';
import { getErrorMessage, logError } from '@/utils/errorHandler';

const profileSchema = z.object({
  nickname: z.string().min(2).max(50).optional(),
  bio: z.string().max(500).optional(),
  avatar_url: z.string().url().optional().or(z.literal('')),
});

type ProfileFormData = z.infer<typeof profileSchema>;

export default function ProfilePage() {
  const navigate = useNavigate();
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
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">{t('title')}</h1>
          <Button variant="outline" onClick={() => navigate('/lobby')}>
            {t('back_to_lobby')}
          </Button>
        </div>

        {/* Profile Card */}
        <Card>
          <CardHeader>
            <CardTitle>{t('profile_card.title')}</CardTitle>
            <CardDescription>{t('profile_card.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Avatar Section */}
            <div className="flex items-center space-x-4">
              <Avatar className="h-20 w-20">
                <AvatarImage src={user.avatar_url || undefined} alt={user.nickname} />
                <AvatarFallback>
                  <UserIcon className="h-10 w-10" />
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="text-sm text-muted-foreground">{t('avatar.email')}</p>
                <p className="font-medium">{user.email || t('avatar.email_not_bound')}</p>
              </div>
            </div>

            <Separator />

            {/* Edit Form */}
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="nickname"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.nickname')}</FormLabel>
                      <FormControl>
                        <Input {...field} disabled={isLoading} />
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
                      <FormLabel>{t('form.bio')}</FormLabel>
                      <FormControl>
                        <Textarea
                          {...field}
                          placeholder={t('form.bio_placeholder')}
                          className="resize-none"
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
                      <FormLabel>{t('form.avatar_url')}</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          placeholder={t('form.avatar_url_placeholder')}
                          disabled={isLoading}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button type="submit" disabled={isLoading}>
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

        {/* Stats Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              {t('stats.title')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingStats ? (
              <div className="text-center py-8">
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
              </div>
            ) : stats ? (
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-3xl font-bold">{stats.games_played}</p>
                  <p className="text-sm text-muted-foreground">{t('stats.games_played')}</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-green-500">{stats.games_won}</p>
                  <p className="text-sm text-muted-foreground">{t('stats.games_won')}</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-blue-500">
                    {(stats.win_rate * 100).toFixed(1)}%
                  </p>
                  <p className="text-sm text-muted-foreground">{t('stats.win_rate')}</p>
                </div>
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">{t('stats.no_data')}</p>
            )}
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
