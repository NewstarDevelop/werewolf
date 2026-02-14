import { useRef, useEffect, useCallback, useState } from "react";
import { List, useDynamicRowHeight } from "react-window";
import type { ListImperativeAPI } from "react-window";
import ChatMessage from "./ChatMessage";
import { MessageCircle, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { UIMessage } from "@/hooks/useGameTransformers";

interface ChatLogProps {
  messages: UIMessage[];
  isLoading?: boolean;
}

// Stable empty object to avoid re-renders from rowProps
const EMPTY_ROW_PROPS = {};

const ChatLog = ({ messages, isLoading }: ChatLogProps) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<ListImperativeAPI>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const { t } = useTranslation('common');
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });

  const shouldVirtualize = messages.length > 50;

  // 使用 react-window v2 的动态行高
  const dynamicRowHeight = useDynamicRowHeight({
    defaultRowHeight: 72,
  });

  // 监听容器尺寸变化
  useEffect(() => {
    if (!containerRef.current || !shouldVirtualize) return;
    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setContainerSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, [shouldVirtualize]);

  // Track scroll position for virtualized list
  const handleVirtualScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    const target = event.currentTarget;
    const isNearBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 100;
    isNearBottomRef.current = isNearBottom;
  }, []);

  // P2-3: Smart scroll - only auto-scroll if user is near bottom
  useEffect(() => {
    if (shouldVirtualize && listRef.current) {
      // Only auto-scroll if user is near bottom
      if (isNearBottomRef.current) {
        listRef.current.scrollToRow({ index: messages.length - 1, align: "end" });
      }
    } else if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;

      // Only auto-scroll if user is near bottom (within 100px)
      if (isNearBottom) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }
  }, [messages, shouldVirtualize]);

  // 行渲染组件
  const Row = useCallback(({ index, style }: { index: number; style: React.CSSProperties }) => {
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
  }, [messages]);

  return (
    <div className="flex flex-col h-full glass-panel rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/10 bg-card/40 backdrop-blur-sm">
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
        <div
          ref={containerRef}
          className="flex-1 min-h-0"
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          aria-label={t('ui.game_log')}
        >
          {containerSize.height > 0 && containerSize.width > 0 && (
            <List<object>
              listRef={listRef}
              style={{ height: containerSize.height, width: containerSize.width }}
              rowCount={messages.length}
              rowHeight={dynamicRowHeight}
              rowComponent={Row}
              rowProps={EMPTY_ROW_PROPS}
              onScroll={handleVirtualScroll}
              className="scrollbar-thin p-4"
            />
          )}
        </div>
      ) : (
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 scrollbar-thin"
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          aria-label={t('ui.game_log')}
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
