/**
 * Registration page for new users.
 */
import { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { useToast } from '@/hooks/use-toast';
import { Loader2 } from 'lucide-react';
import { getErrorMessage, logError } from '@/utils/errorHandler';

function createRegisterSchema(t: (key: string) => string) {
  return z.object({
    email: z.string().email({ message: t('auth.email_invalid') }),
    nickname: z.string().min(2, { message: t('auth.nickname_min') }).max(50, { message: t('auth.nickname_max') }),
    password: z.string().min(6, { message: t('auth.password_min') }).max(100, { message: t('auth.password_max') }),
    confirmPassword: z.string(),
  }).refine((data) => data.password === data.confirmPassword, {
    message: t('auth.password_mismatch'),
    path: ['confirmPassword'],
  });
}

type RegisterFormData = z.infer<ReturnType<typeof createRegisterSchema>>;

interface LocationState {
  from?: { pathname: string };
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { register: registerUser } = useAuth();
  const { toast } = useToast();
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);

  const registerSchema = createRegisterSchema(t);
  const form = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: '',
      nickname: '',
      password: '',
      confirmPassword: '',
    },
  });

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true);
    try {
      await registerUser(data.email, data.password, data.nickname);
      toast({
        title: t('auth.register_success'),
        description: t('auth.register_welcome'),
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
      logError('RegisterPage.onSubmit', error);
      toast({
        variant: 'destructive',
        title: t('auth.register_failed'),
        description: getErrorMessage(error, t('auth.register_error')),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4 relative overflow-hidden">
      {/* Atmospheric Background */}
      <div className="absolute inset-0 atmosphere-night z-0" />
      <div className="absolute inset-0 atmosphere-moonlight z-0 opacity-60" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_var(--tw-gradient-stops))] from-red-950/20 via-transparent to-transparent z-0" />
      <div className="absolute top-1/4 left-1/4 w-64 h-64 rounded-full bg-moonlight/5 blur-3xl animate-pulse-slow z-0" />
      <div className="absolute bottom-1/3 right-1/4 w-48 h-48 rounded-full bg-werewolf/5 blur-3xl animate-pulse-slow z-0" style={{ animationDelay: '1.5s' }} />

      <div className="relative z-10 w-full max-w-md animate-fade-in-up">
        {/* Branding */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 mb-3 shadow-glow-red">
            <svg viewBox="0 0 24 24" className="w-7 h-7 text-primary" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3c-1.5 2-3 3.5-3 6a3 3 0 0 0 6 0c0-2.5-1.5-4-3-6Z" />
              <path d="M6.5 12c-1.5 0-3 .5-4 2 1.5 1 3 1.5 4.5 1.5" />
              <path d="M17.5 12c1.5 0 3 .5 4 2-1.5 1-3 1.5-4.5 1.5" />
              <path d="M12 9c-2 3-4 5.5-4 8a4 4 0 0 0 8 0c0-2.5-2-5-4-8Z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold font-display text-glow-red tracking-tight">Werewolf</h1>
        </div>

        {/* Register Card */}
        <Card className="glass-panel-dark border-border/30 shadow-2xl backdrop-blur-xl">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl font-bold text-center">{t('auth.register_title')}</CardTitle>
            <CardDescription className="text-center">
              {t('auth.register_subtitle')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-foreground/80">{t('auth.email')}</FormLabel>
                      <FormControl>
                        <Input
                          type="email"
                          placeholder="your@email.com"
                          className="h-11 bg-muted/30 border-border/40 focus:border-accent/60 transition-colors"
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
                  name="nickname"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-foreground/80">{t('auth.nickname')}</FormLabel>
                      <FormControl>
                        <Input
                          type="text"
                          placeholder={t('auth.nickname_placeholder')}
                          className="h-11 bg-muted/30 border-border/40 focus:border-accent/60 transition-colors"
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
                      <FormLabel className="text-foreground/80">{t('auth.password')}</FormLabel>
                      <FormControl>
                        <Input
                          type="password"
                          placeholder={t('auth.password_placeholder')}
                          className="h-11 bg-muted/30 border-border/40 focus:border-accent/60 transition-colors"
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
                  name="confirmPassword"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-foreground/80">{t('auth.confirm_password')}</FormLabel>
                      <FormControl>
                        <Input
                          type="password"
                          placeholder={t('auth.confirm_password_placeholder')}
                          className="h-11 bg-muted/30 border-border/40 focus:border-accent/60 transition-colors"
                          {...field}
                          disabled={isLoading}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button type="submit" className="w-full h-11 text-base font-semibold shadow-lg hover:shadow-xl transition-all duration-300" disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('auth.registering')}
                    </>
                  ) : (
                    t('auth.register_button')
                  )}
                </Button>
              </form>
            </Form>
          </CardContent>
          <CardFooter className="flex flex-col space-y-2 pt-2">
            <div className="text-sm text-center text-muted-foreground">
              {t('auth.have_account')}{' '}
              <Link to="/auth/login" className="text-accent hover:text-accent/80 font-medium transition-colors">
                {t('auth.login_now')}
              </Link>
            </div>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
