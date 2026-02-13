/**
 * Login page with email/password and OAuth options.
 */
import { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useAuth } from '@/contexts/AuthContext';
import { authService } from '@/services/authService';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { useToast } from '@/hooks/use-toast';
import { Loader2, Sun, Moon } from 'lucide-react';
import { useTheme } from 'next-themes';
import { getErrorMessage, logError } from '@/utils/errorHandler';

function createLoginSchema(t: (key: string) => string) {
  return z.object({
    email: z.string().email({ message: t('auth.email_invalid') }),
    password: z.string().min(1, { message: t('auth.password_required') }),
  });
}

type LoginFormData = z.infer<ReturnType<typeof createLoginSchema>>;

interface LocationState {
  from?: { pathname: string };
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const { toast } = useToast();
  const { setTheme, resolvedTheme } = useTheme();
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);
  const [isOAuthLoading, setIsOAuthLoading] = useState(false);

  const loginSchema = createLoginSchema(t);
  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    try {
      await login(data.email, data.password);
      toast({
        title: t('auth.login_success'),
        description: t('auth.login_welcome'),
      });

      // Read the original target page from ProtectedRoute
      const from = (location.state as LocationState)?.from?.pathname;

      // Defensive validation: must be an internal path
      if (from && from.startsWith('/') && !from.startsWith('/auth/')) {
        navigate(from, { replace: true });
      } else {
        navigate('/lobby', { replace: true });
      }
    } catch (error) {
      logError('LoginPage.onSubmit', error);
      toast({
        variant: 'destructive',
        title: t('auth.login_failed'),
        description: getErrorMessage(error, t('auth.login_error')),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLinuxdoLogin = async () => {
    setIsOAuthLoading(true);
    try {
      const authUrl = await authService.getLinuxdoAuthUrl('/lobby');
      window.location.href = authUrl;
    } catch (error) {
      logError('LoginPage.handleLinuxdoLogin', error);
      toast({
        variant: 'destructive',
        title: t('auth.oauth_failed'),
        description: getErrorMessage(error, t('auth.oauth_error')),
      });
      setIsOAuthLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4 relative">
      {/* Theme Toggle Button */}
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-4 right-4"
        onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
        aria-label={t('auth.toggle_theme')}
      >
        <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
        <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      </Button>

      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">{t('auth.login_title')}</CardTitle>
          <CardDescription className="text-center">
            {t('auth.login_subtitle')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* OAuth Login */}
          <Button
            variant="outline"
            className="w-full"
            onClick={handleLinuxdoLogin}
            disabled={isOAuthLoading}
          >
            {isOAuthLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('auth.oauth_redirecting')}
              </>
            ) : (
              <>
                <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" />
                </svg>
                {t('auth.oauth_login')}
              </>
            )}
          </Button>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                {t('auth.or_email_login')}
              </span>
            </div>
          </div>

          {/* Email/Password Form */}
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('auth.email')}</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        placeholder="your@email.com"
                        {...field}
                        disabled={isLoading}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('auth.password')}</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder="••••••••"
                        {...field}
                        disabled={isLoading}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('auth.logging_in')}
                  </>
                ) : (
                  t('auth.login_button')
                )}
              </Button>
            </form>
          </Form>
        </CardContent>
        <CardFooter className="flex flex-col space-y-2">
          <div className="text-sm text-center text-muted-foreground">
            {t('auth.no_account')}{' '}
            <Link to="/auth/register" className="text-primary hover:underline">
              {t('auth.register_now')}
            </Link>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
