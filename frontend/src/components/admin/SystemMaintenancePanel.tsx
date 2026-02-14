/**
 * SystemMaintenancePanel - System maintenance and update management
 *
 * Features:
 * - Check for repository updates
 * - Display current and remote versions
 * - Trigger manual update with confirmation
 * - Show update progress and logs
 * - Handle blocking conditions (active games/users)
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  RefreshCw,
  Download,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Loader2,
  Server,
  GitBranch,
} from 'lucide-react';
import { toast } from 'sonner';
import { systemService, type UpdateCheckResponse, type UpdateStatusResponse, type UpdateJobState } from '@/services/systemService';

interface SystemMaintenancePanelProps {
  token?: string;
}

export function SystemMaintenancePanel({ token }: SystemMaintenancePanelProps) {
  const { t } = useTranslation('common');

  // State
  const [checkResult, setCheckResult] = useState<UpdateCheckResponse | null>(null);
  const [jobStatus, setJobStatus] = useState<UpdateStatusResponse | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [showUpdateConfirm, setShowUpdateConfirm] = useState(false);
  const [showForceConfirm, setShowForceConfirm] = useState(false);
  const [forcePhrase, setForcePhrase] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Polling ref
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Check for updates
  const handleCheck = useCallback(async () => {
    setIsChecking(true);
    setError(null);
    try {
      const result = await systemService.checkUpdate(token);
      setCheckResult(result);

      // If there's a running job, also get its status
      if (result.agent_job_running && result.agent_job_id) {
        const status = await systemService.getUpdateStatus(result.agent_job_id, token);
        setJobStatus(status);
        setIsUpdating(true);
      }
    } catch (err) {
      const error = err as Error & { status?: number };
      let message: string;

      if (error.status === 503) {
        // Feature disabled - show configuration guidance
        message = t('admin.update_feature_disabled', 'Update feature is disabled. Enable UPDATE_AGENT_ENABLED in .env to use this feature.');
      } else if (error.status === 502) {
        // Agent unreachable - show connection guidance
        message = t('admin.update_agent_unreachable', 'Update Agent is unreachable. Ensure the agent is running and UPDATE_AGENT_URL is correctly configured.');
      } else {
        message = error.message || t('admin.update_check_failed', 'Failed to check for updates');
      }

      setError(message);
      toast.error(message);
    } finally {
      setIsChecking(false);
    }
  }, [token, t]);

  // Run update
  const handleRunUpdate = useCallback(async (force: boolean = false, confirmPhrase?: string) => {
    setIsUpdating(true);
    setError(null);
    setShowUpdateConfirm(false);
    setShowForceConfirm(false);
    setForcePhrase('');

    try {
      const result = await systemService.runUpdate(
        { force, confirm_phrase: confirmPhrase },
        token
      );
      toast.success(result.message);

      // Start polling for status
      setJobStatus({
        job_id: result.job_id,
        state: 'queued',
        message: 'Starting update...',
        started_at: null,
        finished_at: null,
        current_revision: checkResult?.current_revision || null,
        remote_revision: checkResult?.remote_revision || null,
        last_log_lines: [],
      });
    } catch (err) {
      setIsUpdating(false);
      const message = (err as Error).message || 'Failed to start update';
      setError(message);
      toast.error(message);
    }
  }, [token, checkResult]);

  // Poll for job status
  useEffect(() => {
    if (!isUpdating || !jobStatus?.job_id) {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    const poll = async () => {
      try {
        const status = await systemService.getUpdateStatus(jobStatus.job_id!, token);
        setJobStatus(status);

        // Check if job is finished
        if (status.state === 'success' || status.state === 'error') {
          setIsUpdating(false);
          if (status.state === 'success') {
            toast.success(t('admin.update_success', 'Update completed successfully'));
            // Refresh check result
            handleCheck();
          } else {
            toast.error(status.message || t('admin.update_failed', 'Update failed'));
          }
        } else if (status.state === 'idle') {
          // Runner container doesn't exist - the job was lost or failed to start
          // This shouldn't happen during an active update
          setIsUpdating(false);
          toast.error(t('admin.update_job_lost', 'Update job was lost or failed to start. Please try again.'));
          handleCheck();
        }
      } catch {
        // Ignore polling errors (server might be restarting)
      }
    };

    pollingRef.current = setInterval(poll, 2000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [isUpdating, jobStatus?.job_id, token, t, handleCheck]);

  // Initial check on mount
  useEffect(() => {
    handleCheck();
  }, [handleCheck]);

  // Handle update button click
  const onUpdateClick = () => {
    if (checkResult?.blocked) {
      setShowForceConfirm(true);
    } else {
      setShowUpdateConfirm(true);
    }
  };

  // Render version badge
  const renderRevision = (revision: string | null | undefined, label: string) => {
    const shortRev = revision ? revision.substring(0, 7) : '-';
    return (
      <div className="flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">{label}:</span>
        <code className="text-sm font-mono bg-muted px-1 rounded">{shortRev}</code>
      </div>
    );
  };

  // Render job state badge
  const renderJobState = (state: UpdateJobState) => {
    const config: Record<UpdateJobState, { icon: React.ReactNode; color: string; labelKey: string; defaultLabel: string }> = {
      idle: { icon: <Server className="h-4 w-4" />, color: 'text-muted-foreground', labelKey: 'admin.job_state_idle', defaultLabel: 'Idle' },
      queued: { icon: <Loader2 className="h-4 w-4 animate-spin" />, color: 'text-yellow-500', labelKey: 'admin.job_state_queued', defaultLabel: 'Queued' },
      running: { icon: <Loader2 className="h-4 w-4 animate-spin" />, color: 'text-blue-500', labelKey: 'admin.job_state_running', defaultLabel: 'Running' },
      success: { icon: <CheckCircle2 className="h-4 w-4" />, color: 'text-green-500', labelKey: 'admin.job_state_success', defaultLabel: 'Success' },
      error: { icon: <XCircle className="h-4 w-4" />, color: 'text-red-500', labelKey: 'admin.job_state_error', defaultLabel: 'Error' },
    };
    const { icon, color, labelKey, defaultLabel } = config[state];
    return (
      <div className={`flex items-center gap-2 ${color}`}>
        {icon}
        <span className="text-sm font-medium">{t(labelKey, defaultLabel)}</span>
      </div>
    );
  };

  return (
    <>
      <Card className="glass-panel">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            {t('admin.system_maintenance_title', 'System Maintenance')}
          </CardTitle>
          <CardDescription>
            {t('admin.system_maintenance_desc', 'Manage system updates and service status')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Version Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {renderRevision(checkResult?.current_revision || jobStatus?.current_revision, t('admin.current_version', 'Current'))}
            {renderRevision(checkResult?.remote_revision || jobStatus?.remote_revision, t('admin.latest_version', 'Latest'))}
          </div>

          {/* Update Available Alert */}
          {checkResult?.update_available && !isUpdating && (
            <Alert>
              <Download className="h-4 w-4" />
              <AlertTitle>{t('admin.update_available', 'Update Available')}</AlertTitle>
              <AlertDescription>
                {t('admin.update_available_desc', 'A new version is available. Click "Update Now" to install.')}
              </AlertDescription>
            </Alert>
          )}

          {/* Up to Date */}
          {checkResult && !checkResult.update_available && !isUpdating && (
            <Alert variant="default" className="border-green-500/50 bg-green-500/10">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <AlertTitle className="text-green-600">{t('admin.up_to_date', 'Up to Date')}</AlertTitle>
              <AlertDescription>
                {t('admin.up_to_date_desc', 'System is running the latest version.')}
              </AlertDescription>
            </Alert>
          )}

          {/* Blocking Reasons */}
          {checkResult?.blocked && checkResult.blocking_reasons.length > 0 && !isUpdating && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>{t('admin.update_blocked', 'Update Blocked')}</AlertTitle>
              <AlertDescription>
                <ul className="list-disc pl-4 mt-2 space-y-1">
                  {checkResult.blocking_reasons.map((reason, i) => (
                    <li key={i} className="text-sm">{reason}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Job Status & Logs */}
          {isUpdating && jobStatus && (
            <div className="space-y-4" role="status" aria-live="polite">
              <div className="flex items-center justify-between">
                {renderJobState(jobStatus.state)}
                {jobStatus.message && (
                  <span className="text-sm text-muted-foreground">{jobStatus.message}</span>
                )}
              </div>
              {jobStatus.last_log_lines.length > 0 && (
                <ScrollArea
                  className="h-32 w-full rounded border bg-muted/50 p-2"
                  role="log"
                  aria-label={t('admin.update_logs', 'Update logs')}
                >
                  <pre className="text-xs font-mono whitespace-pre-wrap">
                    {jobStatus.last_log_lines.join('\n')}
                  </pre>
                </ScrollArea>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <Alert variant="destructive">
              <XCircle className="h-4 w-4" />
              <AlertTitle>{t('admin.error', 'Error')}</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={handleCheck}
              disabled={isChecking || isUpdating}
            >
              {isChecking ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              {t('admin.check_update', 'Check for Updates')}
            </Button>

            {checkResult?.update_available && !isUpdating && (
              <Button onClick={onUpdateClick} disabled={isUpdating}>
                <Download className="h-4 w-4 mr-2" />
                {t('admin.update_now', 'Update Now')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Normal Update Confirmation Dialog */}
      <Dialog open={showUpdateConfirm} onOpenChange={setShowUpdateConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.update_confirm_title', 'Install Update?')}</DialogTitle>
            <DialogDescription>
              {t('admin.update_confirm_desc', 'This will download the latest code and restart the server. The service will be briefly unavailable during the update.')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowUpdateConfirm(false)}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button onClick={() => handleRunUpdate(false)}>
              {t('admin.confirm_update', 'Confirm Update')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Force Update Confirmation Dialog */}
      <Dialog open={showForceConfirm} onOpenChange={setShowForceConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              {t('admin.force_update_title', 'Force Update?')}
            </DialogTitle>
            <DialogDescription>
              {t('admin.force_update_desc', 'There are active games or users. Updating now will interrupt them. Type "UPDATE" to confirm.')}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Label htmlFor="force-phrase">{t('admin.confirm_phrase', 'Confirmation Phrase')}</Label>
            <Input
              id="force-phrase"
              value={forcePhrase}
              onChange={(e) => setForcePhrase(e.target.value)}
              placeholder="UPDATE"
              className="mt-2"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowForceConfirm(false)}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleRunUpdate(true, forcePhrase)}
              disabled={forcePhrase !== 'UPDATE'}
            >
              {t('admin.force_update', 'Force Update')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
