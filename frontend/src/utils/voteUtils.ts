/**
 * Vote Result Utilities
 *
 * Parses and formats vote result messages from backend.
 */

export interface VoteStats {
  /** Seat ID -> Vote count mapping */
  voteCount: Map<number, number>;
  /** Abstain count */
  abstainCount: number;
  /** Original individual votes for reference */
  individualVotes: Array<{ voter: number; target: number | null }>;
}

/**
 * Parse vote result message from backend
 *
 * @param message - System message like "投票结果：1号投5号，2号投5号，3号投1号，4号弃票"
 * @returns VoteStats object or null if message is not a vote result
 *
 * @example
 * parseVoteResult("投票结果：1号投5号，2号投5号，3号投1号")
 * // Returns: { voteCount: Map([[5, 2], [1, 1]]), abstainCount: 0, ... }
 */
export function parseVoteResult(message: string): VoteStats | null {
  // Check if message is a vote result
  if (!message.startsWith("投票结果：") && !message.startsWith("Vote Result:")) {
    return null;
  }

  // Remove prefix
  const content = message.replace(/^投票结果：|^Vote Result:\s*/, "");

  // Split by Chinese comma or regular comma
  const votes = content.split(/[，,]/).map(v => v.trim()).filter(v => v);

  const voteCount = new Map<number, number>();
  let abstainCount = 0;
  const individualVotes: Array<{ voter: number; target: number | null }> = [];

  // Parse each vote
  for (const vote of votes) {
    // Match pattern: "X号投Y号" or "X号弃票"
    const voteMatch = vote.match(/(\d+)号投(\d+)号/);
    const abstainMatch = vote.match(/(\d+)号弃票/);

    if (voteMatch) {
      const voter = parseInt(voteMatch[1]);
      const target = parseInt(voteMatch[2]);

      individualVotes.push({ voter, target });

      // Count votes for target
      voteCount.set(target, (voteCount.get(target) || 0) + 1);
    } else if (abstainMatch) {
      const voter = parseInt(abstainMatch[1]);
      individualVotes.push({ voter, target: null });
      abstainCount++;
    }
  }

  return {
    voteCount,
    abstainCount,
    individualVotes,
  };
}

/**
 * Format vote statistics for display
 *
 * @param stats - Parsed vote statistics
 * @param language - Current language ("zh" or "en")
 * @returns Array of formatted strings like ["5号(2票)", "1号(1票)"]
 *
 * @example
 * formatVoteStats({ voteCount: Map([[5, 2], [1, 1]]), ... }, "zh")
 * // Returns: ["5号(2票)", "1号(1票)"]
 */
export function formatVoteStats(stats: VoteStats, language: string = "zh"): string[] {
  const formatted: string[] = [];

  // Sort by vote count (descending), then by seat ID (ascending)
  const sortedEntries = Array.from(stats.voteCount.entries()).sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1]; // Sort by count descending
    return a[0] - b[0]; // Sort by seat ID ascending
  });

  for (const [seatId, count] of sortedEntries) {
    if (language === "zh") {
      formatted.push(`${seatId}号(${count}票)`);
    } else {
      formatted.push(`#${seatId} (${count} vote${count > 1 ? "s" : ""})`);
    }
  }

  return formatted;
}

/**
 * Check if a message is a vote result message
 *
 * @param message - Message text to check
 * @returns true if message is a vote result
 */
export function isVoteResultMessage(message: string): boolean {
  return message.startsWith("投票结果：") || message.startsWith("Vote Result:");
}

/**
 * Format detailed individual votes for display
 *
 * @param stats - Parsed vote statistics
 * @param language - Current language ("zh" or "en")
 * @returns Formatted string like "1号→5号、2号→5号、3号弃票"
 *
 * @example
 * formatDetailedVotes({ individualVotes: [{voter: 1, target: 5}, {voter: 2, target: 5}] }, "zh")
 * // Returns: "1号→5号、2号→5号"
 */
export function formatDetailedVotes(stats: VoteStats, language: string = "zh"): string {
  const formatted: string[] = [];

  for (const vote of stats.individualVotes) {
    if (vote.target !== null) {
      if (language === "zh") {
        formatted.push(`${vote.voter}号→${vote.target}号`);
      } else {
        formatted.push(`#${vote.voter}→#${vote.target}`);
      }
    } else {
      if (language === "zh") {
        formatted.push(`${vote.voter}号弃票`);
      } else {
        formatted.push(`#${vote.voter} abstained`);
      }
    }
  }

  return formatted.join(language === "zh" ? "、" : ", ");
}
