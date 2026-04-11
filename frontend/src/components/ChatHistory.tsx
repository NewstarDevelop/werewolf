import { useEffect, useRef } from "react";

export interface ChatEntry {
  id: string;
  kind: "system" | "private" | "speech";
  message: string;
  speaker?: string;
}

interface ChatHistoryProps {
  entries: ChatEntry[];
}

const tagText: Record<ChatEntry["kind"], string> = {
  system: "系统",
  private: "私信",
  speech: "发言",
};

export function ChatHistory({ entries }: ChatHistoryProps) {
  const bottomRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [entries]);

  return (
    <section className="chat-panel" aria-labelledby="chat-panel-title">
      <div className="panel-header">
        <p className="panel-kicker">Log Feed</p>
        <div>
          <h2 id="chat-panel-title">对局日志</h2>
          <p className="panel-copy">区分系统播报、私人信息和玩家发言，保持底部追踪。</p>
        </div>
      </div>
      <ol className="chat-feed" aria-label="对局日志列表">
        {entries.map((entry) => (
          <li key={entry.id} className={`chat-row is-${entry.kind}`}>
            <div className="chat-meta">
              <span className="chat-tag">{tagText[entry.kind]}</span>
              <strong>{entry.speaker ?? "系统播报"}</strong>
            </div>
            <p>{entry.message}</p>
          </li>
        ))}
        <li ref={bottomRef} aria-hidden="true" className="chat-anchor" />
      </ol>
    </section>
  );
}
