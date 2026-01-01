import { memo } from "react";
import { User, Skull, Shield, Search, Crosshair, FlaskConical, Target } from "lucide-react";
import { type Role } from "@/services/api";
import { useTranslation } from "react-i18next";
import { useIsMobile } from "@/hooks/use-mobile";

interface PlayerCardProps {
  seatId: number;
  name: string;
  isUser: boolean;
  isAlive: boolean;
  isSelected: boolean;
  role?: Role;
  avatar?: string;
  onSelect: () => void;
  isCurrentActor?: boolean;
  isWolfTeammate?: boolean;
  verificationResult?: boolean; // true = werewolf, false = good
  wolfVote?: number; // teammate's vote target seat_id
  isSelectable?: boolean;
}

const PlayerCard = ({
  seatId,
  name,
  isUser,
  isAlive,
  isSelected,
  role,
  onSelect,
  isCurrentActor,
  isWolfTeammate,
  verificationResult,
  wolfVote,
  isSelectable = true,
}: PlayerCardProps) => {
  const { t } = useTranslation('common');
  const isMobile = useIsMobile();

  const padding = isMobile ? "p-1.5" : "p-3";
  const avatarSize = isMobile ? "w-10 h-10" : "w-14 h-14";
  const iconSize = isMobile ? "w-5 h-5" : "w-7 h-7";

  const getRoleIcon = () => {
    if (!role) return null;
    switch (role) {
      case "werewolf":
        return <Skull className="w-3 h-3 text-werewolf" />;
      case "seer":
        return <Search className="w-3 h-3 text-moonlight" />;
      case "witch":
        return <FlaskConical className="w-3 h-3 text-purple-400" />;
      case "hunter":
        return <Crosshair className="w-3 h-3 text-orange-400" />;
      case "villager":
        return <User className="w-3 h-3 text-villager" />;
      default:
        return null;
    }
  };

  // Determine background class based on special status
  const getBackgroundClass = () => {
    if (isSelected) return "bg-werewolf/20 scale-105";
    if (isCurrentActor && isUser) return "bg-yellow-400/20 scale-105";
    return "bg-card/50";
  };

  // P2-5: Generate accessible label describing player state
  const getAccessibleLabel = () => {
    const parts: string[] = [];
    parts.push(`${seatId}${t('player.seat_suffix')} ${name}`);
    if (!isAlive) parts.push(t('player.eliminated'));
    if (isSelected) parts.push(t('player.selected'));
    if (isUser) parts.push(t('player.you'));
    if (verificationResult === true) parts.push(t('player.verified_werewolf'));
    if (verificationResult === false) parts.push(t('player.verified_good'));
    if (isWolfTeammate) parts.push(t('player.wolf_teammate'));
    if (isCurrentActor) parts.push(t('player.current_actor'));
    return parts.join(', ');
  };

  // Determine border color based on special status
  const getBorderClass = () => {
    // Speaking/acting has absolute highest priority - must be checked first!
    if (isCurrentActor && isUser) return "border-2 border-yellow-400 shadow-[0_0_15px_rgba(250,204,21,0.5)] animate-pulse z-20";
    if (isCurrentActor) return "border-2 border-accent animate-pulse z-20";

    // Selection state (second priority)
    if (isSelected) return "border-2 border-werewolf shadow-glow-red";

    // Team/verification states (lower priority, only show when NOT speaking)
    if (isWolfTeammate) return "border-2 border-werewolf/50";
    if (verificationResult === true) return "border-2 border-werewolf/70";
    if (verificationResult === false) return "border-2 border-villager/70";

    // Default state
    return "border border-border hover:border-accent/50";
  };

  const getRoleBadgeStyle = (role: Role) => {
    switch (role) {
      case "werewolf":
        return "bg-werewolf/20 border-werewolf text-werewolf";
      case "seer":
        return "bg-blue-500/20 border-blue-500 text-blue-400";
      case "witch":
        return "bg-purple-500/20 border-purple-500 text-purple-400";
      case "hunter":
        return "bg-orange-500/20 border-orange-500 text-orange-400";
      case "villager":
        return "bg-villager/20 border-villager text-villager";
      default:
        return "bg-muted border-muted text-muted-foreground";
    }
  };

  return (
    <button
      onClick={onSelect}
      disabled={!isAlive || !isSelectable}
      aria-label={getAccessibleLabel()}
      aria-pressed={isSelected}
      className={`
        relative group flex flex-col items-center gap-2 ${padding} rounded-xl
        transition-all duration-300
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background
        ${
          isAlive && isSelectable
            ? "hover:scale-105 hover:bg-muted/50 cursor-pointer"
            : "opacity-40 cursor-not-allowed"
        }
        ${!isAlive ? "grayscale" : ""}
        ${getBackgroundClass()}
        ${getBorderClass()}
        ${isUser ? "ring-2 ring-accent/30" : ""}
      `}
    >
      {/* Seat number badge */}
      <div className="absolute -top-1 -left-1 w-5 h-5 rounded-full bg-muted border border-border flex items-center justify-center">
        <span className="text-[10px] font-bold text-muted-foreground">
          {seatId}
        </span>
      </div>

      {/* Current actor indicator */}
      {isCurrentActor && isAlive && (
        <div className="absolute -top-1 -right-1">
          <Target className="w-4 h-4 text-accent animate-pulse" />
        </div>
      )}

      {/* Wolf teammate indicator */}
      {isWolfTeammate && !isUser && (
        <div className="absolute -top-1 -right-1">
          <Skull className="w-4 h-4 text-werewolf" />
        </div>
      )}

      {/* Verification result indicator */}
      {verificationResult !== undefined && !isUser && (
        <div
          className={`absolute -top-1 -right-1 w-4 h-4 rounded-full ${
            verificationResult ? "bg-werewolf" : "bg-villager"
          }`}
        />
      )}

      {/* Avatar */}
      <div
        className={`
          relative ${avatarSize} rounded-full flex items-center justify-center
          transition-all duration-300
          ${
            isAlive
              ? isSelected
                ? "bg-werewolf/30 shadow-glow-red"
                : "bg-muted group-hover:bg-accent/20"
              : "bg-muted/50"
          }
        `}
      >
        {isAlive ? (
          <User
            className={`${iconSize} ${
              isSelected
                ? "text-werewolf"
                : "text-muted-foreground group-hover:text-accent"
            }`}
          />
        ) : (
          <Skull className={`${iconSize} text-muted-foreground/50`} />
        )}

        {/* Role badge for user */}
        {role && (
          <div className="absolute -bottom-1 -right-1 p-1.5 rounded-full bg-card border border-border">
            {getRoleIcon()}
          </div>
        )}
      </div>

      {/* Name */}
      <div className="text-center min-h-[32px] flex flex-col items-center justify-center gap-1">
        <p
          className={`text-sm font-semibold truncate max-w-[70px] ${
            isAlive
              ? isSelected
                ? "text-werewolf"
                : "text-foreground"
              : "text-muted-foreground line-through"
          }`}
        >
          {name}
        </p>
        {role && (
          <span className={`inline-flex items-center justify-center rounded-full px-2 py-0.5 border text-[11px] font-semibold ${getRoleBadgeStyle(role)}`}>
            {t(`roles:${role}`)}
          </span>
        )}
        {/* Teammate vote indicator */}
        {wolfVote && (
          <div className="mt-0.5 px-1.5 py-0.5 rounded-full bg-werewolf/80 text-white text-[10px] font-bold">
            →{wolfVote}
          </div>
        )}
      </div>

      {/* Death overlay */}
      {!isAlive && (
        <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-background/30 backdrop-blur-[1px]">
          <span className="text-xs text-werewolf font-display uppercase tracking-wider">
            {t('player.eliminated')}
          </span>
        </div>
      )}
    </button>
  );
};

export default memo(PlayerCard);
