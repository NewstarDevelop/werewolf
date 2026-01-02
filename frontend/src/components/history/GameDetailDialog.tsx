import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Clock, Users, Trophy } from 'lucide-react';
import { useGameHistoryDetail } from '@/hooks/useGameHistory';

interface GameDetailDialogProps {
  gameId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GameDetailDialog({ gameId, open, onOpenChange }: GameDetailDialogProps) {
  const { t } = useTranslation('common');
  const { data: game, isLoading } = useGameHistoryDetail(gameId);

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}${t('history.hours')} ${minutes}${t('history.minutes')}`;
    }
    return `${minutes}${t('history.minutes')}`;
  };

  const getWinnerText = (winner: string) => {
    if (winner === 'werewolf') return t('history.winner_werewolf');
    if (winner === 'villager') return t('history.winner_villager');
    return winner;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>{t('history.game_detail')}</DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="py-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-4"></div>
            <p className="text-muted-foreground">{t('common.loading')}</p>
          </div>
        ) : game ? (
          <ScrollArea className="max-h-[60vh]">
            <div className="space-y-6 pr-4">
              {/* Game Info */}
              <div className="bg-card/30 border border-border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">{game.room_name}</h3>
                  <Badge variant={game.is_winner ? 'default' : 'secondary'}>
                    {game.is_winner ? <Trophy className="w-3 h-3 mr-1" /> : null}
                    {getWinnerText(game.winner)}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">{t('history.game_time')}</span>
                    <p className="font-medium">
                      <Clock className="w-3 h-3 inline mr-1" />
                      {format(new Date(game.finished_at), 'yyyy-MM-dd HH:mm')}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('history.duration')}</span>
                    <p className="font-medium">{formatDuration(game.duration_seconds)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('history.my_role')}</span>
                    <p className="font-medium">{game.my_role}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">
                      <Users className="w-3 h-3 inline mr-1" />
                      {t('room.player_count')}
                    </span>
                    <p className="font-medium">{game.player_count}</p>
                  </div>
                </div>
              </div>

              {/* Players List */}
              <div>
                <h4 className="text-sm font-semibold mb-3">{t('history.players')}</h4>
                <div className="space-y-2">
                  {game.players.map((player, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between bg-card/30 border border-border rounded-lg p-3"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-muted-foreground w-6">#{index + 1}</span>
                        <span className="font-medium">{player.nickname}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">{player.role}</span>
                        {player.is_winner && (
                          <Badge variant="default" className="text-xs">
                            <Trophy className="w-3 h-3 mr-1" />
                            {t('history.winner')}
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </ScrollArea>
        ) : (
          <div className="py-12 text-center">
            <p className="text-muted-foreground">{t('history.no_data')}</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
