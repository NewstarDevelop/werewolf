import { useTranslation } from 'react-i18next';
import { GameHistoryCard } from './GameHistoryCard';
import type { GameHistoryItem } from '@/services/gameHistoryApi';

interface GameHistoryListProps {
  games: GameHistoryItem[];
  isLoading: boolean;
  onViewDetail: (gameId: string) => void;
}

export function GameHistoryList({ games, isLoading, onViewDetail }: GameHistoryListProps) {
  const { t } = useTranslation('common');

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="h-48 rounded-lg bg-card/50 border border-border animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (games.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground text-lg">{t('history.no_games')}</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {games.map((game) => (
        <GameHistoryCard
          key={game.game_id}
          game={game}
          onViewDetail={onViewDetail}
        />
      ))}
    </div>
  );
}
