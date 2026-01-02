/**
 * useGameHistory Hook - React Query hook for game history data
 */
import { useQuery } from '@tanstack/react-query';
import { getGameHistory, getGameHistoryDetail } from '@/services/gameHistoryApi';

export function useGameHistory(
  winner?: 'werewolf' | 'villager',
  page: number = 1,
  pageSize: number = 20
) {
  return useQuery({
    queryKey: ['gameHistory', winner, page, pageSize],
    queryFn: () => getGameHistory(winner, page, pageSize),
    staleTime: 60000, // 1 minute
  });
}

export function useGameHistoryDetail(gameId: string | null) {
  return useQuery({
    queryKey: ['gameHistoryDetail', gameId],
    queryFn: () => getGameHistoryDetail(gameId!),
    enabled: !!gameId,
    staleTime: 300000, // 5 minutes
  });
}
