/**
 * EnvManager - Environment Variables Management Component
 *
 * Refactored version that accepts token as prop from AdminAuthGuard.
 * This component handles CRUD operations for .env variables.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Plus, AlertTriangle, Loader2, RefreshCcw, Settings } from 'lucide-react';
import { toast } from 'sonner';
import { configService } from '@/services/configService';
import { EnvVariable } from '@/types/config';
import { EnvVariablesTable } from '@/components/settings/EnvVariablesTable';
import { EnvEditDialog } from '@/components/settings/EnvEditDialog';
import { EnvDeleteDialog } from '@/components/settings/EnvDeleteDialog';
import { getErrorMessage } from '@/utils/errorHandler';
import { useTranslation } from 'react-i18next';

interface EnvManagerProps {
  token?: string;
}

export function EnvManager({ token }: EnvManagerProps) {
  const { t } = useTranslation('common');
  const [variables, setVariables] = useState<EnvVariable[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingVar, setEditingVar] = useState<EnvVariable | null>(null);
  const [deletingVar, setDeletingVar] = useState<EnvVariable | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [envNotFound, setEnvNotFound] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);

  const loadVariables = useCallback(async () => {
    try {
      setLoading(true);
      setEnvNotFound(false);
      const data = await configService.getMergedEnvVars(token);
      setVariables(data);
    } catch (error) {
      const status =
        typeof error === 'object' && error !== null && 'status' in error
          ? (error as { status?: number }).status
          : undefined;

      if (status === 404) {
        setEnvNotFound(true);
        setVariables([]);
        return;
      }

      toast.error(getErrorMessage(error, t('admin.env_load_failed', 'Failed to load environment variables')));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadVariables();
  }, [loadVariables]);

  const handleRestart = async () => {
    try {
      setIsRestarting(true);
      setShowRestartConfirm(false);
      await configService.restartService(token);
      toast.success(t('admin.restart_initiated', 'Service restarting... Page will reload shortly.'));
      setTimeout(() => window.location.reload(), 3000);
    } catch (error) {
      toast.error(getErrorMessage(error, t('admin.restart_failed', 'Failed to restart service')));
      setIsRestarting(false);
    }
  };

  const handleSave = async (name: string, value: string, confirmSensitive: boolean) => {
    try {
      const result = await configService.updateEnvVars(
        {
          updates: [
            {
              name,
              action: 'set',
              value,
              confirm_sensitive: confirmSensitive,
            },
          ],
        },
        token
      );

      if (result.success) {
        toast.success(
          result.restart_required
            ? t('admin.env_saved_restart', 'Variable saved. Server restart required for changes to take effect.')
            : t('admin.env_saved', 'Variable saved successfully')
        );
        await loadVariables();
        setEditingVar(null);
        setIsCreating(false);
      }
    } catch (error) {
      toast.error(getErrorMessage(error, t('admin.env_save_failed', 'Failed to save variable')));
      throw error;
    }
  };

  const handleDelete = async (name: string) => {
    try {
      const result = await configService.updateEnvVars(
        {
          updates: [
            {
              name,
              action: 'unset',
            },
          ],
        },
        token
      );

      if (result.success) {
        toast.success(t('admin.env_deleted', 'Variable deleted successfully'));
        await loadVariables();
        setDeletingVar(null);
      }
    } catch (error) {
      toast.error(getErrorMessage(error, t('admin.env_delete_failed', 'Failed to delete variable')));
    }
  };

  const handleCreate = () => {
    setIsCreating(true);
    setEditingVar(null);
  };

  const handleEdit = (variable: EnvVariable) => {
    setEditingVar(variable);
    setIsCreating(false);
  };

  const missingCount = useMemo(
    () => variables.filter((v) => !v.is_set && v.is_required).length,
    [variables]
  );

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                {t('admin.env_title', 'Environment Variables')}
              </CardTitle>
              <CardDescription>
                {t('admin.env_description', 'Manage environment variables from your .env file')}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {/* Restart Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowRestartConfirm(true)}
                disabled={isRestarting}
              >
                {isRestarting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCcw className="h-4 w-4" />
                )}
                <span className="ml-1 hidden sm:inline">
                  {t('admin.restart', 'Restart')}
                </span>
              </Button>
              {/* Add Variable Button */}
              <Button onClick={handleCreate} size="sm">
                <Plus className="h-4 w-4 mr-2" />
                {t('admin.add_variable', 'Add Variable')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {envNotFound && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <strong>{t('admin.env_not_found_title', 'No .env file found.')}</strong>{' '}
                {t('admin.env_not_found_desc', 'Create variables below to generate one.')}
              </AlertDescription>
            </Alert>
          )}

          {missingCount > 0 && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <strong>{t('admin.action_required', 'Action Required:')}</strong>{' '}
                {t('admin.missing_vars', '{{count}} required variable(s) missing configuration.', { count: missingCount })}
              </AlertDescription>
            </Alert>
          )}

          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              {t('admin.restart_hint', 'Changes to environment variables require a server restart to take effect.')}
            </AlertDescription>
          </Alert>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : (
            <EnvVariablesTable
              variables={variables}
              onEdit={handleEdit}
              onDelete={setDeletingVar}
            />
          )}
        </CardContent>
      </Card>

      <EnvEditDialog
        open={isCreating || editingVar !== null}
        variable={editingVar}
        onClose={() => {
          setEditingVar(null);
          setIsCreating(false);
        }}
        onSave={handleSave}
      />

      <EnvDeleteDialog
        open={deletingVar !== null}
        variableName={deletingVar?.name || ''}
        onClose={() => setDeletingVar(null)}
        onConfirm={() => deletingVar && handleDelete(deletingVar.name)}
      />

      {/* Restart Confirmation Dialog */}
      <AlertDialog open={showRestartConfirm} onOpenChange={setShowRestartConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('admin.restart_confirm_title', 'Restart Service?')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('admin.restart_confirm_description', 'This will restart the backend service. All active connections will be interrupted and in-progress games may be affected. The service should be back online within a few seconds.')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleRestart}>
              {t('admin.restart_now', 'Restart Now')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default EnvManager;
