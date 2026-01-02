import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Users, Clock, Trophy } from 'lucide-react';
import type { GameHistoryItem } from '@/services/gameHistoryApi';

interface GameHistoryCardProps {
  game: GameHistoryItem;
  onViewDetail: (gameId: string) => void;
}

export function GameHistoryCard({ game, onViewDetail }: GameHistoryCardProps) {
  const { t } = useTranslation('common');

  const getWinnerBadgeColor = (winner: string, isWinner: boolean) => {
    if (!isWinner) return 'secondary';
    return winner === 'werewolf' ? 'destructive' : 'default';
  };

  const getWinnerText = (winner: string) => {
    if (winner === 'werewolf') return t('history.winner_werewolf');
    if (winner === 'villager') return t('history.winner_villager');
    return winner;
  };

  return (
    <Card className="bg-card/50 border-border hover:border-accent transition-colors backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg">{game.room_name}</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              <Clock className="w-3 h-3 inline mr-1" />
              {format(new Date(game.finished_at), 'yyyy-MM-dd HH:mm')}
            </p>
          </div>
          <Badge variant={getWinnerBadgeColor(game.winner, game.is_winner)}>
            {game.is_winner ? <Trophy className="w-3 h-3 mr-1" /> : null}
            {getWinnerText(game.winner)}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{t('history.my_role')}</span>
            <span className="text-foreground font-semibold">{game.my_role}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              <Users className="w-3 h-3 inline mr-1" />
              {t('room.player_count')}
            </span>
            <span className="text-foreground font-semibold">{game.player_count}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="w-full mt-2"
            onClick={() => onViewDetail(game.game_id)}
          >
            {t('history.view_detail')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
