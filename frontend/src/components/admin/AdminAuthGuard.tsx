/**
 * AdminAuthGuard - Page-level authentication guard for admin panel
 *
 * Features:
 * - Auto-validates JWT token on mount
 * - Falls back to manual admin token input
 * - Stores admin token in sessionStorage for session persistence
 */

import { useState, useEffect, useCallback, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ShieldAlert, Key, Loader2, Lock } from 'lucide-react';
import { adminService } from '@/services/adminService';

const ADMIN_TOKEN_KEY = 'admin_access_token';

interface AdminAuthGuardProps {
  children: (adminToken: string | undefined) => ReactNode;
}

type AuthState = 'checking' | 'locked' | 'authenticated';

export function AdminAuthGuard({ children }: AdminAuthGuardProps) {
  const { t } = useTranslation('common');
  const [authState, setAuthState] = useState<AuthState>('checking');
  const [tokenInput, setTokenInput] = useState('');
  const [activeToken, setActiveToken] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const validateToken = useCallback(async (token?: string) => {
    setIsValidating(true);
    setError(null);
    try {
      const isValid = await adminService.validateAccess(token);
      if (isValid) {
        setActiveToken(token);
        setAuthState('authenticated');
        if (token) {
          sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
        }
      } else {
        setAuthState('locked');
        if (token) {
          setError(t('admin.invalid_token', 'Invalid admin token. Please try again.'));
        }
      }
    } catch {
      setAuthState('locked');
    } finally {
      setIsValidating(false);
    }
  }, [t]);

  useEffect(() => {
    let isMounted = true;

    // Check for cached token first
    const cachedToken = sessionStorage.getItem(ADMIN_TOKEN_KEY);

    // Try JWT auth first (no token needed), then cached token
    const attemptAuth = async () => {
      // First try with no token (uses JWT from cookies if user is admin)
      const jwtValid = await adminService.validateAccess();
      if (!isMounted) return;

      if (jwtValid) {
        setActiveToken(undefined);
        setAuthState('authenticated');
        return;
      }

      // If JWT fails and we have a cached token, try that
      if (cachedToken) {
        await validateToken(cachedToken);
      } else if (isMounted) {
        setAuthState('locked');
      }
    };

    attemptAuth();

    return () => { isMounted = false; };
  }, [validateToken]);

  const handleUnlock = async () => {
    if (!tokenInput.trim()) {
      setError(t('admin.token_required', 'Please enter an admin token.'));
      return;
    }
    await validateToken(tokenInput.trim());
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleUnlock();
    }
  };

  if (authState === 'checking') {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (authState === 'locked') {
    return (
      <div className="flex items-center justify-center min-h-[400px] p-4">
        <Card className="w-full max-w-md glass-panel">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Lock className="h-6 w-6 text-muted-foreground" />
            </div>
            <CardTitle className="flex items-center justify-center gap-2">
              <ShieldAlert className="h-5 w-5" />
              {t('admin.access_required', 'Administrator Access Required')}
            </CardTitle>
            <CardDescription>
              {t('admin.access_description', 'Enter your admin token or use your admin account to access this panel.')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive" role="alert" aria-live="assertive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="relative">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="password"
                placeholder={t('admin.token_placeholder', 'Admin Token / JWT')}
                value={tokenInput}
                onChange={(e) => {
                  setTokenInput(e.target.value);
                  setError(null);
                }}
                onKeyDown={handleKeyDown}
                className="pl-10"
                disabled={isValidating}
                autoComplete="current-password"
                aria-label={t('admin.token_input_label', 'Admin access token')}
              />
            </div>
            <Button
              onClick={handleUnlock}
              disabled={isValidating}
              className="w-full"
            >
              {isValidating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('admin.validating', 'Validating...')}
                </>
              ) : (
                t('admin.unlock', 'Unlock')
              )}
            </Button>
            <p className="text-xs text-center text-muted-foreground">
              {t('admin.token_hint', 'Supports JWT admin token or X-Admin-Key')}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children(activeToken)}</>;
}

export default AdminAuthGuard;
