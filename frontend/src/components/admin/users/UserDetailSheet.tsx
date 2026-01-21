/**
 * UserDetailSheet - Side drawer for viewing and editing user details
 */

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { parseServerDate } from '@/utils/date';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { UserStatusBadge, AdminBadge } from './UserStatusBadge';
import {
  Loader2,
  Mail,
  Calendar,
  Clock,
  Shield,
  Ban,
  UserCheck,
  Save,
  AlertTriangle,
} from 'lucide-react';
import { adminService } from '@/services/adminService';
import type { AdminUserDetail, AdminUpdateUserProfileRequest } from '@/types/adminUser';
import { toast } from 'sonner';

interface UserDetailSheetProps {
  userId: string | null;
  isOpen: boolean;
  onClose: () => void;
  token?: string;
  initialTab?: 'overview' | 'edit' | 'danger';
  onUserUpdated?: () => void;
}

function formatDateTime(dateStr: string | null): string {
  const date = parseServerDate(dateStr);
  if (!date) return '-';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getInitials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

export function UserDetailSheet({
  userId,
  isOpen,
  onClose,
  token,
  initialTab = 'overview',
  onUserUpdated,
}: UserDetailSheetProps) {
  const { t } = useTranslation('common');
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>(initialTab);

  // Edit form state
  const [editNickname, setEditNickname] = useState('');
  const [editBio, setEditBio] = useState('');
  const [editAvatarUrl, setEditAvatarUrl] = useState('');

  // Load user detail
  useEffect(() => {
    if (isOpen && userId) {
      setIsLoading(true);
      setError(null);
      adminService
        .getUserDetail(userId, token)
        .then((data) => {
          setUser(data);
          setEditNickname(data.nickname);
          setEditBio(data.bio || '');
          setEditAvatarUrl(data.avatar_url || '');
        })
        .catch((err) => {
          setError(err.message || 'Failed to load user');
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [isOpen, userId, token]);

  // Reset tab when opening with different initial tab
  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab, userId]);

  const handleSaveProfile = async () => {
    if (!user) return;

    const updates: AdminUpdateUserProfileRequest = {};
    if (editNickname !== user.nickname) updates.nickname = editNickname;
    if (editBio !== (user.bio || '')) updates.bio = editBio;
    if (editAvatarUrl !== (user.avatar_url || '')) updates.avatar_url = editAvatarUrl;

    if (Object.keys(updates).length === 0) {
      toast.info(t('admin.users.no_changes', 'No changes to save'));
      return;
    }

    setIsSaving(true);
    try {
      const updated = await adminService.updateUserProfile(user.id, updates, token);
      setUser(updated);
      toast.success(t('admin.users.profile_updated', 'Profile updated successfully'));
      onUserUpdated?.();
    } catch (err) {
      const error = err as Error & { status?: number };
      if (error.status === 409) {
        toast.error(t('admin.users.nickname_taken', 'Nickname already taken'));
      } else {
        toast.error(error.message || 'Failed to update profile');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleStatus = async () => {
    if (!user) return;

    setIsSaving(true);
    try {
      const updated = await adminService.setUserStatus(
        user.id,
        { is_active: !user.is_active },
        token
      );
      setUser(updated);
      toast.success(
        updated.is_active
          ? t('admin.users.unbanned', 'User has been unbanned')
          : t('admin.users.banned', 'User has been banned')
      );
      onUserUpdated?.();
    } catch (err) {
      toast.error((err as Error).message || 'Failed to update status');
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleAdmin = async () => {
    if (!user) return;

    setIsSaving(true);
    try {
      const updated = await adminService.setUserAdmin(
        user.id,
        { is_admin: !user.is_admin },
        token
      );
      setUser(updated);
      toast.success(
        updated.is_admin
          ? t('admin.users.admin_granted', 'Admin privileges granted')
          : t('admin.users.admin_revoked', 'Admin privileges revoked')
      );
      onUserUpdated?.();
    } catch (err) {
      toast.error((err as Error).message || 'Failed to update admin status');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{t('admin.users.detail_title', 'User Details')}</SheetTitle>
          <SheetDescription>
            {t('admin.users.detail_description', 'View and manage user information')}
          </SheetDescription>
        </SheetHeader>

        {isLoading ? (
          <div className="space-y-6 mt-6">
            <div className="flex items-center gap-4">
              <Skeleton className="h-16 w-16 rounded-full" />
              <div className="space-y-2">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-48" />
              </div>
            </div>
            <Skeleton className="h-[300px]" />
          </div>
        ) : error ? (
          <Alert variant="destructive" className="mt-6">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : user ? (
          <div className="mt-6 space-y-6">
            {/* User Header */}
            <div className="flex items-center gap-4">
              <Avatar className="h-16 w-16">
                <AvatarImage src={user.avatar_url || undefined} alt={user.nickname} />
                <AvatarFallback className="text-lg">{getInitials(user.nickname)}</AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-semibold truncate">{user.nickname}</h3>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Mail className="h-3 w-3" />
                  <span className="truncate">{user.email || '-'}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <UserStatusBadge isActive={user.is_active} isAdmin={user.is_admin} />
                </div>
              </div>
            </div>

            <Separator />

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="overview">
                  {t('admin.users.tab.overview', 'Overview')}
                </TabsTrigger>
                <TabsTrigger value="edit">
                  {t('admin.users.tab.edit', 'Edit')}
                </TabsTrigger>
                <TabsTrigger value="danger">
                  {t('admin.users.tab.danger', 'Danger')}
                </TabsTrigger>
              </TabsList>

              {/* Overview Tab */}
              <TabsContent value="overview" className="space-y-4 mt-4">
                <div className="grid gap-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-muted-foreground">{t('admin.users.field.id', 'ID')}</Label>
                      <p className="font-mono text-sm break-all">{user.id}</p>
                    </div>
                    <div>
                      <Label className="text-muted-foreground">{t('admin.users.field.email_verified', 'Email Verified')}</Label>
                      <p>{user.is_email_verified ? t('common.yes', 'Yes') : t('common.no', 'No')}</p>
                    </div>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">{t('admin.users.field.bio', 'Bio')}</Label>
                    <p className="text-sm">{user.bio || '-'}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <Label className="text-muted-foreground text-xs">{t('admin.users.field.created', 'Created')}</Label>
                        <p className="text-sm">{formatDateTime(user.created_at)}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <Label className="text-muted-foreground text-xs">{t('admin.users.field.last_login', 'Last Login')}</Label>
                        <p className="text-sm">{formatDateTime(user.last_login_at)}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </TabsContent>

              {/* Edit Tab */}
              <TabsContent value="edit" className="space-y-4 mt-4">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="nickname">{t('admin.users.field.nickname', 'Nickname')}</Label>
                    <Input
                      id="nickname"
                      value={editNickname}
                      onChange={(e) => setEditNickname(e.target.value)}
                      maxLength={50}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="avatar_url">{t('admin.users.field.avatar_url', 'Avatar URL')}</Label>
                    <Input
                      id="avatar_url"
                      value={editAvatarUrl}
                      onChange={(e) => setEditAvatarUrl(e.target.value)}
                      placeholder="https://..."
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="bio">{t('admin.users.field.bio', 'Bio')}</Label>
                    <Textarea
                      id="bio"
                      value={editBio}
                      onChange={(e) => setEditBio(e.target.value)}
                      maxLength={500}
                      rows={4}
                    />
                  </div>
                  <Button onClick={handleSaveProfile} disabled={isSaving} className="w-full">
                    {isSaving ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4 mr-2" />
                    )}
                    {t('admin.users.save_profile', 'Save Profile')}
                  </Button>
                </div>
              </TabsContent>

              {/* Danger Tab */}
              <TabsContent value="danger" className="space-y-4 mt-4">
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    {t('admin.users.danger_warning', 'Actions in this section can significantly impact the user account.')}
                  </AlertDescription>
                </Alert>

                <div className="space-y-4">
                  {/* Ban/Unban Toggle */}
                  <div className="flex items-center justify-between p-4 rounded-lg border">
                    <div className="flex items-center gap-3">
                      {user.is_active ? (
                        <Ban className="h-5 w-5 text-destructive" />
                      ) : (
                        <UserCheck className="h-5 w-5 text-green-600" />
                      )}
                      <div>
                        <p className="font-medium">
                          {user.is_active
                            ? t('admin.users.ban_user', 'Ban User')
                            : t('admin.users.unban_user', 'Unban User')}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {user.is_active
                            ? t('admin.users.ban_description', 'Prevent this user from accessing the platform')
                            : t('admin.users.unban_description', 'Restore access for this user')}
                        </p>
                      </div>
                    </div>
                    <Switch
                      checked={!user.is_active}
                      onCheckedChange={handleToggleStatus}
                      disabled={isSaving}
                    />
                  </div>

                  {/* Admin Toggle */}
                  <div className="flex items-center justify-between p-4 rounded-lg border">
                    <div className="flex items-center gap-3">
                      <Shield className="h-5 w-5 text-amber-600" />
                      <div>
                        <p className="font-medium">
                          {t('admin.users.admin_privileges', 'Admin Privileges')}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {user.is_admin
                            ? t('admin.users.revoke_admin_description', 'Remove admin privileges from this user')
                            : t('admin.users.grant_admin_description', 'Grant admin privileges to this user')}
                        </p>
                      </div>
                    </div>
                    <Switch
                      checked={user.is_admin}
                      onCheckedChange={handleToggleAdmin}
                      disabled={isSaving}
                    />
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

export default UserDetailSheet;
