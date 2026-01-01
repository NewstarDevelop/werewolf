/**
 * User profile page with stats and settings.
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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

const profileSchema = z.object({
  nickname: z.string().min(2).max(50).optional(),
  bio: z.string().max(500).optional(),
  avatar_url: z.string().url().optional().or(z.literal('')),
});

type ProfileFormData = z.infer<typeof profileSchema>;

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user, logout, updateUser, refreshUser } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
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
      const updates: any = {};
      if (data.nickname && data.nickname !== user?.nickname) updates.nickname = data.nickname;
      if (data.bio !== undefined && data.bio !== user?.bio) updates.bio = data.bio;
      if (data.avatar_url && data.avatar_url !== user?.avatar_url) updates.avatar_url = data.avatar_url;

      if (Object.keys(updates).length > 0) {
        const updatedUser = await authService.updateProfile(updates);
        updateUser(updatedUser);
        toast({
          title: '更新成功',
          description: '您的个人资料已更新',
        });
      }
    } catch (error: any) {
      toast({
        variant: 'destructive',
        title: '更新失败',
        description: error.message,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/auth/login');
  };

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">个人中心</h1>
          <Button variant="outline" onClick={() => navigate('/lobby')}>
            返回大厅
          </Button>
        </div>

        {/* Profile Card */}
        <Card>
          <CardHeader>
            <CardTitle>个人资料</CardTitle>
            <CardDescription>管理您的账户信息</CardDescription>
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
                <p className="text-sm text-muted-foreground">邮箱</p>
                <p className="font-medium">{user.email || '未绑定'}</p>
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
                      <FormLabel>昵称</FormLabel>
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
                      <FormLabel>个人简介</FormLabel>
                      <FormControl>
                        <Textarea
                          {...field}
                          placeholder="介绍一下自己..."
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
                      <FormLabel>头像URL</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          placeholder="https://example.com/avatar.jpg"
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
                      保存中...
                    </>
                  ) : (
                    '保存更改'
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
              游戏统计
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
                  <p className="text-sm text-muted-foreground">总场次</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-green-500">{stats.games_won}</p>
                  <p className="text-sm text-muted-foreground">胜场</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-blue-500">
                    {(stats.win_rate * 100).toFixed(1)}%
                  </p>
                  <p className="text-sm text-muted-foreground">胜率</p>
                </div>
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">暂无数据</p>
            )}
          </CardContent>
        </Card>

        {/* Danger Zone */}
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">危险区域</CardTitle>
          </CardHeader>
          <CardContent>
            <Button variant="destructive" onClick={handleLogout}>
              退出登录
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
