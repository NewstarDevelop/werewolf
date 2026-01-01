import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Info, AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { authorizedFetch } from "@/services/api";

interface LogEntry {
  timestamp: number;
  level: string;
  message: string;
  module: string;
}

interface LogPanelProps {
  gameId: string;
  isOpen: boolean;
  onClose: () => void;
}

const LogPanel = ({ gameId, isOpen, onClose }: LogPanelProps) => {
  const { t } = useTranslation('common');

  const { data, isLoading } = useQuery({
    queryKey: ['gameLogs', gameId],
    queryFn: () => authorizedFetch<{ logs: LogEntry[] }>(`/api/game/${gameId}/logs`),
    enabled: isOpen && !!gameId,
    refetchInterval: isOpen ? 2000 : false, // Refresh every 2s when open
  });

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'ERROR':
        return <AlertCircle className="w-3 h-3 text-red-400" />;
      case 'WARNING':
        return <AlertTriangle className="w-3 h-3 text-yellow-400" />;
      default:
        return <Info className="w-3 h-3 text-blue-400" />;
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'text-red-400';
      case 'WARNING':
        return 'text-yellow-400';
      default:
        return 'text-foreground';
    }
  };

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[500px] sm:w-[600px]">
        <SheetHeader>
          <SheetTitle>{t('logs.title')}</SheetTitle>
        </SheetHeader>

        <ScrollArea className="h-[calc(100vh-80px)] mt-4">
          {isLoading ? (
            <div className="text-center text-muted-foreground py-8">
              {t('logs.loading')}
            </div>
          ) : data?.logs && data.logs.length > 0 ? (
            <div className="space-y-2">
              {data.logs.map((log, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg bg-secondary/30 border border-border text-xs font-mono"
                >
                  <div className="flex items-center gap-2 mb-1">
                    {getLevelIcon(log.level)}
                    <span className="text-muted-foreground">
                      {new Date(log.timestamp * 1000).toLocaleTimeString()}
                    </span>
                    <span className="text-accent text-[10px]">
                      {log.module}
                    </span>
                  </div>
                  <div className={getLevelColor(log.level)}>
                    {log.message}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-8">
              {t('logs.no_logs')}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
};

export default LogPanel;
