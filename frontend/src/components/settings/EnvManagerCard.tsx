/**
 * Environment Variables Management Card
 * Main component for managing .env variables
 */

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Plus, AlertTriangle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { configService } from '@/services/configService';
import { EnvVariable } from '@/types/config';
import { EnvVariablesTable } from './EnvVariablesTable';
import { EnvEditDialog } from './EnvEditDialog';
import { EnvDeleteDialog } from './EnvDeleteDialog';
import { getErrorMessage } from '@/utils/errorHandler';

export function EnvManagerCard() {
  const { t } = useTranslation('settings');
  const [variables, setVariables] = useState<EnvVariable[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingVar, setEditingVar] = useState<EnvVariable | null>(null);
  const [deletingVar, setDeletingVar] = useState<EnvVariable | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const loadVariables = async () => {
    try {
      setLoading(true);
      const data = await configService.getEnvVars();
      setVariables(data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to load environment variables'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVariables();
  }, []);

  const handleSave = async (name: string, value: string, confirmSensitive: boolean) => {
    try {
      const result = await configService.updateEnvVars({
        updates: [
          {
            name,
            action: 'set',
            value,
            confirm_sensitive: confirmSensitive,
          },
        ],
      });

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
      const result = await configService.updateEnvVars({
        updates: [
          {
            name,
            action: 'unset',
          },
        ],
      });

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

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Environment Variables</CardTitle>
            <CardDescription>
              Manage environment variables from your .env file
            </CardDescription>
          </div>
          <Button onClick={handleCreate} size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Add Variable
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
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
    </Card>
  );
}
