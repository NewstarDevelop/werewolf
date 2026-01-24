import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Send, Vote, Sparkles, Loader2, SkipForward, Shield, Bomb } from "lucide-react";
import { PendingAction } from "@/services/api";
import { useTranslation } from "react-i18next";
import { useSound } from "@/contexts/SoundContext";
import { z } from "zod";
import { toast } from "sonner";

const messageSchema = z.string()
  .min(1, 'Message cannot be empty')
  .max(500, 'Message too long (max 500 characters)')
  .regex(/^[^<>]*$/, 'Invalid characters detected');

interface GameActionsProps {
  onSendMessage: (message: string) => void;
  onVote: () => void;
  onUseSkill: () => void;
  onSkip: () => void;  // MAJOR FIX: Dedicated skip handler to prevent ambiguity
  canVote: boolean;
  canUseSkill: boolean;
  canSpeak?: boolean;
  isNight: boolean;
  isSubmitting?: boolean;
  pendingAction?: PendingAction | null;
  translatedMessage?: string;  // P1-1: Pre-translated action hint for consistency
}

const GameActions = ({
  onSendMessage,
  onVote,
  onUseSkill,
  onSkip,
  canVote,
  canUseSkill,
  canSpeak,
  isNight,
  isSubmitting,
  pendingAction,
  translatedMessage,
}: GameActionsProps) => {
  const [message, setMessage] = useState("");
  const { t } = useTranslation('game');
  const { play } = useSound();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSpeak) return;

    const result = messageSchema.safeParse(message.trim());
    if (!result.success) {
      toast.error(result.error.errors[0].message);
      return;
    }

    play('CLICK');
    onSendMessage(result.data);
    setMessage("");
  };

  const handleVoteClick = () => {
    play('VOTE');
    onVote();
  };

  const handleSkillClick = () => {
    play('CLICK');
    onUseSkill();
  };

  // Get action button label based on pending action type
  const getVoteButtonLabel = () => {
    if (!pendingAction) return t('action.vote');
    return t(`action.${pendingAction.type}`);
  };

  const getSkillButtonLabel = () => {
    if (!pendingAction) return t('action.skill');
    if (["verify", "save", "poison"].includes(pendingAction.type)) {
      return t(`action.${pendingAction.type}`);
    }
    if (pendingAction.type === "protect") return t('action.protect');
    if (pendingAction.type === "self_destruct") return t('action.self_destruct');
    return t('action.skill');
  };

  // Determine if we should show skip button
  const showSkipButton =
    pendingAction &&
    ["save", "poison", "shoot", "vote", "protect"].includes(pendingAction.type) &&
    pendingAction.choices.includes(0);

  // MAJOR FIX: Use dedicated skip handler to avoid selectedPlayerId ambiguity
  const handleSkipClick = () => {
    play('CLICK');
    onSkip();
  };

  // Get appropriate icon based on action type
  const getActionIcon = () => {
    if (pendingAction?.type === "protect") return <Shield className="w-4 h-4" />;
    if (pendingAction?.type === "self_destruct") return <Bomb className="w-4 h-4" />;
    if (pendingAction?.type === "vote" || pendingAction?.type === "kill" || pendingAction?.type === "shoot") return <Vote className="w-4 h-4" />;
    return <Sparkles className="w-4 h-4" />;
  };

  return (
    <div className="glass-panel border-t border-border/10 p-3">
      <div className="flex flex-col gap-3">
        {/* Action hint - P1-1: Use translated message for consistency */}
        {(translatedMessage || pendingAction?.message) && (
          <div className="text-center text-sm text-accent bg-accent/10 py-2 px-4 rounded-lg border border-accent/20 animate-fade-in">
            {/* MINOR FIX: Ensure sufficient contrast for accessibility */}
            {/* If contrast issues occur, consider using text-accent-foreground or text-foreground */}
            {translatedMessage || pendingAction?.message}
          </div>
        )}

        {/* Chat Input */}
        <form onSubmit={handleSubmit} className="flex gap-2 items-center bg-muted/30 p-1.5 rounded-2xl border border-border/10 focus-within:border-accent/50 focus-within:bg-muted/50 focus-within:shadow-[0_0_15px_rgba(0,0,0,0.3)] transition-all duration-300">
          <div className="flex-1 relative">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              maxLength={500}
              placeholder={
                canSpeak
                  ? t('message.enter_message')
                  : isNight
                  ? t('status.night')
                  : t('message.waiting')
              }
              disabled={!canSpeak || isSubmitting}
              aria-label={t('message.input_label')}
              className="w-full px-4 py-2 h-10 bg-transparent border-none text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-0 disabled:opacity-50 disabled:cursor-not-allowed text-sm md:text-base font-medium"
            />
          </div>
          <Button
            type="submit"
            size="icon"
            variant="ghost"
            disabled={!canSpeak || !message.trim() || isSubmitting}
            className="h-10 w-10 rounded-xl hover:bg-accent hover:text-accent-foreground transition-all duration-300 active:scale-95"
            aria-label={t('action.send')}
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </form>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <Button
            variant="vote"
            onClick={handleVoteClick}
            disabled={!canVote || isSubmitting}
            className="flex-1 h-11 md:h-10"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Vote className="w-4 h-4" />
            )}
            {getVoteButtonLabel()}
          </Button>

          <Button
            variant="skill"
            onClick={handleSkillClick}
            disabled={(!canUseSkill && pendingAction?.type !== 'self_destruct') || isSubmitting}
            className="flex-1 h-11 md:h-10"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              getActionIcon()
            )}
            {getSkillButtonLabel()}
          </Button>

          {showSkipButton && (
            <Button
              variant="muted"
              onClick={handleSkipClick}
              disabled={isSubmitting}
              className="w-24 h-11 md:h-10"
            >
              <SkipForward className="w-4 h-4" />
              {t('action.skip')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default GameActions;
