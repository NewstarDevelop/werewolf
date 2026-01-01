import { useRef, useEffect } from "react";
import { List, useListRef } from "react-window";
import { AutoSizer } from "react-virtualized-auto-sizer";
import ChatMessage from "./ChatMessage";
import { MessageCircle, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

interface Message {
  id: number;
  sender: string;
  message: string;
  isUser: boolean;
  isSystem?: boolean;
  timestamp: string;
  day?: number;
}

interface ChatLogProps {
  messages: Message[];
  isLoading?: boolean;
}

const ChatLog = ({ messages, isLoading }: ChatLogProps) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const listRef = useListRef();
  const { t } = useTranslation('common');

  const shouldVirtualize = messages.length > 50;

  // P2-3: Smart scroll - only auto-scroll if user is near bottom
  useEffect(() => {
    if (shouldVirtualize && listRef.current) {
      // Auto-scroll virtualized list to bottom
      listRef.current.scrollToRow(messages.length - 1, "end");
    } else if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;

      // Only auto-scroll if user is near bottom (within 100px)
      if (isNearBottom) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }
  }, [messages, shouldVirtualize]);

  return (
    <div className="flex flex-col h-full bg-card/50 rounded-xl border border-border overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-muted/30">
        <MessageCircle className="w-4 h-4 text-accent" />
        <h2 className="font-display text-sm uppercase tracking-wider text-foreground">
          {t('ui.game_log')}
        </h2>
        <span className="ml-auto text-xs text-muted-foreground">
          {t('player.messages_count', { count: messages.length })}
        </span>
        {isLoading && (
          <Loader2 className="w-4 h-4 text-accent animate-spin" />
        )}
      </div>

      {/* Messages */}
      {messages.length === 0 ? (
        <div className="flex items-center justify-center flex-1 text-muted-foreground text-sm">
          {t('player.waiting')}
        </div>
      ) : shouldVirtualize ? (
        <div className="flex-1">
          <AutoSizer>
            {({ height, width }) => (
              <List
                listRef={listRef}
                defaultHeight={height}
                defaultWidth={width}
                rowCount={messages.length}
                rowHeight={80}
                rowComponent={({ index, style }) => {
                  const msg = messages[index];
                  return (
                    <div style={style}>
                      <ChatMessage
                        sender={msg.sender}
                        message={msg.message}
                        isUser={msg.isUser}
                        isSystem={msg.isSystem}
                        timestamp={msg.timestamp}
                        day={msg.day}
                      />
                    </div>
                  );
                }}
                className="p-4 scrollbar-thin"
              />
            )}
          </AutoSizer>
        </div>
      ) : (
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 scrollbar-thin"
        >
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              sender={msg.sender}
              message={msg.message}
              isUser={msg.isUser}
              isSystem={msg.isSystem}
              timestamp={msg.timestamp}
              day={msg.day}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default ChatLog;
