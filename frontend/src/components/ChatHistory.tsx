import { useEffect, useMemo, useRef, useState } from "react";

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

type ChatFilter = "all" | ChatEntry["kind"];

const chatFilterOptions: Array<{
  value: ChatFilter;
  label: string;
}> = [
  { value: "all", label: "全部" },
  { value: "speech", label: chatTagCopy.speech },
  { value: "private", label: chatTagCopy.private },
  { value: "system", label: chatTagCopy.system },
];

export function ChatHistory({ entries }: ChatHistoryProps) {
  const bottomRef = useRef<HTMLLIElement | null>(null);
  const [filter, setFilter] = useState<ChatFilter>("all");
  const visibleEntries = useMemo(
    () => (
      filter === "all"
        ? entries
        : entries.filter((entry) => entry.kind === filter)
    ),
    [entries, filter],
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [visibleEntries]);

  return (
    <section className="chat-section" aria-labelledby="chat-section-title">
      <header className="chat-section-header">
        <h2 id="chat-section-title">对局日志</h2>
        <div className="chat-section-tools">
          <div className="chat-filter" role="group" aria-label="日志筛选">
            {chatFilterOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={filter === option.value ? "chat-filter__button is-active" : "chat-filter__button"}
                aria-pressed={filter === option.value}
                onClick={() => setFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="chat-section-stats">
            {entries.length === 0 ? "暂无消息" : `${visibleEntries.length}/${entries.length} 条`}
          </p>
        </div>
      </header>
      <ol className="chat-feed" aria-label="对局日志列表" aria-live="polite" aria-relevant="additions">
        {visibleEntries.map((entry) => (
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
