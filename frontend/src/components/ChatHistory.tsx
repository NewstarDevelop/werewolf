import { useEffect, useRef } from "react";

import { chatTagCopy, narratorSpeaker } from "../copy";

export interface ChatEntry {
  id: string;
  kind: "system" | "private" | "speech";
  message: string;
  speaker?: string;
}

interface ChatHistoryProps {
  entries: ChatEntry[];
}

export function ChatHistory({ entries }: ChatHistoryProps) {
  const bottomRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [entries]);

  return (
    <section className="chat-section" aria-labelledby="chat-section-title">
      <header className="chat-section-header">
        <h2 id="chat-section-title">对局日志</h2>
        <p className="chat-section-stats">
          {entries.length === 0 ? "暂无消息" : `共 ${entries.length} 条`}
        </p>
      </header>
      <ol className="chat-feed" aria-label="对局日志列表" aria-live="polite" aria-relevant="additions">
        {entries.map((entry) => (
          <li key={entry.id} className={`chat-row is-${entry.kind}`}>
            <div className="chat-meta">
              <div className="chat-badges">
                <span className="chat-tag">{chatTagCopy[entry.kind]}</span>
                <strong className="chat-speaker">{entry.speaker ?? narratorSpeaker}</strong>
              </div>
            </div>
            <p>{entry.message}</p>
          </li>
        ))}
        <li ref={bottomRef} aria-hidden="true" className="chat-anchor" />
      </ol>
    </section>
  );
}
