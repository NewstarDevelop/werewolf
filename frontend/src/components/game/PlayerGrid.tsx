import PlayerCard from "./PlayerCard";
import { Users } from "lucide-react";
import { PendingAction, Role } from "@/services/api";
import { useTranslation } from "react-i18next";
import { useIsMobile } from "@/hooks/use-mobile";

interface Player {
  id: number;
  name: string;
  isUser: boolean;
  isAlive: boolean;
  role?: Role;
  seatId: number;
}

interface PlayerGridProps {
  players: Player[];
  selectedPlayerId: number | null;
  onSelectPlayer: (id: number) => void;
  currentActor?: number | null;
  pendingAction?: PendingAction | null;
  wolfTeammates?: number[];
  verifiedResults?: Record<number, boolean>;
  wolfVotesVisible?: Record<number, number>; // teammate_seat -> target_seat
  myRole?: Role;
}

const PlayerGrid = ({
  players,
  selectedPlayerId,
  onSelectPlayer,
  currentActor,
  pendingAction,
  wolfTeammates = [],
  verifiedResults = {},
  wolfVotesVisible = {},
  myRole,
}: PlayerGridProps) => {
  const { t } = useTranslation('common');
  const isMobile = useIsMobile();

  // Determine which players can be selected based on pending action
  const selectableIds = pendingAction?.choices || [];

  return (
    <div className={`bg-card/50 rounded-xl border border-border ${isMobile ? 'p-2 h-full overflow-y-auto' : 'p-3'}`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-border">
        <Users className="w-4 h-4 text-accent" />
        <h2 className="font-display text-sm font-semibold text-foreground">
          {t('player_grid.title')}
        </h2>
        <span className="ml-auto text-xs text-muted-foreground">
          {pendingAction ? t('player_grid.select_target') : ""}
        </span>
      </div>

      {/* Grid */}
      <div className={`grid ${isMobile ? 'grid-cols-4 gap-1' : 'grid-cols-3 gap-2'}`}>
        {players.map((player) => {
          // Check if this player is a wolf teammate (for werewolf role)
          const isWolfTeammate =
            myRole === "werewolf" && wolfTeammates.includes(player.seatId);

          // Check verification result (for seer role)
          const verificationResult = verifiedResults[player.seatId];

          // Get teammate's vote target (for werewolf role)
          const wolfVote = wolfVotesVisible[player.seatId];

          // Check if player is selectable
          const isSelectable =
            selectableIds.length === 0 ||
            selectableIds.includes(player.seatId);

          return (
            <PlayerCard
              key={player.id}
              seatId={player.seatId}
              name={player.name}
              isUser={player.isUser}
              isAlive={player.isAlive}
              isSelected={selectedPlayerId === player.id}
              role={player.role}
              onSelect={() => isSelectable && onSelectPlayer(player.id)}
              isCurrentActor={
                // 只在发言阶段显示边框，真实玩家显示黄色边框
                pendingAction?.type === "speak" && player.isUser
              }
              isWolfTeammate={isWolfTeammate}
              verificationResult={verificationResult}
              wolfVote={wolfVote}
              isSelectable={isSelectable}
            />
          );
        })}
      </div>

      {/* Legend */}
      {myRole && (
        <div className="mt-4 pt-3 border-t border-border">
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            {myRole === "werewolf" && (
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-werewolf" />
                <span>{t('player_grid.wolf_teammate')}</span>
              </div>
            )}
            {myRole === "seer" && (
              <>
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-villager" />
                  <span>{t('player_grid.good')}</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-werewolf" />
                  <span>{t('player_grid.werewolf')}</span>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PlayerGrid;
