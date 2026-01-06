import { memo } from "react";
import { useTranslation } from "react-i18next";
import { parseVoteResult, isVoteResultMessage } from "@/utils/voteUtils";
import VoteResultMessage from "./VoteResultMessage";

interface ChatMessageProps {
  sender: string;
  message: string;
  isUser: boolean;
  isSystem?: boolean;
  timestamp: string;
  day?: number;
}

const ChatMessage = ({
  sender,
  message,
  isUser,
  isSystem,
  timestamp,
  day,
}: ChatMessageProps) => {
  const { i18n } = useTranslation();

  if (isSystem) {
    // Check if this is a vote result message
    if (isVoteResultMessage(message)) {
      const voteStats = parseVoteResult(message);

      if (voteStats && voteStats.voteCount.size > 0) {
        return <VoteResultMessage voteStats={voteStats} language={i18n.language} />;
      }
    }

    // Regular system message
    return (
      <div className="flex justify-center my-3 animate-fade-in-up">
        <div className="px-4 py-2 rounded-full bg-accent/10 border border-accent/20 text-accent text-sm backdrop-blur-sm shadow-sm">
          {message}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex ${
        isUser ? "justify-end" : "justify-start"
      } mb-3 animate-fade-in-up`}
    >
      <div className={`max-w-[75%] ${isUser ? "order-2" : "order-1"}`}>
        <div
          className={`flex items-center gap-2 mb-1 ${
            isUser ? "justify-end" : "justify-start"
          }`}
        >
          <span
            className={`text-xs font-medium ${
              isUser ? "text-accent" : "text-muted-foreground"
            }`}
          >
            {sender}
          </span>
          {timestamp && (
            <span className="text-xs text-muted-foreground/60">{timestamp}</span>
          )}
        </div>
        <div
          className={`px-4 py-2.5 rounded-2xl transition-colors ${
            isUser
              ? "bg-accent/20 border border-accent/30 rounded-br-md shadow-[var(--shadow-message-user)]"
              : "bg-muted/80 border border-white/5 rounded-bl-md backdrop-blur-sm"
          }`}
        >
          <p className="text-sm text-foreground/90 leading-relaxed">{message}</p>
        </div>
      </div>
    </div>
  );
};

export default memo(ChatMessage);
