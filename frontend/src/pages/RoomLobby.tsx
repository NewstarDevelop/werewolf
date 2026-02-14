/**
 * Room Lobby Page - displays room list and allows creating/joining rooms
 */
import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { createRoom, getRooms, joinRoom } from '@/services/roomApi';
import { getPlayerId } from '@/utils/player';
import { useAuth } from '@/contexts/AuthContext';
import { z } from 'zod';
import { GameMode, WolfKingVariant, ApiError } from '@/services/api';

const roomNameSchema = z.string()
  .max(50, 'Room name too long (max 50 characters)')
  .regex(/^[^<>]*$/, 'Invalid characters in room name');

export default function RoomLobby() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation('common');
  const { user, isAuthenticated, isLoading } = useAuth();
  const playerId = getPlayerId();

  const [roomName, setRoomName] = useState('');
  const [gameMode, setGameMode] = useState<GameMode>('classic_9');
  const [wolfKingVariant, setWolfKingVariant] = useState<WolfKingVariant>('wolf_king');

  // 濡傛灉鐢ㄦ埛鏈櫥褰曪紝閲嶅畾鍚戝埌鐧诲綍椤碉紙绛夊緟鍔犺浇瀹屾垚鍚庡啀鍒ゆ柇锛?
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      toast.error(t('auth.login_required'), {
        description: t('auth.login_required_desc'),
      });
      navigate('/login');
    }
  }, [isAuthenticated, isLoading, navigate, t]);

  // Query rooms list (refresh every 3 seconds, stop when window loses focus)
  // Query rooms list (poll every 3s only when authenticated)
  const { data: rooms, refetch } = useQuery({
    queryKey: ['rooms'],
    queryFn: () => getRooms('waiting'),
    enabled: !isLoading && isAuthenticated,
    refetchInterval: !isLoading && isAuthenticated ? 3000 : false,
    refetchIntervalInBackground: false,
  });

  // Create room mutation
  const createRoomMutation = useMutation({
    mutationFn: createRoom,
    onSuccess: (data) => {
      toast.success(t('room.room_created'));
      navigate(`/room/${data.room.id}/waiting`);
    },
    onError: (error: ApiError) => {
      // 澶勭悊 409 鍐茬獊閿欒锛堢敤鎴峰凡鏈夋椿璺冩埧闂达級
      if (error.response?.status === 409) {
        toast.error(t('room.room_limit_reached', { defaultValue: 'You already have an active room' }), {
          description: error.response?.data?.detail || error.message,
        });
      } else {
        toast.error(t('room.room_create_failed'), { description: error.message });
      }
    },
  });

  // Join room mutation
  const joinRoomMutation = useMutation({
    mutationFn: ({ roomId, nickname }: { roomId: string; nickname: string }) =>
      joinRoom(roomId, { player_id: playerId, nickname }),
    onSuccess: (_, variables) => {
      toast.success(t('room.joined_room'));
      navigate(`/room/${variables.roomId}/waiting`);
    },
    onError: (error: Error) => {
      toast.error(t('room.join_failed'), { description: error.message });
    },
  });

  // Loading state (hooks must run before any return)
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-4"></div>
          <p className="text-muted-foreground">{t("app.loading")}</p>
        </div>
      </div>
    );
  }


  const handleCreateRoom = () => {
    if (!user) {
      toast.error(t('auth.login_required', { defaultValue: '璇峰厛鐧诲綍' }));
      return;
    }

    const roomNameValue = roomName.trim() || t('room.default_room_name', { name: user.nickname });
    const roomNameResult = roomNameSchema.safeParse(roomNameValue);
    if (!roomNameResult.success) {
      toast.error(roomNameResult.error.errors[0].message);
      return;
    }

    createRoomMutation.mutate({
      name: roomNameResult.data,
      game_mode: gameMode,
      wolf_king_variant: gameMode === 'classic_12' ? wolfKingVariant : undefined,
      language: i18n.language,
    });
  };

  const handleJoinRoom = async (roomId: string) => {
    if (!user) {
      toast.error(t('auth.login_required', { defaultValue: '璇峰厛鐧诲綍' }));
      return;
    }

    // FIX: 绉婚櫎 has_same_user 妫€鏌ワ紝鐩存帴璋冪敤 joinRoom
    // 鍚庣宸蹭慨鏀逛负锛氬鏋滅敤鎴峰凡鍦ㄦ埧闂翠腑锛岃繑鍥炵幇鏈夎褰曞苟绛惧彂鏂?token
    // 杩欐牱鐢ㄦ埛鍙互閲嶆柊鑾峰彇 room token锛堣В鍐宠繑鍥炲ぇ鍘呭悗涓㈠け鏉冮檺鐨勯棶棰橈級
    joinRoomMutation.mutate({ roomId, nickname: user.nickname });
  };

  return (
    <div className="min-h-full relative">
      {/* Ambient background effect */}
      <div className="fixed inset-0 atmosphere-night z-0 pointer-events-none" />
      <div className="fixed inset-0 atmosphere-moonlight z-0 opacity-40 pointer-events-none" />

      <div className="relative z-10 max-w-5xl mx-auto px-4 py-6 md:py-10 animate-fade-in">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground font-display tracking-tight">
            {t('room.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('room.subtitle')}
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Create Room Panel - Sidebar */}
          <div className="lg:col-span-1">
            <Card className="glass-panel border-border/30 animate-slide-up sticky top-6">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  {t('room.create_room')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Room Name Input */}
                <div>
                  <Label htmlFor="roomName" className="text-sm text-muted-foreground">{t('room.room_name')}</Label>
                  <Input
                    id="roomName"
                    placeholder={t('room.room_name_placeholder')}
                    value={roomName}
                    onChange={(e) => setRoomName(e.target.value)}
                    className="mt-1.5 h-10 bg-muted/30 border-border/40 focus:border-accent/60"
                  />
                </div>

                {/* Game Mode Selection */}
                <div className="space-y-2">
                  <Label className="text-sm text-muted-foreground">{t('room.game_mode')}</Label>
                  <RadioGroup
                    value={gameMode}
                    onValueChange={(v) => setGameMode(v as GameMode)}
                    className="grid grid-cols-2 gap-2"
                  >
                    <Label
                      htmlFor="mode_9"
                      className={`flex items-center gap-2 rounded-lg border p-3 cursor-pointer transition-all duration-200 ${
                        gameMode === 'classic_9'
                          ? 'border-accent bg-accent/10 shadow-sm'
                          : 'border-border/40 hover:border-border'
                      }`}
                    >
                      <RadioGroupItem value="classic_9" id="mode_9" />
                      <span className="text-sm font-medium">{t('room.mode_classic_9')}</span>
                    </Label>
                    <Label
                      htmlFor="mode_12"
                      className={`flex items-center gap-2 rounded-lg border p-3 cursor-pointer transition-all duration-200 ${
                        gameMode === 'classic_12'
                          ? 'border-accent bg-accent/10 shadow-sm'
                          : 'border-border/40 hover:border-border'
                      }`}
                    >
                      <RadioGroupItem value="classic_12" id="mode_12" />
                      <span className="text-sm font-medium">{t('room.mode_classic_12')}</span>
                    </Label>
                  </RadioGroup>
                </div>

                {/* Wolf King Variant Selection (Only for 12 players) */}
                {gameMode === 'classic_12' && (
                  <div className="space-y-2 pl-3 border-l-2 border-accent/30 animate-fade-in">
                    <Label className="text-sm text-muted-foreground">{t('room.wolf_king_variant')}</Label>
                    <RadioGroup
                      value={wolfKingVariant}
                      onValueChange={(v) => setWolfKingVariant(v as WolfKingVariant)}
                      className="flex flex-col gap-2"
                    >
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="wolf_king" id="wk_normal" />
                        <Label htmlFor="wk_normal" className="text-sm cursor-pointer">{t('room.variant_wolf_king')}</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="white_wolf_king" id="wk_white" />
                        <Label htmlFor="wk_white" className="text-sm cursor-pointer">{t('room.variant_white_wolf_king')}</Label>
                      </div>
                    </RadioGroup>
                  </div>
                )}

                {/* Create Button */}
                <Button
                  onClick={handleCreateRoom}
                  disabled={!user || createRoomMutation.isPending}
                  className="w-full h-11 text-base font-semibold shadow-lg hover:shadow-xl transition-all duration-300"
                >
                  {createRoomMutation.isPending ? t('room.creating') : t('room.create_room')}
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Room List - Main Content */}
          <div className="lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                {t('room.waiting_rooms')}
                <span className="text-sm font-normal text-muted-foreground">({rooms?.length || 0})</span>
              </h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => refetch()}
                className="text-muted-foreground hover:text-foreground"
              >
                {t('room.refresh')}
              </Button>
            </div>

            {/* Room Cards */}
            {rooms?.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
                <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4">
                  <svg viewBox="0 0 24 24" className="w-8 h-8 text-muted-foreground/50" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M12 3c-1.5 2-3 3.5-3 6a3 3 0 0 0 6 0c0-2.5-1.5-4-3-6Z" />
                    <path d="M12 9c-2 3-4 5.5-4 8a4 4 0 0 0 8 0c0-2.5-2-5-4-8Z" />
                  </svg>
                </div>
                <p className="text-muted-foreground text-lg font-medium">{t('room.no_rooms')}</p>
                <p className="text-muted-foreground/60 mt-1 text-sm">{t('room.create_hint')}</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {rooms?.map((room, index) => (
                  <Card
                    key={room.id}
                    className="glass-panel border-border/30 hover:border-accent/30 hover:shadow-lg transition-all duration-300 animate-fade-in-up group"
                    style={{ animationDelay: `${index * 0.05}s` }}
                  >
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-foreground truncate group-hover:text-accent transition-colors">
                            {room.name}
                          </h3>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {t('room.creator')}: {room.creator_nickname}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-green-500/10 border border-green-500/20 shrink-0 ml-2">
                          <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                          <span className="text-xs font-medium text-green-600 dark:text-green-400">
                            {t('room.waiting')}
                          </span>
                        </div>
                      </div>

                      {/* Player slots visualization */}
                      <div className="flex items-center gap-1.5 mb-4">
                        {Array.from({ length: room.max_players }).map((_, i) => (
                          <div
                            key={i}
                            className={`h-1.5 flex-1 rounded-full transition-colors ${
                              i < room.current_players
                                ? 'bg-accent/70'
                                : 'bg-muted/50'
                            }`}
                          />
                        ))}
                        <span className="text-xs text-muted-foreground ml-1 tabular-nums">
                          {room.current_players}/{room.max_players}
                        </span>
                      </div>

                      <Button
                        className="w-full h-10"
                        variant={room.current_players >= room.max_players ? "secondary" : "default"}
                        onClick={() => handleJoinRoom(room.id)}
                        disabled={
                          !user ||
                          room.current_players >= room.max_players ||
                          joinRoomMutation.isPending
                        }
                      >
                        {room.current_players >= room.max_players
                          ? t('room.room_full')
                          : joinRoomMutation.isPending
                          ? t('room.joining')
                          : t('room.join_room')}
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
