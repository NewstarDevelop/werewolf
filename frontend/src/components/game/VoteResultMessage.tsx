import { useState } from "react";
import { useTranslation } from "react-i18next";
import { formatVoteStats, formatDetailedVotes, VoteStats } from "@/utils/voteUtils";

interface VoteResultMessageProps {
  voteStats: VoteStats;
  language: string;
}

/**
 * VoteResultMessage Component
 *
 * Displays voting results with statistics and expandable detailed votes.
 * Extracted from ChatMessage to optimize state management.
 */
const VoteResultMessage = ({ voteStats, language }: VoteResultMessageProps) => {
  const [showDetails, setShowDetails] = useState(false);
  const { t } = useTranslation('game');

  const formattedVotes = formatVoteStats(voteStats, language);

  return (
    <div className="flex justify-center my-3 animate-slide-up">
      <div className="flex flex-col items-center gap-2 px-4 py-3 rounded-lg bg-accent/10 border border-accent/20">
        {/* Vote Result Header */}
        <div className="text-accent text-sm font-medium">
          {t('vote_ui.vote_result')}
        </div>

        {/* Vote Stats - Horizontal Layout */}
        <div className="flex flex-row flex-wrap gap-2 justify-center">
          {formattedVotes.map((vote, index) => (
            <div
              key={index}
              className="px-3 py-1 rounded-full bg-accent/20 border border-accent/30 text-accent text-sm font-semibold"
            >
              {vote}
            </div>
          ))}
        </div>

        {/* Abstain count if any */}
        {voteStats.abstainCount > 0 && (
          <div className="text-xs text-muted-foreground">
            {t('vote_ui.abstain_count', { count: voteStats.abstainCount })}
          </div>
        )}

        {/* Toggle Details Button */}
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-xs text-accent/70 hover:text-accent transition-colors flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:rounded-sm"
        >
          {showDetails
            ? t('vote_ui.hide_details')
            : t('vote_ui.show_details')
          }
          <span className={`transition-transform ${showDetails ? "rotate-180" : ""}`}>▼</span>
        </button>

        {/* Detailed Votes - Expandable */}
        {showDetails && (
          <div className="w-full pt-2 border-t border-accent/10">
            <div className="text-xs text-muted-foreground text-center">
              {formatDetailedVotes(voteStats, language)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default VoteResultMessage;
