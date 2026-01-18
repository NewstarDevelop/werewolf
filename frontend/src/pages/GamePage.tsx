import { useState, useMemo, useCallback, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import GameStatusBar from "@/components/game/GameStatusBar";
import ChatLog from "@/components/game/ChatLog";
import PlayerGrid from "@/components/game/PlayerGrid";
import GameActions from "@/components/game/GameActions";
import LogPanel from "@/components/game/LogPanel";
import DebugPanel from "@/components/game/DebugPanel";
import GameAnalysisDialog from "@/components/game/GameAnalysisDialog";
import { toast } from "sonner";
import { useGame } from "@/hooks/useGame";
import { useGameSound } from "@/hooks/useGameSound";
import {
  isNightPhase,
  type Role,
  type Player,
} from "@/services/api";
import { useTranslation } from "react-i18next";
import { translateSystemMessage, translateActionMessage } from "@/utils/messageTranslator";
import { saveLastGameId, clearLastRoomId, clearLastGameId } from "@/hooks/useActiveGame";

interface UIPlayer {
  id: number;
  name: string;
  isUser: boolean;
  isAlive: boolean;
  role?: Role;
  seatId: number;
}

const GamePage = () => {
  const { t } = useTranslation(['common', 'game']);
  const { gameId: gameIdFromRoute } = useParams<{ gameId: string }>();
  const navigate = useNavigate();

  const handleReturnToLobby = useCallback(() => {
    navigate('/lobby');
  }, [navigate]);

  // Validate gameId exists - redirect to lobby if missing
  useEffect(() => {
    if (!gameIdFromRoute) {
      navigate('/lobby', { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameIdFromRoute]);

  // Save gameId to localStorage so sidebar "Current Game" can navigate back
  useEffect(() => {
    if (gameIdFromRoute) {
      saveLastGameId(gameIdFromRoute);
      clearLastRoomId();
    }
  }, [gameIdFromRoute]);

  const {
    gameId,
    gameState,
    isLoading,
    isStarting,
    error,
    isNight,
    needsAction,
    isGameOver,
    startGame,
    speak,
    vote,
    kill,
    verify,
    save,
    poison,
    shoot,
    protect,
    selfDestruct,
    skip,
    isSubmitting,
  } = useGame({ autoStep: true, gameId: gameIdFromRoute });  // Use gameId from route

  // Enable game sounds
  useGameSound({ gameState, isEnabled: true });

  // Clear lastGameId when game is over (no longer an active game)
  useEffect(() => {
    if (isGameOver) {
      clearLastGameId();
    }
  }, [isGameOver]);

  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [logPanelOpen, setLogPanelOpen] = useState(false);
  const [debugPanelOpen, setDebugPanelOpen] = useState(false);
  const [analysisDialogOpen, setAnalysisDialogOpen] = useState(false);

  // Transform game state to UI format
  const players = useMemo<UIPlayer[]>(() => {
    if (!gameState) return [];
    return [...gameState.players]
      .sort((a, b) => a.seat_id - b.seat_id)  // Sort by seat_id to fix border highlighting
      .map((p) => {
        // WL-008 Fix: Use my_seat to identify current player, not is_human
        // is_human means "is this seat a human player" (multiple can be true in multiplayer)
        // my_seat identifies "which seat belongs to the requesting player"
        const isMe = p.seat_id === gameState.my_seat;
        return {
          id: p.seat_id,
          name: isMe ? t('common:player.you') : p.name || t('common:player.default_name', { id: p.seat_id }),
          isUser: isMe,
          isAlive: p.is_alive,
          // Show role for: 1) Current player always, 2) All players when game is finished
          role: isMe ? gameState.my_role : (isGameOver ? (p.role ?? undefined) : undefined),
          seatId: p.seat_id,
        };
      });
  }, [gameState, isGameOver, t]);

  // 预构建 seat_id -> player Map，避免 O(n) 线性查找
  const playerMap = useMemo(() => {
    if (!gameState) return new Map<number, Player>();
    return new Map(gameState.players.map(p => [p.seat_id, p]));
  }, [gameState?.players]);

  // Transform messages to UI format
  const messages = useMemo(() => {
    if (!gameState) return [];
    return gameState.message_log.map((m, idx) => {
      const player = playerMap.get(m.seat_id); // O(1) 查找替代 find()
      const isSystem = m.type === "system" || m.seat_id === 0;
      const isUser = m.seat_id === gameState.my_seat;

      // Translate system messages
      const messageText = isSystem
        ? translateSystemMessage(m.text, t)
        : m.text;

      return {
        id: idx + 1,
        sender: isSystem
          ? t('common:player.system')
          : isUser
          ? t('common:player.you')
          : player?.name || t('common:player.seat', { id: m.seat_id }),
        message: messageText,
        isUser,
        isSystem,
        timestamp: "",
        day: m.day,
      };
    });
  }, [gameState, playerMap, t]);

  const playersAlive = players.filter((p) => p.isAlive).length;
  const turnCount = gameState?.day || 1;

  // Handle sending message (speech)
  const handleSendMessage = async (message: string) => {
    if (!gameState || !needsAction) return;

    try {
      await speak(message);
      toast.success(t('common:toast.speech_success'));
    } catch (err) {
      toast.error(t('common:toast.speech_failed'), {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  // Handle vote
  const handleVote = async () => {
    if (!gameState || !needsAction) return;

    const pendingAction = gameState.pending_action;
    if (!pendingAction) return;

    try {
      if (pendingAction.type === "vote") {
        await vote(selectedPlayerId);
        toast.success(
          selectedPlayerId
            ? t('common:toast.voted_for', { id: selectedPlayerId })
            : t('common:toast.abstain')
        );
      } else if (pendingAction.type === "kill" && selectedPlayerId) {
        await kill(selectedPlayerId);
        toast.success(t('common:toast.kill_selected', { id: selectedPlayerId }));
      } else if (pendingAction.type === "shoot") {
        await shoot(selectedPlayerId);
        toast.success(
          selectedPlayerId
            ? t('common:toast.shoot_selected', { id: selectedPlayerId })
            : t('common:toast.shoot_skipped')
        );
      }
      setSelectedPlayerId(null);
    } catch (err) {
      toast.error(t('common:toast.action_failed'), {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  // Handle skill use
  const handleUseSkill = async () => {
    if (!gameState || !needsAction) return;

    const pendingAction = gameState.pending_action;
    if (!pendingAction) return;

    try {
      switch (pendingAction.type) {
        case "verify":
          if (selectedPlayerId) {
            await verify(selectedPlayerId);
            toast.info(t('common:toast.verify_selected', { id: selectedPlayerId }));
          }
          break;
        case "save":
          if (selectedPlayerId) {
            // Only save if a player is selected (must be the kill target)
            if (selectedPlayerId === gameState.night_kill_target) {
              await save();
              toast.success(t('common:toast.antidote_used'));
            } else {
              toast.error(t('common:toast.save_error'));
              setSelectedPlayerId(null); // Clear selection on error
              return;
            }
          } else {
            // No selection means skip
            await skip();
            toast.info(t('common:toast.antidote_skipped'));
          }
          break;
        case "poison":
          if (selectedPlayerId) {
            await poison(selectedPlayerId);
            toast.success(t('common:toast.poison_used', { id: selectedPlayerId }));
          } else {
            await skip();
            toast.info(t('common:toast.poison_skipped'));
          }
          break;
        case "protect":
          if (selectedPlayerId) {
            await protect(selectedPlayerId);
            toast.success(t('common:toast.protect_selected', { id: selectedPlayerId }));
          } else {
            await skip();
            toast.info(t('common:toast.protect_skipped'));
          }
          break;
        case "self_destruct":
          await selfDestruct();
          toast.success(t('common:toast.self_destruct_activated'));
          break;
        default:
          await skip();
      }
    } catch (err) {
      toast.error(t('common:toast.skill_failed'), {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      // Always clear selection after action attempt
      setSelectedPlayerId(null);
    }
  };

  const handleSelectPlayer = useCallback((id: number) => {
    setSelectedPlayerId(prev => prev === id ? null : id);
  }, []);

  // Show loading state while game is loading
  if (isLoading && !gameState) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="text-center">
          <p className="text-xl text-foreground">{t('common:loading')}</p>
        </div>
      </div>
    );
  }

  // Show error if game failed to load
  if (error && !gameState) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="text-center">
          <p className="text-xl text-destructive mb-4">{error}</p>
          <Button onClick={handleReturnToLobby}>
            {t('common:return_to_lobby')}
          </Button>
        </div>
      </div>
    );
  }

  // Determine action button states
  const canVote =
    needsAction &&
    gameState?.pending_action?.type &&
    ["vote", "kill", "shoot"].includes(gameState.pending_action.type);
  const canUseSkill =
    needsAction &&
    gameState?.pending_action?.type &&
    ["verify", "save", "poison", "protect", "self_destruct"].includes(gameState.pending_action.type) &&
    // For save action, must select the night kill target to enable the button
    // For self_destruct, no target needed (always enabled via includes check above)
    (gameState.pending_action.type !== "save" ||
     selectedPlayerId === gameState.night_kill_target);
  const canSpeak =
    needsAction && gameState?.pending_action?.type === "speak";

  // Get action hint with translation
  const actionHint = gameState?.pending_action?.message
    ? translateActionMessage(gameState.pending_action.message, t)
    : "";

  return (
    <div className="flex flex-col h-[100dvh] bg-background overflow-hidden relative">
      {/* Atmospheric background */}
      <div className="absolute inset-0 atmosphere-game pointer-events-none" />
      <div className={`absolute inset-0 transition-opacity duration-1000 pointer-events-none ${isNight ? 'opacity-100' : 'opacity-0'}`}>
        <div className="absolute inset-0 atmosphere-moonlight" />
      </div>
      <div className={`absolute inset-0 transition-opacity duration-1000 pointer-events-none ${!isNight ? 'opacity-30' : 'opacity-0'}`}>
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-amber-900/10 via-transparent to-transparent" />
      </div>

      {/* Status Bar */}
      <div className="relative z-10">
        <GameStatusBar
          isNight={isNight}
          turnCount={turnCount}
          playersAlive={playersAlive}
          totalPlayers={players.length}
          phase={gameState?.phase}
          role={gameState?.my_role}
          actionHint={actionHint}
          isGameOver={isGameOver}
          winner={gameState?.winner}
          onOpenLogs={() => setLogPanelOpen(true)}
          onOpenDebug={() => setDebugPanelOpen(true)}
          onOpenAnalysis={() => setAnalysisDialogOpen(true)}
          onReturnToLobby={handleReturnToLobby}
        />
      </div>

      {/* Main Content */}
      <div className="relative z-10 flex flex-1 overflow-hidden flex-col md:flex-row p-3 gap-3 md:p-6 md:gap-6 max-w-[1920px] mx-auto w-full">
        {/* Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 shadow-2xl rounded-2xl overflow-hidden glass-panel border border-border/20 ring-1 ring-border/10">
          <ChatLog messages={messages} isLoading={isLoading} />
        </div>

        {/* Right Sidebar: Players */}
        <div className="w-full md:w-[340px] lg:w-[380px] shrink-0 max-h-[40vh] md:max-h-none flex flex-col">
          <PlayerGrid
            players={players}
            selectedPlayerId={selectedPlayerId}
            onSelectPlayer={handleSelectPlayer}
            currentActor={gameState?.current_actor}
            pendingAction={gameState?.pending_action}
            wolfTeammates={gameState?.wolf_teammates}
            verifiedResults={gameState?.verified_results}
            wolfVotesVisible={gameState?.wolf_votes_visible}
            myRole={gameState?.my_role}
            nightKillTarget={gameState?.night_kill_target}
          />
        </div>
      </div>

      {/* Actions Bar */}
      <div className="relative z-10">
        <GameActions
          onSendMessage={handleSendMessage}
          onVote={handleVote}
          onUseSkill={handleUseSkill}
          canVote={canVote && selectedPlayerId !== null}
          canUseSkill={canUseSkill}
          canSpeak={canSpeak}
          isNight={isNight}
          isSubmitting={isSubmitting}
          pendingAction={gameState?.pending_action}
          translatedMessage={actionHint}
        />
      </div>

      {/* Log Panel */}
      {gameId && (
        <LogPanel
          gameId={gameId}
          isOpen={logPanelOpen}
          onClose={() => setLogPanelOpen(false)}
        />
      )}

      {gameId && (
        <DebugPanel
          gameId={gameId}
          isOpen={debugPanelOpen}
          onClose={() => setDebugPanelOpen(false)}
        />
      )}

      {gameId && (
        <GameAnalysisDialog
          gameId={gameId}
          isOpen={analysisDialogOpen}
          onClose={() => setAnalysisDialogOpen(false)}
        />
      )}
    </div>
  );
};

export default GamePage;
