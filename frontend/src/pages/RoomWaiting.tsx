/**
 * Room Waiting Page - waiting room before game starts
 */
import { useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { getRoomDetail, toggleReady, startGame, deleteRoom, leaveRoom } from '@/services/roomApi';
import { getPlayerId } from '@/utils/player';
import { buildWebSocketUrl } from '@/utils/websocket';

export default function RoomWaiting() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation('common');
  const queryClient = useQueryClient();
  const playerId = getPlayerId();

  // FIX: 防止重复导航的 ref
  const hasNavigatedRef = useRef(false);

  // Query room detail (refresh every 2 seconds, stop when window loses focus)
  const { data: roomDetail, isLoading } = useQuery({
    queryKey: ['roomDetail', roomId],
    queryFn: () => getRoomDetail(roomId!),
    enabled: !!roomId && !hasNavigatedRef.current,
    refetchInterval: 2000,
    refetchIntervalInBackground: false,  // P2-2: Stop polling when window loses focus
  });

  // FIX: 监听房间 WebSocket 的 game_started 事件
  useEffect(() => {
    if (!roomId || hasNavigatedRef.current) return;

    const wsUrl = buildWebSocketUrl(`/ws/room/${roomId}`);

    console.log('[RoomWaiting] Connecting to room WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[RoomWaiting] WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('[RoomWaiting] WebSocket message:', message.type);

        if (message.type === 'game_started' && !hasNavigatedRef.current) {
          hasNavigatedRef.current = true;
          const gameId = message.data?.game_id;
          if (gameId) {
            toast.success(t('toast.game_started'));
            navigate(`/game/${gameId}`);
          }
        }
      } catch (error) {
        console.error('[RoomWaiting] Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('[RoomWaiting] WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('[RoomWaiting] WebSocket closed');
    };

    return () => {
      ws.close();
    };
  }, [roomId, navigate, t]);

  // FIX: 兜底方案 - 通过轮询检测房间状态变为 PLAYING 时自动导航
  useEffect(() => {
    if (roomDetail?.room.status === 'playing' && roomDetail.room.game_id && !hasNavigatedRef.current) {
      hasNavigatedRef.current = true;
      toast.success(t('toast.game_started'));
      navigate(`/game/${roomDetail.room.game_id}`);
    }
  }, [roomDetail, navigate, t]);

  // Toggle ready mutation
  const readyMutation = useMutation({
    mutationFn: () => toggleReady(roomId!, playerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roomDetail', roomId] });
    },
    onError: (error: Error) => {
      toast.error(t('room.operation_failed'), { description: error.message });
    },
  });

  // Start game mutation (multiplayer - requires 9 players all ready)
  const startGameMutation = useMutation({
    mutationFn: () => startGame(roomId!, playerId, false),
    onSuccess: (gameId) => {
      toast.success(t('toast.game_started'));
      navigate(`/game/${gameId}`);
    },
    onError: (error: Error) => {
      toast.error(t('toast.game_start_failed'), { description: error.message });
    },
  });

  // Start game with AI fill mutation (allows < 9 players)
  const startGameWithAIMutation = useMutation({
    mutationFn: () => startGame(roomId!, playerId, true),
    onSuccess: (gameId) => {
      toast.success(t('room.game_started_ai'));
      navigate(`/game/${gameId}`);
    },
    onError: (error: Error) => {
      toast.error(t('toast.game_start_failed'), { description: error.message });
    },
  });

  // Delete room mutation
  const deleteRoomMutation = useMutation({
    mutationFn: () => deleteRoom(roomId!),
    onSuccess: () => {
      toast.success(t('room.room_deleted'));
      navigate('/');
    },
    onError: (error: Error) => {
      toast.error(t('room.delete_failed'), { description: error.message });
    },
  });

  // Leave room mutation
  const leaveRoomMutation = useMutation({
    mutationFn: () => leaveRoom(roomId!),
    onSuccess: () => {
      toast.success(t('room.left_room'));
      navigate('/');
    },
    onError: (error: Error) => {
      toast.error(t('room.leave_failed'), { description: error.message });
    },
  });

  const myPlayer = roomDetail?.players.find(p => p.is_me);
  const isCreator = myPlayer?.is_creator || false;
  const allReady = roomDetail?.players.every(p => p.is_ready) || false;
  const hasEnoughPlayers = (roomDetail?.players.length || 0) >= (roomDetail?.room.max_players || 9);

  const handleReady = () => {
    readyMutation.mutate();
  };

  const handleStartGame = () => {
    if (!hasEnoughPlayers) {
      toast.error(t('room.not_enough_players'), { description: t('room.need_9_players') });
      return;
    }
    if (!allReady) {
      toast.error(t('room.players_not_ready'));
      return;
    }
    startGameMutation.mutate();
  };

  const handleStartGameWithAI = () => {
    startGameWithAIMutation.mutate();
  };

  const handleDeleteRoom = () => {
    if (confirm(t('room.confirm_delete'))) {
      deleteRoomMutation.mutate();
    }
  };

  const handleExitRoom = () => {
    if (confirm(t('room.confirm_exit'))) {
      leaveRoomMutation.mutate();
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center animate-fade-in">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-4" />
          <p className="text-muted-foreground">{t('room.loading')}</p>
        </div>
      </div>
    );
  }

  if (!roomDetail) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center animate-fade-in">
          <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
            <svg viewBox="0 0 24 24" className="w-8 h-8 text-muted-foreground/50" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 3c-1.5 2-3 3.5-3 6a3 3 0 0 0 6 0c0-2.5-1.5-4-3-6Z" />
              <path d="M12 9c-2 3-4 5.5-4 8a4 4 0 0 0 8 0c0-2.5-2-5-4-8Z" />
            </svg>
          </div>
          <p className="text-foreground text-lg font-medium mb-3">{t('room.room_not_found')}</p>
          <Button variant="outline" onClick={() => navigate('/lobby')}>{t('room.back_to_lobby')}</Button>
        </div>
      </div>
    );
  }

  const readyCount = roomDetail.players.filter(p => p.is_ready).length;
  const totalSlots = roomDetail.room.max_players;

  return (
    <div className="min-h-full relative">
      {/* Ambient background */}
      <div className="fixed inset-0 atmosphere-night z-0 pointer-events-none" />
      <div className="fixed inset-0 atmosphere-moonlight z-0 opacity-40 pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-6 md:py-10 animate-fade-in">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground font-display tracking-tight">
              {roomDetail.room.name}
            </h1>
            <p className="text-muted-foreground mt-1 text-sm">
              {t('room.creator')}: {roomDetail.room.creator_nickname}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/lobby')}
              className="text-muted-foreground hover:text-foreground"
            >
              {t('room.back_to_lobby')}
            </Button>
            {isCreator ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDeleteRoom}
                disabled={deleteRoomMutation.isPending}
                className="text-destructive hover:text-destructive hover:bg-destructive/10"
              >
                {deleteRoomMutation.isPending ? t('room.deleting') : t('room.delete_room')}
              </Button>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleExitRoom}
                disabled={leaveRoomMutation.isPending}
                className="text-destructive hover:text-destructive hover:bg-destructive/10"
              >
                {leaveRoomMutation.isPending ? t('room.exiting') : t('room.exit_room')}
              </Button>
            )}
          </div>
        </div>

        {/* Status Bar */}
        <div className="glass-panel border-border/30 rounded-xl p-4 mb-6 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm font-medium text-green-600 dark:text-green-400">{t('room.waiting')}</span>
            </div>
            <span className="text-sm text-muted-foreground">
              {t('room.current_players', { current: roomDetail.players.length, max: totalSlots })}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              {Array.from({ length: totalSlots }).map((_, i) => (
                <div
                  key={i}
                  className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
                    i < readyCount
                      ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]'
                      : i < roomDetail.players.length
                      ? 'bg-yellow-500/60'
                      : 'bg-muted/40'
                  }`}
                />
              ))}
            </div>
            <span className="text-xs text-muted-foreground tabular-nums">
              {readyCount}/{roomDetail.players.length} {t('room.ready')}
            </span>
          </div>
        </div>

        {/* Players Grid */}
        <div className="mb-8">
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-4">
            {roomDetail.players.map((player, index) => {
              const isMe = player.player_id === playerId;
              const initials = player.nickname ? player.nickname.slice(0, 2).toUpperCase() : '?';

              return (
                <div
                  key={player.id}
                  className={`flex flex-col items-center gap-2 p-4 rounded-xl transition-all duration-300 animate-fade-in-up glass-panel ${
                    isMe ? 'ring-2 ring-accent/50 bg-accent/5' : 'border-border/30'
                  }`}
                  style={{ animationDelay: `${index * 0.05}s` }}
                >
                  {/* Avatar */}
                  <div className={`relative w-14 h-14 rounded-full flex items-center justify-center text-lg font-bold transition-all duration-300 ${
                    player.is_ready
                      ? 'bg-green-500/20 text-green-600 dark:text-green-400 ring-2 ring-green-500/40'
                      : 'bg-muted/50 text-muted-foreground'
                  }`}>
                    {initials}
                    {player.is_creator && (
                      <div className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-yellow-500 flex items-center justify-center shadow-sm">
                        <svg viewBox="0 0 24 24" className="w-3 h-3 text-yellow-950" fill="currentColor">
                          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                        </svg>
                      </div>
                    )}
                    {player.is_ready && (
                      <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-green-500 flex items-center justify-center shadow-sm">
                        <svg viewBox="0 0 24 24" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="3">
                          <path d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    )}
                  </div>

                  {/* Name */}
                  <div className="text-center">
                    <p className="text-sm font-medium text-foreground truncate max-w-[80px]">
                      {player.nickname}
                    </p>
                    {isMe && (
                      <span className="text-[10px] font-semibold text-accent uppercase tracking-wider">
                        {t('room.you')}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Empty slots */}
            {Array.from({ length: Math.max(0, totalSlots - roomDetail.players.length) }).map((_, index) => (
              <div
                key={`empty-${index}`}
                className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-dashed border-border/20 animate-fade-in"
                style={{ animationDelay: `${(roomDetail.players.length + index) * 0.05}s` }}
              >
                <div className="w-14 h-14 rounded-full bg-muted/20 flex items-center justify-center">
                  <span className="text-2xl text-muted-foreground/30">?</span>
                </div>
                <p className="text-xs text-muted-foreground/50">{t('room.wait_join')}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="glass-panel border-border/30 rounded-xl p-5">
          <div className="flex flex-wrap gap-3 justify-center">
            <Button
              onClick={handleReady}
              disabled={readyMutation.isPending}
              variant={myPlayer?.is_ready ? 'outline' : 'default'}
              className={`min-w-[140px] h-11 font-semibold transition-all duration-300 ${
                myPlayer?.is_ready
                  ? 'border-border/50'
                  : 'shadow-lg hover:shadow-xl'
              }`}
            >
              {readyMutation.isPending
                ? t('room.processing')
                : myPlayer?.is_ready
                ? t('room.cancel_ready')
                : t('room.ready_btn')}
            </Button>

            {isCreator && (
              <>
                <Button
                  onClick={handleStartGame}
                  disabled={!hasEnoughPlayers || !allReady || startGameMutation.isPending}
                  className="min-w-[140px] h-11 font-semibold bg-green-600 hover:bg-green-500 shadow-lg hover:shadow-xl transition-all duration-300"
                >
                  {startGameMutation.isPending ? t('room.starting') : t('room.start_game')}
                </Button>

                <Button
                  onClick={handleStartGameWithAI}
                  disabled={startGameWithAIMutation.isPending}
                  variant="outline"
                  className="min-w-[140px] h-11 font-semibold border-accent/40 text-accent hover:bg-accent/10 transition-all duration-300"
                  title={t('room.fill_ai_tooltip')}
                >
                  {startGameWithAIMutation.isPending ? t('room.starting') : t('room.fill_ai_start')}
                </Button>
              </>
            )}
          </div>

          {!hasEnoughPlayers && (
            <p className="text-center text-sm text-yellow-600 dark:text-yellow-400 mt-3">
              {t('room.need_players', { count: totalSlots - roomDetail.players.length })}
            </p>
          )}
        </div>

        {/* Tips */}
        <div className="mt-6 text-center text-muted-foreground/60 text-xs space-y-0.5">
          <p>{t('room.tip_host')}</p>
          <p>{t('room.tip_fill_ai')}</p>
        </div>
      </div>
    </div>
  );
}
