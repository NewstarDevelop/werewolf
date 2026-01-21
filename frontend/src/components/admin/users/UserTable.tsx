/**
 * UserTable - Display user list with selection
 */

import { useTranslation } from 'react-i18next';
import { parseServerDate } from '@/utils/date';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { MoreHorizontal, Eye, Edit, Ban, UserCheck, Shield, ShieldOff, Copy } from 'lucide-react';
import { UserStatusBadge, AdminBadge } from './UserStatusBadge';
import type { AdminUser } from '@/types/adminUser';
import { toast } from 'sonner';

interface UserTableProps {
  users: AdminUser[];
  isLoading: boolean;
  selectedIds: Set<string>;
  onSelectionChange: (ids: Set<string>) => void;
  onViewDetail: (user: AdminUser) => void;
  onEdit: (user: AdminUser) => void;
  onToggleStatus: (user: AdminUser) => void;
  onToggleAdmin: (user: AdminUser) => void;
}

function formatDate(dateStr: string | null): string {
  const date = parseServerDate(dateStr);
  if (!date) return '-';
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatDateTime(dateStr: string | null): string {
  const date = parseServerDate(dateStr);
  if (!date) return '-';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getInitials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

function truncateId(id: string, length = 8): string {
  if (id.length <= length) return id;
  return id.slice(0, length) + '...';
}

export function UserTable({
  users,
  isLoading,
  selectedIds,
  onSelectionChange,
  onViewDetail,
  onEdit,
  onToggleStatus,
  onToggleAdmin,
}: UserTableProps) {
  const { t } = useTranslation('common');

  const allSelected = users.length > 0 && users.every((u) => selectedIds.has(u.id));
  const someSelected = users.some((u) => selectedIds.has(u.id)) && !allSelected;

  const handleSelectAll = () => {
    if (allSelected) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(users.map((u) => u.id)));
    }
  };

  const handleSelectOne = (userId: string) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(userId)) {
      newSet.delete(userId);
    } else {
      newSet.add(userId);
    }
    onSelectionChange(newSet);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success(t('common.copied', 'Copied to clipboard'));
  };

  if (isLoading) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12"></TableHead>
              <TableHead className="w-24">{t('admin.users.column.id', 'ID')}</TableHead>
              <TableHead>{t('admin.users.column.user', 'User')}</TableHead>
              <TableHead>{t('admin.users.column.status', 'Status')}</TableHead>
              <TableHead>{t('admin.users.column.role', 'Role')}</TableHead>
              <TableHead>{t('admin.users.column.created', 'Created')}</TableHead>
              <TableHead>{t('admin.users.column.last_login', 'Last Login')}</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {[...Array(5)].map((_, i) => (
              <TableRow key={i}>
                <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Skeleton className="h-8 w-8 rounded-full" />
                    <div className="space-y-1">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-3 w-32" />
                    </div>
                  </div>
                </TableCell>
                <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                <TableCell><Skeleton className="h-8 w-8" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="rounded-md border p-8 text-center text-muted-foreground">
        {t('admin.users.empty', 'No users found')}
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <Checkbox
                  checked={allSelected}
                  ref={(el) => {
                    if (el) {
                      (el as unknown as HTMLInputElement).indeterminate = someSelected;
                    }
                  }}
                  onCheckedChange={handleSelectAll}
                  aria-label={t('admin.users.select_all', 'Select all')}
                />
              </TableHead>
              <TableHead className="w-24">{t('admin.users.column.id', 'ID')}</TableHead>
              <TableHead>{t('admin.users.column.user', 'User')}</TableHead>
              <TableHead>{t('admin.users.column.status', 'Status')}</TableHead>
              <TableHead>{t('admin.users.column.role', 'Role')}</TableHead>
              <TableHead>{t('admin.users.column.created', 'Created')}</TableHead>
              <TableHead>{t('admin.users.column.last_login', 'Last Login')}</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow
                key={user.id}
                className={selectedIds.has(user.id) ? 'bg-muted/50' : ''}
              >
                <TableCell>
                  <Checkbox
                    checked={selectedIds.has(user.id)}
                    onCheckedChange={() => handleSelectOne(user.id)}
                    aria-label={t('admin.users.select_user', 'Select {{name}}', { name: user.nickname })}
                  />
                </TableCell>
                <TableCell>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="font-mono text-xs h-auto py-1 px-2"
                        onClick={() => copyToClipboard(user.id)}
                      >
                        {truncateId(user.id)}
                        <Copy className="h-3 w-3 ml-1 opacity-50" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="font-mono text-xs">{user.id}</p>
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={user.avatar_url || undefined} alt={user.nickname} />
                      <AvatarFallback>{getInitials(user.nickname)}</AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col">
                      <span className="font-medium truncate max-w-[200px]">{user.nickname}</span>
                      <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                        {user.email || '-'}
                      </span>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <UserStatusBadge isActive={user.is_active} showAdmin={false} />
                </TableCell>
                <TableCell>
                  <AdminBadge isAdmin={user.is_admin} />
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  <Tooltip>
                    <TooltipTrigger>{formatDate(user.created_at)}</TooltipTrigger>
                    <TooltipContent>{formatDateTime(user.created_at)}</TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  <Tooltip>
                    <TooltipTrigger>{formatDate(user.last_login_at)}</TooltipTrigger>
                    <TooltipContent>{formatDateTime(user.last_login_at)}</TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                        <span className="sr-only">{t('admin.users.actions', 'Actions')}</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onViewDetail(user)}>
                        <Eye className="h-4 w-4 mr-2" />
                        {t('admin.users.action.view', 'View Details')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onEdit(user)}>
                        <Edit className="h-4 w-4 mr-2" />
                        {t('admin.users.action.edit', 'Edit Profile')}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => onToggleStatus(user)}>
                        {user.is_active ? (
                          <>
                            <Ban className="h-4 w-4 mr-2" />
                            {t('admin.users.action.ban', 'Ban')}
                          </>
                        ) : (
                          <>
                            <UserCheck className="h-4 w-4 mr-2" />
                            {t('admin.users.action.unban', 'Unban')}
                          </>
                        )}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onToggleAdmin(user)}>
                        {user.is_admin ? (
                          <>
                            <ShieldOff className="h-4 w-4 mr-2" />
                            {t('admin.users.action.remove_admin', 'Remove Admin')}
                          </>
                        ) : (
                          <>
                            <Shield className="h-4 w-4 mr-2" />
                            {t('admin.users.action.make_admin', 'Make Admin')}
                          </>
                        )}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </TooltipProvider>
  );
}

export default UserTable;
