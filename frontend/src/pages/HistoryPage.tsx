import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { GameHistoryList } from '@/components/history/GameHistoryList';
import { HistoryFilters } from '@/components/history/HistoryFilters';
import { GameDetailDialog } from '@/components/history/GameDetailDialog';
import { useGameHistory } from '@/hooks/useGameHistory';

export default function HistoryPage() {
  const { t } = useTranslation('common');
  const [selectedWinner, setSelectedWinner] = useState<string | undefined>(undefined);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);

  const pageSize = 20;
  const { data, isLoading, error } = useGameHistory(
    selectedWinner as 'werewolf' | 'villager' | undefined,
    currentPage,
    pageSize
  );

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  const handleWinnerChange = (winner: string | undefined) => {
    setSelectedWinner(winner);
    setCurrentPage(1);
  };

  const handleViewDetail = (gameId: string) => {
    setSelectedGameId(gameId);
  };

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-full relative">
      <div className="fixed inset-0 atmosphere-night z-0 pointer-events-none" />
      <div className="fixed inset-0 atmosphere-moonlight z-0 opacity-40 pointer-events-none" />

      <div className="relative z-10 max-w-5xl mx-auto px-4 py-6 md:py-10 animate-fade-in">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground font-display tracking-tight">
            {t('history.title')}
          </h1>
          <p className="text-muted-foreground mt-1">{t('history.my_games')}</p>
        </div>

        {/* Error State */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/30 rounded-xl p-4 mb-6 animate-fade-in">
            <p className="text-destructive text-center text-sm">
              {t('common.error')}: {error instanceof Error ? error.message : String(error)}
            </p>
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar - Filters */}
          <div className="lg:col-span-1">
            <HistoryFilters
              selectedWinner={selectedWinner}
              onWinnerChange={handleWinnerChange}
            />
          </div>

          {/* Games List */}
          <div className="lg:col-span-3">
            <div className="mb-4">
              <p className="text-sm text-muted-foreground">
                {data && data.total > 0
                  ? t('history.page_info', { page: currentPage, total: data.total })
                  : t('history.no_games')}
              </p>
            </div>

            <GameHistoryList
              games={data?.games || []}
              isLoading={isLoading}
              onViewDetail={handleViewDetail}
            />

            {/* Pagination */}
            {data && totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-8">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePreviousPage}
                  disabled={currentPage === 1}
                  className="border-border/40 hover:border-accent/50"
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  {t('common.previous')}
                </Button>
                <span className="text-sm text-muted-foreground tabular-nums">
                  {t('common.page_of', { current: currentPage, total: totalPages })}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNextPage}
                  disabled={currentPage === totalPages}
                  className="border-border/40 hover:border-accent/50"
                >
                  {t('common.next')}
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Game Detail Dialog */}
      <GameDetailDialog
        gameId={selectedGameId}
        open={!!selectedGameId}
        onOpenChange={(open) => !open && setSelectedGameId(null)}
      />
    </div>
  );
}
