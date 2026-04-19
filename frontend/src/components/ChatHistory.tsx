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
    <section className="chat-panel" aria-labelledby="chat-panel-title">
      <header className="panel-header">
        <h2 id="chat-panel-title">对局日志</h2>
        <p className="panel-stats">
          {entries.length === 0 ? "暂无消息" : `共 ${entries.length} 条`}
        </p>
      </header>
      <ol className="chat-feed" aria-label="对局日志列表" aria-live="polite" aria-relevant="additions">
        {entries.map((entry, index) => (
          <li key={entry.id} className={`chat-row is-${entry.kind}`}>
            <div className="chat-meta">
              <div className="chat-badges">
                <span className="chat-tag">{chatTagCopy[entry.kind]}</span>
                <strong className="chat-speaker">{entry.speaker ?? narratorSpeaker}</strong>
              </div>
              <span className="chat-index">#{index + 1}</span>
            </div>
            <p>{entry.message}</p>
          </li>
        ))}
        <li ref={bottomRef} aria-hidden="true" className="chat-anchor" />
      </ol>
    </section>
  );
}
