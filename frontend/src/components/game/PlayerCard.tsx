import { memo } from "react";
import { User, Skull, Shield, Search, Crosshair, FlaskConical, Target, Crown, Ghost } from "lucide-react";
import { type Role } from "@/services/api";
import { useTranslation } from "react-i18next";
import { useIsMobile } from "@/hooks/use-mobile";
import { cva } from 'class-variance-authority';

const playerCardVariants = cva(
  'relative group flex flex-col items-center gap-2 rounded-xl transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background',
  {
    variants: {
      status: {
        alive: '',
        dead: 'opacity-50 cursor-not-allowed grayscale',
      },
      selectable: {
        true: 'hover:scale-105 hover:bg-muted/50 cursor-pointer',
        false: 'cursor-not-allowed',
      },
      selected: {
        true: 'bg-werewolf/20 scale-105',
        false: 'glass-panel',
      },
      isCurrentActor: {
        true: 'bg-yellow-400/20 scale-105',
        false: '',
      },
      isUser: {
        true: 'ring-2 ring-accent/30',
        false: '',
      },
    },
    compoundVariants: [
      {
        status: 'alive',
        selectable: true,
        className: '',
      },
      {
        selected: true,
        isCurrentActor: true,
        className: 'bg-yellow-400/20',
      },
    ],
    defaultVariants: {
      status: 'alive',
      selectable: true,
      selected: false,
      isCurrentActor: false,
      isUser: false,
    },
  }
);

const playerCardBorderVariants = cva('', {
  variants: {
    borderType: {
      currentActorUser: 'border-2 border-yellow-400 shadow-[0_0_15px_rgba(250,204,21,0.5)] animate-pulse z-20',
      currentActor: 'border-2 border-accent animate-pulse z-20',
      selected: 'border-2 border-werewolf shadow-glow-red',
      killTarget: 'border-2 border-purple-500 shadow-[0_0_12px_rgba(168,85,247,0.5)] animate-pulse',
      wolfTeammate: 'border-2 border-werewolf/50',
      verifiedWerewolf: 'border-2 border-werewolf/70',
      verifiedGood: 'border-2 border-villager/70',
      default: 'border border-border hover:border-accent/50',
    },
  },
  defaultVariants: {
    borderType: 'default',
  },
});

interface PlayerCardProps {
  seatId: number;
  name: string;
  isUser: boolean;
  isAlive: boolean;
  isSelected: boolean;
  role?: Role;
  avatar?: string;
  onSelect: (seatId: number) => void;
  isCurrentActor?: boolean;
  isWolfTeammate?: boolean;
  verificationResult?: boolean; // true = werewolf, false = good
  wolfVote?: number; // teammate's vote target seat_id
  isSelectable?: boolean;
  isKillTarget?: boolean; // For witch save phase - highlight the kill target
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
  isKillTarget = false,
}: PlayerCardProps) => {
  const { t } = useTranslation(['common', 'roles']);
  const isMobile = useIsMobile();

  // Responsive sizing constants
  const padding = isMobile ? "p-2.5" : "p-3";
  const avatarSize = isMobile ? "w-12 h-12" : "w-14 h-14";
  const iconSize = isMobile ? "w-6 h-6" : "w-7 h-7";
  const nameMaxWidth = isMobile ? "max-w-[60px]" : "max-w-[90px]";
  const badgeOffset = isMobile ? "-top-1 -left-1" : "-top-2 -left-2";
  const badgeOffsetRight = isMobile ? "-top-1 -right-1" : "-top-2 -right-2";

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
      case "guard":
        return <Shield className="w-3 h-3 text-emerald-400" />;
      case "wolf_king":
        return <Crown className="w-3 h-3 text-red-500" />;
      case "white_wolf_king":
        return <Ghost className="w-3 h-3 text-slate-300" />;
      default:
        return null;
    }
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
    if (role) parts.push(t(`roles:${role}`));
    return parts.join(', ');
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
      case "guard":
        return "bg-emerald-500/20 border-emerald-500 text-emerald-400";
      case "wolf_king":
        return "bg-red-500/20 border-red-500 text-red-400";
      case "white_wolf_king":
        return "bg-slate-500/20 border-slate-500 text-slate-300";
      default:
        return "bg-muted border-muted text-muted-foreground";
    }
  };

  // Determine border type based on priority
  const getBorderType = (): 'currentActorUser' | 'currentActor' | 'selected' | 'killTarget' | 'wolfTeammate' | 'verifiedWerewolf' | 'verifiedGood' | 'default' => {
    if (isCurrentActor && isUser) return 'currentActorUser';
    if (isCurrentActor) return 'currentActor';
    if (isSelected) return 'selected';
    if (isKillTarget) return 'killTarget';
    if (isWolfTeammate) return 'wolfTeammate';
    if (verificationResult === true) return 'verifiedWerewolf';
    if (verificationResult === false) return 'verifiedGood';
    return 'default';
  };

  return (
    <button
      onClick={() => onSelect(seatId)}
      disabled={!isAlive || !isSelectable}
      aria-label={getAccessibleLabel()}
      aria-pressed={isSelected}
      className={`
        ${padding}
        ${playerCardVariants({
          status: isAlive ? 'alive' : 'dead',
          selectable: isAlive && isSelectable,
          selected: isSelected,
          isCurrentActor: isCurrentActor, // Fix #3: Remove && isUser to apply to all current actors
          isUser,
        })}
        ${playerCardBorderVariants({ borderType: getBorderType() })}
      `}
    >
      {/* Seat number badge */}
      <div className={`absolute ${badgeOffset} w-6 h-6 rounded-full bg-muted border border-border flex items-center justify-center z-10`}>
        <span className="text-[10px] font-bold text-muted-foreground">
          {seatId}
        </span>
      </div>

      {/* Current actor indicator - highest priority */}
      {isCurrentActor && isAlive && (
        <div className={`absolute ${badgeOffsetRight} z-10`}>
          <Target className="w-4 h-4 text-accent animate-pulse" />
        </div>
      )}

      {/* Wolf teammate indicator - only show when not current actor */}
      {isWolfTeammate && !isUser && !isCurrentActor && (
        <div className={`absolute ${badgeOffsetRight} z-10`}>
          <Skull className="w-4 h-4 text-werewolf" />
        </div>
      )}

      {/* Verification result indicator - only show when no other right indicators */}
      {verificationResult !== undefined && !isUser && !isCurrentActor && !isWolfTeammate && (
        <div
          className={`absolute ${badgeOffsetRight} w-4 h-4 rounded-full z-10 ${
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
          className={`text-sm font-semibold truncate ${nameMaxWidth} ${
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
          <span className={`inline-flex items-center justify-center rounded-full px-2 py-0.5 border text-[11px] font-semibold max-w-full truncate ${getRoleBadgeStyle(role)}`}>
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
