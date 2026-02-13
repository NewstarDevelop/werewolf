/**
 * OAuth callback handler page.
 * Token is now set as HttpOnly cookie by backend.
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { Loader2 } from 'lucide-react';

export default function OAuthCallback() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshUser } = useAuth();

  useEffect(() => {
    const handleCallback = async () => {
      // Token is already set as HttpOnly cookie by backend
      // Just refresh user data and redirect
      try {
        await refreshUser();
        navigate('/lobby', { replace: true });
      } catch (error) {
        console.error('Failed to refresh user:', error);
        navigate('/auth/login', { replace: true });
      }
    };

    handleCallback();
  }, [navigate, refreshUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <Loader2 className="h-12 w-12 animate-spin mx-auto text-primary" />
        <p className="text-muted-foreground">{t('auth.oauth_logging_in')}</p>
      </div>
    </div>
  );
}
