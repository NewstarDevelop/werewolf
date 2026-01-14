import { Moon, Sun, Trophy, FileText, Brain, TrendingUp, Menu } from "lucide-react";
import { GamePhase, Role, Winner } from "@/services/api";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

interface GameStatusBarProps {
  isNight: boolean;
  turnCount: number;
  playersAlive: number;
  totalPlayers: number;
  phase?: GamePhase;
  role?: Role;
  actionHint?: string;
  isGameOver?: boolean;
  winner?: Winner | null;
  onOpenLogs?: () => void;
  onOpenDebug?: () => void;
  onOpenAnalysis?: () => void;
}

const GameStatusBar = ({
  isNight,
  turnCount,
  playersAlive,
  totalPlayers,
  phase,
  role,
  actionHint,
  isGameOver,
  winner,
  onOpenLogs,
  onOpenDebug,
  onOpenAnalysis,
}: GameStatusBarProps) => {
  const { t } = useTranslation(['common', 'game', 'roles']);

  return (
    <header className="relative flex items-center justify-between px-3 py-2 md:px-6 md:py-4 glass-panel-dark border-b border-border/20 backdrop-blur-md z-50 transition-all duration-500 shadow-sm">
      {/* Decorative glow */}
      <div
        className={`absolute inset-0 opacity-40 transition-all duration-1000 ${
          isGameOver
            ? winner === "villager"
              ? "bg-gradient-to-r from-transparent via-villager/30 to-transparent"
              : "bg-gradient-to-r from-transparent via-werewolf/30 to-transparent"
            : isNight
            ? "bg-gradient-to-r from-transparent via-moonlight/20 to-transparent"
            : "bg-gradient-to-r from-transparent via-day/20 to-transparent"
        }`}
      />

      {/* Mobile Menu */}
      <div className="relative z-10 md:hidden">
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="h-11 w-11 -ml-2" aria-label={t('common:ui.open_menu')}>
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left">
            <SheetHeader>
              <SheetTitle>{t('common:app.title')}</SheetTitle>
            </SheetHeader>
            <div className="flex flex-col gap-4 mt-4">
              {role && (
                <div className="text-sm">
                  <span className="text-muted-foreground">{t('roles:your_role', { role: '' })}</span>
                  <span className="font-bold">{t(`roles:${role}`)}</span>
                </div>
              )}
              <LanguageSwitcher />
              <div className="flex flex-col gap-2">
                {isGameOver && onOpenAnalysis && (
                  <Button variant="outline" size="sm" onClick={onOpenAnalysis} className="justify-start">
                    <TrendingUp className="w-4 h-4 mr-2" />
                    {t('common:ui.game_analysis')}
                  </Button>
                )}
                {onOpenLogs && (
                  <Button variant="outline" size="sm" onClick={onOpenLogs} className="justify-start">
                    <FileText className="w-4 h-4 mr-2" />
                    {t('common:ui.system_log')}
                  </Button>
                )}
                {onOpenDebug && (
                  <Button variant="outline" size="sm" onClick={onOpenDebug} className="justify-start">
                    <Brain className="w-4 h-4 mr-2" />
                    {t('common:ui.ai_debug')}
                  </Button>
                )}
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </div>

      {/* Desktop Title */}
      <div className="relative z-10 hidden md:block">
        <h1 className="font-display text-xl font-bold text-glow-red">
          {t('common:app.title')}
        </h1>
        {role && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {t('roles:your_role', { role: t(`roles:${role}`) })}
          </p>
        )}
      </div>

      {/* Center: Day/Night Indicator & Phase */}
      <div className="relative z-10 flex flex-col items-center gap-1">
        {isGameOver ? (
          <div className="flex items-center gap-3 px-4 py-2 rounded-full border bg-secondary/50 border-accent/30">
            <Trophy className="w-5 h-5 text-accent animate-pulse" />
            <span className="font-display text-lg font-bold text-accent">
              {t('game:game_over.title')}
            </span>
            <span
              className={`font-medium hidden md:inline ${
                winner === "villager" ? "text-villager" : "text-werewolf"
              }`}
            >
              {winner === "villager" ? t('game:winner.villager') : t('game:winner.werewolf')}
            </span>
          </div>
        ) : (
          <>
            <div
              className={`flex items-center gap-2 md:gap-3 px-3 py-1.5 md:px-5 md:py-2.5 rounded-full border transition-all duration-500 backdrop-blur-sm ${
                isNight
                  ? "bg-slate-950/60 border-moonlight/40 shadow-[0_0_20px_rgba(56,189,248,0.25)]"
                  : "bg-amber-50 dark:bg-amber-100/20 border-amber-400/50 dark:border-day/40 shadow-[0_0_20px_rgba(251,191,36,0.25)]"
              }`}
            >
              {isNight ? (
                <Moon className="w-5 h-5 text-moonlight animate-glow-pulse" />
              ) : (
                <Sun className="w-5 h-5 text-amber-600 dark:text-day animate-glow-pulse" />
              )}
              <span
                className={`font-display text-lg font-bold ${
                  isNight ? "text-moonlight text-glow-blue" : "text-amber-700 dark:text-day"
                }`}
              >
                {isNight ? t('game:status.night') : t('game:status.day')}
              </span>
              <span className="text-muted-foreground font-medium">
                {t('game:status.day_count', { count: turnCount })}
              </span>
            </div>
            {phase && (
              <span className="text-xs text-muted-foreground hidden md:inline">
                {t(`game:phase.${phase}`)}
              </span>
            )}
          </>
        )}
      </div>

      {/* Right: Player Count & Controls */}
      <div className="relative z-10 flex items-center gap-3">
        <div className="hidden md:block"><LanguageSwitcher /></div>

        {isGameOver && onOpenAnalysis && (
          <button
            type="button"
            onClick={onOpenAnalysis}
            className="hidden md:inline-flex items-center gap-2 rounded-full px-4 py-2 bg-accent/20 hover:bg-accent/30 transition-colors border border-accent/30"
            title={t('common:ui.game_analysis')}
            aria-label={t('common:ui.game_analysis')}
          >
            <TrendingUp className="w-4 h-4 text-accent" />
            <span className="text-sm font-medium text-accent">{t('common:ui.game_analysis')}</span>
          </button>
        )}

        {onOpenLogs && (
          <button
            type="button"
            onClick={onOpenLogs}
            className="hidden md:inline-flex items-center justify-center rounded-full p-2 bg-muted/60 hover:bg-muted transition-colors"
            title={t('common:ui.system_log')}
            aria-label={t('common:ui.system_log')}
          >
            <FileText className="w-4 h-4 text-foreground" />
          </button>
        )}

        {onOpenDebug && (
          <button
            type="button"
            onClick={onOpenDebug}
            className="hidden md:inline-flex items-center justify-center rounded-full p-2 bg-muted/60 hover:bg-muted transition-colors"
            title={t('common:ui.ai_debug')}
            aria-label={t('common:ui.ai_debug')}
          >
            <Brain className="w-4 h-4 text-purple-400" />
          </button>
        )}

        <div className="text-right">
          <p className="text-sm text-muted-foreground hidden md:block">{t('game:status.players_alive')}</p>
          <p className="font-display text-xl">
            <span className="text-villager">{playersAlive}</span>
            <span className="text-muted-foreground mx-1">/</span>
            <span className="text-foreground">{totalPlayers}</span>
          </p>
        </div>
      </div>
    </header>
  );
};

export default GameStatusBar;
