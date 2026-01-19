/**
 * Room Waiting Page - waiting room before game starts
 */
import { useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { getRoomDetail, toggleReady, startGame, deleteRoom, leaveRoom } from '@/services/roomApi';
import { getPlayerId } from '@/utils/player';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

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

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_API_URL
      ? new URL(import.meta.env.VITE_API_URL).host
      : window.location.host;
    const wsUrl = `${protocol}//${host}/api/ws/room/${roomId}`;

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
  const hasEnoughPlayers = (roomDetail?.players.length || 0) >= 9;

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
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-foreground text-xl">{t('room.loading')}</p>
      </div>
    );
  }

  if (!roomDetail) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <p className="text-foreground text-xl mb-4">{t('room.room_not_found')}</p>
          <Button onClick={() => navigate('/')}>{t('room.back_to_lobby')}</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="text-center mb-6 relative">
          <div className="absolute right-0 top-0">
            <LanguageSwitcher />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-2">
            {roomDetail.room.name}
          </h1>
          <p className="text-muted-foreground">
            {t('room.creator')}: {roomDetail.room.creator_nickname}
          </p>
          <div className="mt-4 flex gap-2 justify-center">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/')}
              className="border-border text-foreground hover:bg-accent"
            >
              {t('room.back_to_lobby')}
            </Button>
            {isCreator ? (
              <Button
                variant="outline"
                size="sm"
                onClick={handleDeleteRoom}
                disabled={deleteRoomMutation.isPending}
                className="border-red-600 text-red-400 hover:bg-red-900/20"
              >
                {deleteRoomMutation.isPending ? t('room.deleting') : t('room.delete_room')}
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={handleExitRoom}
                disabled={leaveRoomMutation.isPending}
                className="border-red-600 text-red-400 hover:bg-red-900/20"
              >
                {leaveRoomMutation.isPending ? t('room.exiting') : t('room.exit_room')}
              </Button>
            )}
          </div>
        </div>

        {/* Room Status Card */}
        <Card className="mb-8 bg-card border-border">
          <CardHeader>
            <CardTitle className="text-card-foreground flex items-center justify-between">
              <span>{t('room.status')}</span>
              <Badge variant="outline" className="text-green-500 border-green-500">
                {t('room.waiting')}
              </Badge>
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              {t('room.current_players', { current: roomDetail.players.length, max: roomDetail.room.max_players })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('room.ready_count')}</span>
                <span className="text-foreground font-semibold">
                  {roomDetail.players.filter(p => p.is_ready).length}/{roomDetail.players.length}
                </span>
              </div>
              {!hasEnoughPlayers && (
                <div className="text-yellow-400 text-center py-2">
                  {t('room.need_players', { count: roomDetail.room.max_players - roomDetail.players.length })}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Players Grid */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-foreground mb-4">{t('room.player_list')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {roomDetail.players.map((player, index) => (
              <Card
                key={player.id}
                className={`bg-card border-2 transition-colors ${
                  player.is_ready
                    ? 'border-green-500'
                    : 'border-border'
                } ${
                  player.player_id === playerId
                    ? 'ring-2 ring-purple-500'
                    : ''
                }`}
              >
                <CardHeader>
                  <CardTitle className="text-card-foreground text-base flex items-center gap-2">
                    <span>{t('room.seat', { index: index + 1 })}</span>
                    {player.is_creator && (
                      <Badge variant="outline" className="text-yellow-500 border-yellow-500">
                        {t('room.host')}
                      </Badge>
                    )}
                    {player.player_id === playerId && (
                      <Badge variant="outline" className="text-purple-500 border-purple-500">
                        {t('room.you')}
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription className="text-muted-foreground">
                    {player.nickname}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-center">
                    {player.is_ready ? (
                      <Badge className="bg-green-600 hover:bg-green-700">
                        {t('room.ready')}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-muted-foreground border-border">
                        {t('room.not_ready')}
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}

            {/* Empty slots */}
            {Array.from({ length: Math.max(0, roomDetail.room.max_players - roomDetail.players.length) }).map((_, index) => (
              <Card key={`empty-${index}`} className="bg-card/50 border-dashed border-border">
                <CardHeader>
                  <CardTitle className="text-muted-foreground text-base">
                    {t('room.seat', { index: roomDetail.players.length + index + 1 })}
                  </CardTitle>
                  <CardDescription className="text-muted-foreground">
                    {t('room.wait_join')}
                  </CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-4 justify-center">
          <Button
            onClick={handleReady}
            disabled={readyMutation.isPending}
            variant={myPlayer?.is_ready ? 'outline' : 'default'}
            className={
              myPlayer?.is_ready
                ? 'border-border text-foreground hover:bg-accent'
                : 'bg-primary hover:bg-primary/90'
            }
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
                disabled={
                  !hasEnoughPlayers ||
                  !allReady ||
                  startGameMutation.isPending
                }
                className="bg-green-600 hover:bg-green-700"
              >
                {startGameMutation.isPending
                  ? t('room.starting')
                  : t('room.start_game')}
              </Button>

              <Button
                onClick={handleStartGameWithAI}
                disabled={startGameWithAIMutation.isPending}
                className="bg-cyan-600 hover:bg-cyan-700"
                title={t('room.fill_ai_tooltip')}
              >
                {startGameWithAIMutation.isPending
                  ? t('room.starting')
                  : t('room.fill_ai_start')}
              </Button>
            </>
          )}
        </div>

        {/* Tips */}
        <div className="mt-8 text-center text-muted-foreground text-sm space-y-1">
          <p>{t('room.tip_host')}</p>
          <p>{t('room.tip_fill_ai')}</p>
          <p>{t('room.tip_player_count')}</p>
        </div>
      </div>
    </div>
  );
}
