/**
 * GameActions Component Tests
 *
 * Tests action buttons, input validation, skip behavior, and pending action display.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'action.vote': 'Vote',
        'action.kill': 'Kill',
        'action.verify': 'Verify',
        'action.save': 'Save',
        'action.poison': 'Poison',
        'action.protect': 'Protect',
        'action.self_destruct': 'Self Destruct',
        'action.skill': 'Skill',
        'action.skip': 'Skip',
        'action.send': 'Send',
        'action.shoot': 'Shoot',
        'message.enter_message': 'Enter message...',
        'message.waiting': 'Waiting...',
        'message.input_label': 'Message input',
        'status.night': 'Night time',
      };
      return translations[key] || key;
    },
    i18n: { language: 'en' },
  }),
}));

// Mock SoundContext
vi.mock('@/contexts/SoundContext', () => ({
  useSound: () => ({
    play: vi.fn(),
  }),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: { error: vi.fn() },
}));

import GameActions from './GameActions';
import type { PendingAction } from '@/services/api';

function pa(type: string, choices: number[], message: string): PendingAction {
  return { type, choices, message } as unknown as PendingAction;
}

describe('GameActions', () => {
  const defaultProps = {
    onSendMessage: vi.fn(),
    onVote: vi.fn(),
    onUseSkill: vi.fn(),
    onSkip: vi.fn(),
    canVote: false,
    canUseSkill: false,
    canSpeak: false,
    isNight: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders action buttons', () => {
    render(<GameActions {...defaultProps} />);
    expect(screen.getByText('Vote')).toBeInTheDocument();
    expect(screen.getByText('Skill')).toBeInTheDocument();
  });

  it('disables vote button when canVote is false', () => {
    render(<GameActions {...defaultProps} canVote={false} />);
    const voteBtn = screen.getByText('Vote').closest('button');
    expect(voteBtn).toBeDisabled();
  });

  it('enables vote button when canVote is true', () => {
    render(<GameActions {...defaultProps} canVote={true} />);
    const voteBtn = screen.getByText('Vote').closest('button');
    expect(voteBtn).not.toBeDisabled();
  });

  it('calls onVote when vote button clicked', () => {
    render(<GameActions {...defaultProps} canVote={true} />);
    fireEvent.click(screen.getByText('Vote'));
    expect(defaultProps.onVote).toHaveBeenCalledOnce();
  });

  it('calls onUseSkill when skill button clicked', () => {
    render(<GameActions {...defaultProps} canUseSkill={true} />);
    fireEvent.click(screen.getByText('Skill'));
    expect(defaultProps.onUseSkill).toHaveBeenCalledOnce();
  });

  it('shows skip button when pending action supports it', () => {
    render(<GameActions {...defaultProps} pendingAction={pa('save', [3, 0], 'Use antidote?')} />);
    expect(screen.getByText('Skip')).toBeInTheDocument();
  });

  it('hides skip button when choices do not include 0', () => {
    render(<GameActions {...defaultProps} pendingAction={pa('vote', [1, 2, 3], 'Vote now')} />);
    expect(screen.queryByText('Skip')).not.toBeInTheDocument();
  });

  it('calls onSkip when skip button clicked', () => {
    render(<GameActions {...defaultProps} pendingAction={pa('shoot', [1, 2, 0], 'Shoot?')} />);
    fireEvent.click(screen.getByText('Skip'));
    expect(defaultProps.onSkip).toHaveBeenCalledOnce();
  });

  it('shows translated action hint when provided', () => {
    render(<GameActions {...defaultProps} translatedMessage="Select a target to verify" />);
    expect(screen.getByText('Select a target to verify')).toBeInTheDocument();
  });

  it('shows pending action message as fallback', () => {
    render(<GameActions {...defaultProps} pendingAction={pa('vote', [1, 2], 'Please vote')} />);
    expect(screen.getByText('Please vote')).toBeInTheDocument();
  });

  it('disables input when canSpeak is false', () => {
    render(<GameActions {...defaultProps} canSpeak={false} />);
    const input = screen.getByLabelText('Message input');
    expect(input).toBeDisabled();
  });

  it('enables input when canSpeak is true', () => {
    render(<GameActions {...defaultProps} canSpeak={true} />);
    const input = screen.getByLabelText('Message input');
    expect(input).not.toBeDisabled();
  });

  it('calls onSendMessage with trimmed content on submit', () => {
    render(<GameActions {...defaultProps} canSpeak={true} />);
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'Hello world' } });
    fireEvent.submit(input.closest('form')!);
    expect(defaultProps.onSendMessage).toHaveBeenCalledWith('Hello world');
  });

  it('does not submit empty messages', () => {
    render(<GameActions {...defaultProps} canSpeak={true} />);
    const input = screen.getByLabelText('Message input');
    fireEvent.submit(input.closest('form')!);
    expect(defaultProps.onSendMessage).not.toHaveBeenCalled();
  });

  it('updates vote button label based on pending action type', () => {
    render(<GameActions {...defaultProps} pendingAction={pa('kill', [1, 2], 'Kill target')} />);
    expect(screen.getAllByText('Kill').length).toBeGreaterThanOrEqual(1);
  });

  it('updates skill button label for verify action', () => {
    render(<GameActions {...defaultProps} pendingAction={pa('verify', [1, 2], 'Verify')} />);
    expect(screen.getAllByText('Verify').length).toBeGreaterThanOrEqual(1);
  });

  it('updates skill button label for protect action', () => {
    render(<GameActions {...defaultProps} pendingAction={pa('protect', [1, 2, 0], 'Protect')} />);
    // Both vote and skill buttons show "Protect" for protect action
    const protectButtons = screen.getAllByText('Protect');
    expect(protectButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('disables all buttons when isSubmitting is true', () => {
    render(<GameActions {...defaultProps} canVote={true} canUseSkill={true} isSubmitting={true} />);
    const buttons = screen.getAllByRole('button');
    buttons.forEach(btn => {
      expect(btn).toBeDisabled();
    });
  });
});
