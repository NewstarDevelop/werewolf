/**
 * VoteResultMessage Component Tests
 *
 * Tests rendering of vote results, abstain counts, and detail toggling.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) => {
      const translations: Record<string, string> = {
        'vote_ui.vote_result': 'Vote Result',
        'vote_ui.hide_details': 'Hide Details',
        'vote_ui.show_details': 'Show Details',
      };
      if (key === 'vote_ui.abstain_count' && opts?.count !== undefined) {
        return `${opts.count} abstained`;
      }
      return translations[key] || key;
    },
    i18n: { language: 'en' },
  }),
}));

// Mock voteUtils
vi.mock('@/utils/voteUtils', () => ({
  formatVoteStats: (stats: { voteCount: Map<number, number> }) => {
    const result: string[] = [];
    stats.voteCount.forEach((count, seat) => {
      result.push(`#${seat}: ${count} votes`);
    });
    return result;
  },
  formatDetailedVotes: () => 'P1→P5, P2→P5, P3→P1',
}));

import VoteResultMessage from './VoteResultMessage';

function createVoteStats(votes: [number, number][], abstainCount = 0) {
  const voteCount = new Map<number, number>(votes);
  return {
    voteCount,
    abstainCount,
    individualVotes: [],
  };
}

describe('VoteResultMessage', () => {
  it('renders vote result header', () => {
    const stats = createVoteStats([[5, 2], [1, 1]]);
    render(<VoteResultMessage voteStats={stats} language="en" />);
    expect(screen.getByText('Vote Result')).toBeInTheDocument();
  });

  it('renders formatted vote stats', () => {
    const stats = createVoteStats([[5, 2], [1, 1]]);
    render(<VoteResultMessage voteStats={stats} language="en" />);
    expect(screen.getByText('#5: 2 votes')).toBeInTheDocument();
    expect(screen.getByText('#1: 1 votes')).toBeInTheDocument();
  });

  it('shows abstain count when > 0', () => {
    const stats = createVoteStats([[5, 2]], 3);
    render(<VoteResultMessage voteStats={stats} language="en" />);
    expect(screen.getByText('3 abstained')).toBeInTheDocument();
  });

  it('hides abstain count when 0', () => {
    const stats = createVoteStats([[5, 2]], 0);
    render(<VoteResultMessage voteStats={stats} language="en" />);
    expect(screen.queryByText(/abstained/)).not.toBeInTheDocument();
  });

  it('toggles detailed votes on button click', () => {
    const stats = createVoteStats([[5, 2]]);
    render(<VoteResultMessage voteStats={stats} language="en" />);

    // Initially details are hidden
    expect(screen.queryByText('P1→P5, P2→P5, P3→P1')).not.toBeInTheDocument();
    expect(screen.getByText('Show Details')).toBeInTheDocument();

    // Click to show details
    fireEvent.click(screen.getByText('Show Details'));
    expect(screen.getByText('P1→P5, P2→P5, P3→P1')).toBeInTheDocument();
    expect(screen.getByText('Hide Details')).toBeInTheDocument();

    // Click to hide details
    fireEvent.click(screen.getByText('Hide Details'));
    expect(screen.queryByText('P1→P5, P2→P5, P3→P1')).not.toBeInTheDocument();
  });
});
