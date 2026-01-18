/**
 * Environment Variable Edit Dialog
 * Dialog for creating or editing environment variables
 */

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import { Loader2, Eye, EyeOff, AlertTriangle } from 'lucide-react';
import { EnvVariable } from '@/types/config';
import { envVarSchema, EnvVarFormData } from '@/schemas/envSchema';
import { isSensitiveKey } from '@/utils/envUtils';

interface EnvEditDialogProps {
  open: boolean;
  variable: EnvVariable | null;
  onClose: () => void;
  onSave: (name: string, value: string, confirmSensitive: boolean) => Promise<void>;
}

export function EnvEditDialog({ open, variable, onClose, onSave }: EnvEditDialogProps) {
  const [showValue, setShowValue] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmSensitive, setConfirmSensitive] = useState(false);
  const isEditMode = variable !== null;

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
  } = useForm<EnvVarFormData>({
    resolver: zodResolver(envVarSchema),
    defaultValues: {
      name: '',
      value: '',
    },
  });

  const currentName = watch('name');
  const isSensitive = isSensitiveKey(currentName);

  useEffect(() => {
    if (open) {
      if (variable) {
        reset({
          name: variable.name,
          value: variable.value || '',
        });
      } else {
        reset({
          name: '',
          value: '',
        });
      }
      setShowValue(false);
      setConfirmSensitive(false);
    }
  }, [open, variable, reset]);

  const onSubmit = async (data: EnvVarFormData) => {
    try {
      setSaving(true);
      await onSave(data.name, data.value, confirmSensitive);
    } catch (error) {
      // Error is handled by parent component
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEditMode ? 'Edit Environment Variable' : 'Add Environment Variable'}
          </DialogTitle>
          <DialogDescription>
            {isEditMode
              ? 'Update the value of this environment variable.'
              : 'Create a new environment variable.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Variable Name</Label>
            <Input
              id="name"
              {...register('name')}
              disabled={isEditMode}
              placeholder="API_KEY"
              className="font-mono"
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="value">Value</Label>
            <div className="relative">
              <Input
                id="value"
                {...register('value')}
                type={showValue ? 'text' : 'password'}
                placeholder="Enter value"
                className="font-mono pr-10"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-0 top-0 h-full px-3"
                onClick={() => setShowValue(!showValue)}
              >
                {showValue ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </Button>
            </div>
            {errors.value && (
              <p className="text-sm text-destructive">{errors.value.message}</p>
            )}
          </div>

          {isSensitive && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                This variable appears to contain sensitive information (API key, secret, password, etc.).
                It will be masked in the table view.
              </AlertDescription>
            </Alert>
          )}

          {isSensitive && (
            <div className="flex items-start space-x-2">
              <Checkbox
                id="confirm-sensitive"
                checked={confirmSensitive}
                onCheckedChange={(checked) => setConfirmSensitive(checked === true)}
              />
              <div className="grid gap-1.5 leading-none">
                <label
                  htmlFor="confirm-sensitive"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  I understand this is a sensitive variable
                </label>
                <p className="text-sm text-muted-foreground">
                  Confirm that you want to modify this security-sensitive environment variable.
                </p>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving || (isSensitive && !confirmSensitive)}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditMode ? 'Save Changes' : 'Create Variable'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
