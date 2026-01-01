import { Button } from "@/components/ui/button";
import { Moon, Users, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

interface GameLobbyProps {
  onStartGame: () => void;
  isLoading: boolean;
  error: string | null;
}

const GameLobby = ({ onStartGame, isLoading, error }: GameLobbyProps) => {
  const { t } = useTranslation('common');

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background">
      {/* Background effects */}
      <div className="fixed inset-0 bg-gradient-to-b from-night via-background to-background pointer-events-none" />
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] rounded-full blur-3xl bg-moonlight/5 pointer-events-none" />

      {/* Language Switcher - Top Right */}
      <div className="fixed top-6 right-6 z-20">
        <LanguageSwitcher />
      </div>

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center gap-8 p-8">
        {/* Logo/Title */}
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <Moon className="w-24 h-24 text-moonlight animate-pulse" />
            <div className="absolute inset-0 w-24 h-24 bg-moonlight/20 rounded-full blur-xl" />
          </div>
          <h1 className="font-display text-5xl text-foreground tracking-wider">
            {t('app.title')}
          </h1>
        </div>

        {/* Game Info */}
        <div className="flex items-center gap-6 text-muted-foreground">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            <span>{t('lobby.player_count', { count: 9 })}</span>
          </div>
          <div className="text-sm">
            {t('lobby.roles')}
          </div>
        </div>

        {/* Start Button */}
        <Button
          size="lg"
          variant="default"
          onClick={onStartGame}
          disabled={isLoading}
          className="px-12 py-6 text-lg font-display tracking-wider bg-werewolf hover:bg-werewolf/90"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              {t('game.creating')}
            </>
          ) : (
            t('game.start')
          )}
        </Button>

        {/* Error message */}
        {error && (
          <div className="text-werewolf text-sm bg-werewolf/10 px-4 py-2 rounded-lg">
            {error}
          </div>
        )}

        {/* Instructions */}
        <div className="max-w-md text-center text-sm text-muted-foreground mt-4">
          <p>{t('lobby.instructions')}</p>
        </div>
      </div>
    </div>
  );
};

export default GameLobby;
