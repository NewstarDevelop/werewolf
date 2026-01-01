import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useQuery } from "@tanstack/react-query";
import { Brain, Users, MessageSquare } from "lucide-react";
import { MessageInGame, authorizedFetch } from "@/services/api";
import { useTranslation } from "react-i18next";

interface DebugPanelProps {
  gameId: string;
  isOpen: boolean;
  onClose: () => void;
}

const DebugPanel = ({ gameId, isOpen, onClose }: DebugPanelProps) => {
  const { t } = useTranslation('common');

  const { data, isLoading } = useQuery({
    queryKey: ['debugMessages', gameId],
    queryFn: () => authorizedFetch<{ messages: MessageInGame[] }>(`/api/game/${gameId}/debug-messages`),
    enabled: isOpen && !!gameId,
    refetchInterval: isOpen ? 2000 : false, // Refresh every 2s when open
  });

  const getMessageTypeIcon = (type: string) => {
    switch (type) {
      case 'vote_thought':
        return <Brain className="w-3 h-3 text-purple-400" />;
      case 'wolf_chat':
        return <Users className="w-3 h-3 text-red-400" />;
      default:
        return <MessageSquare className="w-3 h-3 text-blue-400" />;
    }
  };

  const getMessageTypeColor = (type: string) => {
    switch (type) {
      case 'vote_thought':
        return 'text-purple-400';
      case 'wolf_chat':
        return 'text-red-400';
      case 'system':
        return 'text-muted-foreground';
      default:
        return 'text-foreground';
    }
  };

  const getMessageTypeLabel = (type: string) => {
    return t(`message_type.${type}`, { defaultValue: type });
  };

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[500px] sm:w-[600px]">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-purple-400" />
            {t('ui.ai_debug')}
          </SheetTitle>
        </SheetHeader>

        <ScrollArea className="h-[calc(100vh-80px)] mt-4">
          {isLoading ? (
            <div className="text-center text-muted-foreground py-8 text-base">
              {t('app.loading')}
            </div>
          ) : data?.messages && data.messages.length > 0 ? (
            <div className="space-y-3">
              {data.messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`p-4 rounded-lg border ${
                    msg.type === 'vote_thought'
                      ? 'bg-purple-500/10 border-purple-500/30'
                      : msg.type === 'wolf_chat'
                      ? 'bg-red-500/10 border-red-500/30'
                      : 'bg-secondary/30 border-border'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    {getMessageTypeIcon(msg.type)}
                    <span className="font-semibold text-accent text-sm">
                      {msg.seat_id === 0 ? t('player.system') : t('player.seat', { id: msg.seat_id })}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      [{getMessageTypeLabel(msg.type)}]
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {t('player.day', { count: msg.day })}
                    </span>
                  </div>
                  <div className={`${getMessageTypeColor(msg.type)} whitespace-pre-wrap text-sm leading-relaxed font-sans`}>
                    {msg.text}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-8 text-base">
              {t('player.no_messages')}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
};

export default DebugPanel;
