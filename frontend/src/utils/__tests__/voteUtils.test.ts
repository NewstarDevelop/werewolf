/**
 * voteUtils Tests
 *
 * Tests vote result parsing, formatting, and display logic.
 */
import { describe, it, expect } from 'vitest';
import {
  parseVoteResult,
  formatVoteStats,
  isVoteResultMessage,
  formatDetailedVotes,
  VoteStats,
} from '../voteUtils';

// ============================================================================
// parseVoteResult
// ============================================================================

describe('parseVoteResult', () => {
  it('parses Chinese vote result message', () => {
    const result = parseVoteResult('投票结果：1号投5号，2号投5号，3号投1号');
    expect(result).not.toBeNull();
    expect(result!.voteCount.get(5)).toBe(2);
    expect(result!.voteCount.get(1)).toBe(1);
    expect(result!.abstainCount).toBe(0);
    expect(result!.individualVotes).toHaveLength(3);
  });

  it('parses English vote result message', () => {
    const result = parseVoteResult('Vote Result: 1号投5号，2号投5号');
    expect(result).not.toBeNull();
    expect(result!.voteCount.get(5)).toBe(2);
  });

  it('handles abstain votes', () => {
    const result = parseVoteResult('投票结果：1号投5号，2号弃票，3号弃票');
    expect(result).not.toBeNull();
    expect(result!.abstainCount).toBe(2);
    expect(result!.individualVotes[1].target).toBeNull();
  });

  it('returns null for non-vote messages', () => {
    expect(parseVoteResult('Hello world')).toBeNull();
    expect(parseVoteResult('天亮了')).toBeNull();
    expect(parseVoteResult('')).toBeNull();
  });

  it('handles all abstain votes', () => {
    const result = parseVoteResult('投票结果：1号弃票，2号弃票，3号弃票');
    expect(result).not.toBeNull();
    expect(result!.voteCount.size).toBe(0);
    expect(result!.abstainCount).toBe(3);
  });

  it('handles single vote', () => {
    const result = parseVoteResult('投票结果：1号投3号');
    expect(result).not.toBeNull();
    expect(result!.voteCount.get(3)).toBe(1);
    expect(result!.individualVotes).toHaveLength(1);
  });

  it('correctly tracks individual voter-target pairs', () => {
    const result = parseVoteResult('投票结果：4号投7号，5号投7号');
    expect(result).not.toBeNull();
    expect(result!.individualVotes[0]).toEqual({ voter: 4, target: 7 });
    expect(result!.individualVotes[1]).toEqual({ voter: 5, target: 7 });
  });
});

// ============================================================================
// formatVoteStats
// ============================================================================

describe('formatVoteStats', () => {
  function makeStats(counts: [number, number][], abstain = 0): VoteStats {
    return {
      voteCount: new Map(counts),
      abstainCount: abstain,
      individualVotes: [],
    };
  }

  it('formats Chinese vote stats', () => {
    const result = formatVoteStats(makeStats([[5, 3], [1, 1]]), 'zh');
    expect(result).toEqual(['5号(3票)', '1号(1票)']);
  });

  it('formats English vote stats with pluralization', () => {
    const result = formatVoteStats(makeStats([[5, 3], [1, 1]]), 'en');
    expect(result).toEqual(['#5 (3 votes)', '#1 (1 vote)']);
  });

  it('sorts by vote count descending, then seat ascending', () => {
    const result = formatVoteStats(makeStats([[3, 2], [1, 2], [7, 1]]), 'zh');
    expect(result).toEqual(['1号(2票)', '3号(2票)', '7号(1票)']);
  });

  it('returns empty array for no votes', () => {
    expect(formatVoteStats(makeStats([]), 'zh')).toEqual([]);
  });
});

// ============================================================================
// isVoteResultMessage
// ============================================================================

describe('isVoteResultMessage', () => {
  it('detects Chinese vote result prefix', () => {
    expect(isVoteResultMessage('投票结果：1号投5号')).toBe(true);
  });

  it('detects English vote result prefix', () => {
    expect(isVoteResultMessage('Vote Result: 1号投5号')).toBe(true);
  });

  it('rejects non-vote messages', () => {
    expect(isVoteResultMessage('Hello')).toBe(false);
    expect(isVoteResultMessage('')).toBe(false);
    expect(isVoteResultMessage('投票中...')).toBe(false);
  });
});

// ============================================================================
// formatDetailedVotes
// ============================================================================

describe('formatDetailedVotes', () => {
  function makeStats(votes: Array<{ voter: number; target: number | null }>): VoteStats {
    return {
      voteCount: new Map(),
      abstainCount: 0,
      individualVotes: votes,
    };
  }

  it('formats Chinese detailed votes', () => {
    const result = formatDetailedVotes(
      makeStats([
        { voter: 1, target: 5 },
        { voter: 2, target: 5 },
      ]),
      'zh',
    );
    expect(result).toBe('1号→5号、2号→5号');
  });

  it('formats English detailed votes', () => {
    const result = formatDetailedVotes(
      makeStats([
        { voter: 1, target: 5 },
        { voter: 2, target: 5 },
      ]),
      'en',
    );
    expect(result).toBe('#1→#5, #2→#5');
  });

  it('formats abstain in Chinese', () => {
    const result = formatDetailedVotes(
      makeStats([{ voter: 3, target: null }]),
      'zh',
    );
    expect(result).toBe('3号弃票');
  });

  it('formats abstain in English', () => {
    const result = formatDetailedVotes(
      makeStats([{ voter: 3, target: null }]),
      'en',
    );
    expect(result).toBe('#3 abstained');
  });

  it('mixes votes and abstains', () => {
    const result = formatDetailedVotes(
      makeStats([
        { voter: 1, target: 5 },
        { voter: 2, target: null },
      ]),
      'zh',
    );
    expect(result).toBe('1号→5号、2号弃票');
  });

  it('returns empty string for no votes', () => {
    expect(formatDetailedVotes(makeStats([]), 'zh')).toBe('');
  });
});
