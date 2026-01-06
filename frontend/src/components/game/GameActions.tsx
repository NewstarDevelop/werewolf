import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Send, Vote, Sparkles, Loader2, SkipForward, Shield, Bomb } from "lucide-react";
import { PendingAction } from "@/services/api";
import { useTranslation } from "react-i18next";
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSpeak) return;

    const result = messageSchema.safeParse(message.trim());
    if (!result.success) {
      toast.error(result.error.errors[0].message);
      return;
    }

    onSendMessage(result.data);
    setMessage("");
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

  // Determine which handler to use for skip button based on action type
  const getSkipHandler = () => {
    if (!pendingAction) return onUseSkill;
    // vote and shoot are handled by onVote, save and poison and protect by onUseSkill
    return ["vote", "shoot"].includes(pendingAction.type) ? onVote : onUseSkill;
  };

  // Get appropriate icon based on action type
  const getActionIcon = () => {
    if (pendingAction?.type === "protect") return <Shield className="w-4 h-4" />;
    if (pendingAction?.type === "self_destruct") return <Bomb className="w-4 h-4" />;
    if (pendingAction?.type === "vote" || pendingAction?.type === "kill" || pendingAction?.type === "shoot") return <Vote className="w-4 h-4" />;
    return <Sparkles className="w-4 h-4" />;
  };

  return (
    <div className="glass-panel-dark border-t border-white/5 p-3">
      <div className="flex flex-col gap-3">
        {/* Action hint - P1-1: Use translated message for consistency */}
        {(translatedMessage || pendingAction?.message) && (
          <div className="text-center text-sm text-accent bg-accent/10 py-2 px-4 rounded-lg border border-accent/20 animate-fade-in">
            {translatedMessage || pendingAction?.message}
          </div>
        )}

        {/* Chat Input */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <div className="flex-1 relative">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={
                canSpeak
                  ? t('message.enter_message')
                  : isNight
                  ? t('status.night')
                  : t('message.waiting')
              }
              disabled={!canSpeak || isSubmitting}
              aria-label={t('message.input_label')}
              className="w-full px-4 py-2 rounded-xl bg-input border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            />
          </div>
          <Button
            type="submit"
            size="icon"
            variant="muted"
            disabled={!canSpeak || !message.trim() || isSubmitting}
            className="h-10 w-10"
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
            onClick={onVote}
            disabled={!canVote || isSubmitting}
            className="flex-1"
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
            onClick={onUseSkill}
            disabled={(!canUseSkill && pendingAction?.type !== 'self_destruct') || isSubmitting}
            className="flex-1"
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
              onClick={getSkipHandler()}
              disabled={isSubmitting}
              className="w-24"
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
