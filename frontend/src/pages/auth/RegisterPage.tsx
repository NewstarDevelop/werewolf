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
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">{t('auth.register_title')}</CardTitle>
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
                name="nickname"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('auth.nickname')}</FormLabel>
                    <FormControl>
                      <Input
                        type="text"
                        placeholder={t('auth.nickname_placeholder')}
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
                        placeholder={t('auth.password_placeholder')}
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
                    <FormLabel>{t('auth.confirm_password')}</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder={t('auth.confirm_password_placeholder')}
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
                    {t('auth.registering')}
                  </>
                ) : (
                  t('auth.register_button')
                )}
              </Button>
            </form>
          </Form>
        </CardContent>
        <CardFooter className="flex flex-col space-y-2">
          <div className="text-sm text-center text-muted-foreground">
            {t('auth.have_account')}{' '}
            <Link to="/auth/login" className="text-primary hover:underline">
              {t('auth.login_now')}
            </Link>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
