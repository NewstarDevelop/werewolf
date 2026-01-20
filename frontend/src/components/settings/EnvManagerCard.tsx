/**
 * Environment Variables Management Card
 * Main component for managing .env variables
 */

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { Plus, AlertTriangle, Loader2, Key, RefreshCcw, Check } from 'lucide-react';
import { toast } from 'sonner';
import { configService } from '@/services/configService';
import { EnvVariable } from '@/types/config';
import { EnvVariablesTable } from './EnvVariablesTable';
import { EnvEditDialog } from './EnvEditDialog';
import { EnvDeleteDialog } from './EnvDeleteDialog';
import { getErrorMessage } from '@/utils/errorHandler';

const ADMIN_TOKEN_KEY = 'env_admin_token';

export function EnvManagerCard() {
  const [variables, setVariables] = useState<EnvVariable[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingVar, setEditingVar] = useState<EnvVariable | null>(null);
  const [deletingVar, setDeletingVar] = useState<EnvVariable | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  // Admin token state
  const [adminToken, setAdminToken] = useState<string>(() =>
    sessionStorage.getItem(ADMIN_TOKEN_KEY) || ''
  );
  const [authError, setAuthError] = useState(false);
  const [envNotFound, setEnvNotFound] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);

  const getAdminToken = useCallback(() => {
    return adminToken || sessionStorage.getItem(ADMIN_TOKEN_KEY) || undefined;
  }, [adminToken]);

  const loadVariables = useCallback(async () => {
    try {
      setLoading(true);
      setAuthError(false);
      setEnvNotFound(false);
      const token = getAdminToken();
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

      const message = getErrorMessage(error, '');
      if (
        status === 401 ||
        status === 403 ||
        message.includes('Admin access required') ||
        message.includes('403') ||
        message.includes('401')
      ) {
        setAuthError(true);
      }

      toast.error(getErrorMessage(error, 'Failed to load environment variables'));
    } finally {
      setLoading(false);
    }
  }, [getAdminToken]);

  useEffect(() => {
    loadVariables();
  }, [loadVariables]);

  const handleTokenSubmit = async () => {
    // Save token to session storage regardless of loading state
    if (adminToken) {
      sessionStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    } else {
      sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    }
    // Don't trigger reload if already loading
    if (loading) return;
    await loadVariables();
  };

  const handleRestart = async () => {
    try {
      setIsRestarting(true);
      setShowRestartConfirm(false);
      await configService.restartService(getAdminToken());
      toast.success('Service restarting... Page will reload shortly.');
      setTimeout(() => window.location.reload(), 3000);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to restart service'));
      setIsRestarting(false);
    }
  };

  const handleSave = async (name: string, value: string, confirmSensitive: boolean) => {
    try {
      const token = getAdminToken();
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
            ? 'Variable saved. Server restart required for changes to take effect.'
            : 'Variable saved successfully'
        );
        await loadVariables();
        setEditingVar(null);
        setIsCreating(false);
      }
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to save variable'));
      throw error;
    }
  };

  const handleDelete = async (name: string) => {
    try {
      const token = getAdminToken();
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
        toast.success('Variable deleted successfully');
        await loadVariables();
        setDeletingVar(null);
      }
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to delete variable'));
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

  const missingCount = variables.filter((v) => !v.is_set && v.is_required).length;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle>Environment Variables</CardTitle>
            <CardDescription>
              Manage environment variables from your .env file
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Admin Token Input Group */}
            <div className="flex items-center gap-2">
              <div className="relative">
                <Key className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="password"
                  placeholder="Admin Token"
                  aria-label="Admin Token"
                  value={adminToken}
                  onChange={(e) => {
                    setAdminToken(e.target.value);
                    setAuthError(false);
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && handleTokenSubmit()}
                  className={`pl-8 w-[180px] ${authError ? 'border-destructive' : ''}`}
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleTokenSubmit}
                disabled={loading}
                aria-label="Confirm Token"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4 sm:mr-1" />
                )}
                <span className="hidden sm:inline">Confirm</span>
              </Button>
            </div>
            
            {/* Restart Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRestartConfirm(true)}
              disabled={isRestarting}
              aria-label="Restart Service"
            >
              {isRestarting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCcw className="h-4 w-4" />
              )}
              <span className="ml-1 hidden sm:inline">Restart</span>
            </Button>
            {/* Add Variable Button */}
            <Button onClick={handleCreate} size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Add Variable
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {authError && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <strong>Authentication failed.</strong> Please enter a valid Admin Token (JWT admin token).
            </AlertDescription>
          </Alert>
        )}
        
        {envNotFound && (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <strong>No .env file found.</strong> Create variables below to generate one.
            </AlertDescription>
          </Alert>
        )}

        {missingCount > 0 && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <strong>Action Required:</strong> {missingCount} required variable{missingCount > 1 ? 's' : ''} {missingCount > 1 ? 'are' : 'is'} missing configuration.
            </AlertDescription>
          </Alert>
        )}

        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Changes to environment variables require a server restart to take effect.
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
            <AlertDialogTitle>Restart Service?</AlertDialogTitle>
            <AlertDialogDescription>
              This will restart the backend service. All active connections will be interrupted
              and in-progress games may be affected. The service should be back online within
              a few seconds.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRestart}>Restart Now</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
