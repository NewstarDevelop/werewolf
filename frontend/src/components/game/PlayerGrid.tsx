import PlayerCard from "./PlayerCard";
import { Users } from "lucide-react";
import { PendingAction, Role } from "@/services/api";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

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
  nightKillTarget?: number | null; // For witch save phase - highlight the kill target
  guardLastTarget?: number | null; // For guard - last night's protection target (cannot protect consecutively)
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
  nightKillTarget,
  guardLastTarget,
}: PlayerGridProps) => {
  const { t } = useTranslation('common');

  // Determine which players can be selected based on pending action
  const selectableIds = pendingAction?.choices || [];

  // Determine grid mode: compact (3 cols) for 9 or fewer players, expanded (4 cols) for more
  const isCompactMode = players.length <= 9;

  return (
    <div className="bg-card/50 rounded-xl border border-border flex flex-col p-2 md:p-3 h-full md:h-auto md:min-h-[500px] md:max-h-[70vh] overflow-y-auto scrollbar-thin">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-border shrink-0">
        <Users className="w-4 h-4 text-accent" />
        <h2 className="font-display text-sm font-semibold text-foreground">
          {t('player_grid.title')}
        </h2>
        <span className="ml-auto text-xs text-muted-foreground">
          {pendingAction ? t('player_grid.select_target') : ""}
        </span>
      </div>

      {/* Responsive Grid Layout
          - Dynamic columns: 3 cols for 9 players (3x3), 4 cols for 12 players (4x3)
          - Increased padding prevents hover scale overflow
          - Scrollable container handles overflow
      */}
      <div className={cn(
        "grid w-full place-items-center content-start md:content-center",
        "gap-5 sm:gap-6 md:gap-7",
        "auto-rows-min md:auto-rows-auto",
        "p-4 pb-6",
        "grid-cols-3 sm:grid-cols-4 md:grid-cols-3",
        isCompactMode ? "lg:grid-cols-3" : "lg:grid-cols-4"
      )}>
        {players.map((player) => {
          // Check if this player is a wolf teammate (for any wolf role)
          const isWolfRole = myRole === "werewolf" || myRole === "wolf_king" || myRole === "white_wolf_king";
          const isWolfTeammate =
            isWolfRole && wolfTeammates.includes(player.seatId);

          // Check verification result (for seer role)
          const verificationResult = verifiedResults[player.seatId];

          // Get teammate's vote target (for werewolf role)
          const wolfVote = wolfVotesVisible[player.seatId];

          // Check if player is selectable
          // Guard cannot protect the same target consecutively
          const isGuardBlocked = myRole === "guard" && pendingAction?.type === "protect" && guardLastTarget === player.seatId;
          const isSelectable =
            !isGuardBlocked &&
            (selectableIds.length === 0 ||
            selectableIds.includes(player.seatId));

          return (
            <div
              key={player.id}
              className="flex justify-center items-center transition-all duration-300 ease-in-out w-full p-1"
            >
              <PlayerCard
                seatId={player.seatId}
                name={player.name}
                isUser={player.isUser}
                isAlive={player.isAlive}
                isSelected={selectedPlayerId === player.id}
                role={player.role}
                onSelect={onSelectPlayer}
                isCurrentActor={currentActor === player.seatId}
                isWolfTeammate={isWolfTeammate}
                verificationResult={verificationResult}
                wolfVote={wolfVote}
                isSelectable={isSelectable}
                isKillTarget={
                  // Show kill target highlight for witch save phase
                  myRole === "witch" &&
                  pendingAction?.type === "save" &&
                  nightKillTarget === player.seatId
                }
              />
            </div>
          );
        })}
      </div>

      {/* Legend */}
      {myRole && (
        <div className="mt-4 pt-3 border-t border-border">
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            {(myRole === "werewolf" || myRole === "wolf_king" || myRole === "white_wolf_king") && (
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
            {myRole === "guard" && guardLastTarget && (
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-muted-foreground/50" />
                <span>{t('player_grid.guard_blocked', { seat: guardLastTarget })}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PlayerGrid;
