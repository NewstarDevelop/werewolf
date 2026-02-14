import { useLocation, Link } from "react-router-dom";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Home } from "lucide-react";

const NotFound = () => {
  const location = useLocation();
  const { t } = useTranslation('common');

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background relative overflow-hidden">
      <div className="absolute inset-0 atmosphere-night z-0" />
      <div className="absolute inset-0 atmosphere-moonlight z-0 opacity-40" />
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full bg-werewolf/5 blur-3xl animate-pulse-slow z-0" />

      <div className="relative z-10 text-center animate-fade-in-up px-4">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-muted/30 border border-border/30 mb-6">
          <svg viewBox="0 0 24 24" className="w-10 h-10 text-muted-foreground/40" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 3c-1.5 2-3 3.5-3 6a3 3 0 0 0 6 0c0-2.5-1.5-4-3-6Z" />
            <path d="M12 9c-2 3-4 5.5-4 8a4 4 0 0 0 8 0c0-2.5-2-5-4-8Z" />
          </svg>
        </div>
        <h1 className="text-7xl font-bold font-display text-glow-red mb-2">404</h1>
        <p className="text-lg text-muted-foreground mb-8 max-w-md mx-auto">{t('error.404_description')}</p>
        <Button asChild variant="outline" className="h-11 px-6 border-border/50 hover:border-accent/50 transition-all duration-300">
          <Link to="/">
            <Home className="w-4 h-4 mr-2" />
            {t('error.return_home')}
          </Link>
        </Button>
      </div>
    </div>
  );
};

export default NotFound;
