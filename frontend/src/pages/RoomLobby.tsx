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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { createRoom, getRooms, joinRoom, getRoomDetail } from '@/services/roomApi';
import { getPlayerId, getNickname, setNickname as saveNickname } from '@/utils/player';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { authService } from '@/services/authService';
import { useAuth } from '@/contexts/AuthContext';
import { z } from 'zod';
import { GameMode, WolfKingVariant } from '@/services/api';

const nicknameSchema = z.string()
  .min(1, 'Nickname is required')
  .max(20, 'Nickname too long (max 20 characters)')
  .regex(/^[^<>]*$/, 'Invalid characters in nickname');

const roomNameSchema = z.string()
  .max(50, 'Room name too long (max 50 characters)')
  .regex(/^[^<>]*$/, 'Invalid characters in room name');

export default function RoomLobby() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation('common');
  const { user, isAuthenticated, logout: authLogout } = useAuth();
  const playerId = getPlayerId();

  const [nickname, setNickname] = useState(getNickname() || '');
  const [roomName, setRoomName] = useState('');
  const [gameMode, setGameMode] = useState<GameMode>('classic_9');
  const [wolfKingVariant, setWolfKingVariant] = useState<WolfKingVariant>('wolf_king');

  // Auto-save nickname when changed
  useEffect(() => {
    if (nickname) {
      saveNickname(nickname);
    }
  }, [nickname]);

  // Query rooms list (refresh every 3 seconds, stop when window loses focus)
  const { data: rooms, refetch } = useQuery({
    queryKey: ['rooms'],
    queryFn: () => getRooms('waiting'),
    refetchInterval: 3000,
    refetchIntervalInBackground: false,  // P2-2: Stop polling when window loses focus
  });

  // Create room mutation
  const createRoomMutation = useMutation({
    mutationFn: createRoom,
    onSuccess: (data) => {
      toast.success(t('room.room_created'));
      navigate(`/room/${data.room.id}/waiting`);
    },
    onError: (error: Error) => {
      toast.error(t('room.room_create_failed'), { description: error.message });
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

  const handleCreateRoom = () => {
    const nicknameResult = nicknameSchema.safeParse(nickname.trim());
    if (!nicknameResult.success) {
      toast.error(nicknameResult.error.errors[0].message);
      return;
    }

    const roomNameValue = roomName.trim() || t('room.default_room_name', { name: nickname });
    const roomNameResult = roomNameSchema.safeParse(roomNameValue);
    if (!roomNameResult.success) {
      toast.error(roomNameResult.error.errors[0].message);
      return;
    }

    createRoomMutation.mutate({
      name: roomNameResult.data,
      creator_nickname: nicknameResult.data,
      creator_id: playerId,
      game_mode: gameMode,
      wolf_king_variant: gameMode === 'classic_12' ? wolfKingVariant : undefined,
      language: i18n.language,
    });
  };

  const handleJoinRoom = async (roomId: string) => {
    const nicknameResult = nicknameSchema.safeParse(nickname.trim());
    if (!nicknameResult.success) {
      toast.error(nicknameResult.error.errors[0].message);
      return;
    }

    // 检查已登录用户是否已在房间中
    try {
      const currentUser = await authService.getCurrentUser();
      if (currentUser) {
        // 获取房间详情
        const roomDetail = await getRoomDetail(roomId);

        // 检查当前用户的user_id是否已在房间中
        const alreadyInRoom = roomDetail.players.some(
          (p) => p.user_id === currentUser.id
        );

        if (alreadyInRoom) {
          toast.error(t('room.already_in_room'), {
            description: t('room.cannot_join_twice'),
            action: {
              label: t('room.enter_room'),
              onClick: () => navigate(`/room/${roomId}/waiting`),
            },
          });
          return;
        }
      }
    } catch (error) {
      // 区分不同类型的错误
      if (error instanceof Error) {
        if (error.message.includes('Unauthorized') || error.message.includes('401')) {
          // 未登录用户，跳过检查（后端会生成新的player_id）
          console.debug('User not authenticated, skipping duplicate check');
        } else {
          // 其他错误（如网络错误、房间不存在等），记录但允许继续尝试加入
          // 后端会进行最终校验
          console.warn('Failed to check room membership:', error.message);
        }
      } else {
        console.warn('Failed to check room membership:', error);
      }
    }

    joinRoomMutation.mutate({ roomId, nickname: nicknameResult.data });
  };

  const handleLogout = async () => {
    try {
      await authLogout();
      toast.success(t('auth.logout_success', { defaultValue: '已退出登录' }));
      navigate('/');
    } catch (error) {
      toast.error(t('auth.logout_failed', { defaultValue: '退出登录失败' }));
    }
  };

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Ambient background effect */}
      <div className="absolute inset-0 bg-gradient-to-b from-background via-background/90 to-background z-0" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-background to-background z-0" />

      <div className="container relative z-10 mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8 relative">
          <div className="absolute right-0 top-0 flex items-center gap-2">
            {isAuthenticated && user && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground mr-2">
                <span>{user.nickname}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/history')}
                  className="h-8"
                >
                  {t('history.title')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLogout}
                  className="h-8"
                >
                  {t('auth.logout', { defaultValue: '退出登录' })}
                </Button>
              </div>
            )}
            <LanguageSwitcher />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-4 font-display tracking-tight">
            {t('room.title')}
          </h1>
          <p className="text-muted-foreground">
            {t('room.subtitle')}
          </p>
        </div>

        {/* Nickname and Create Room Section */}
        <Card className="mb-8 bg-card/50 border-border backdrop-blur-sm">
          <CardHeader>
            <CardTitle>{t('room.player_info')}</CardTitle>
            <CardDescription>
              {t('room.player_info_desc')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Nickname Input */}
            <div>
              <Label htmlFor="nickname">{t('room.nickname')}</Label>
              <Input
                id="nickname"
                placeholder={t('room.nickname_placeholder')}
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                className="mt-2"
              />
            </div>

            {/* Room Name Input */}
            <div>
              <Label htmlFor="roomName">{t('room.room_name')}</Label>
              <Input
                id="roomName"
                placeholder={t('room.room_name_placeholder')}
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                className="mt-2"
              />
            </div>

            {/* Game Mode Selection */}
            <div className="space-y-3 pt-2">
              <Label>{t('room.game_mode')}</Label>
              <RadioGroup
                value={gameMode}
                onValueChange={(v) => setGameMode(v as GameMode)}
                className="flex flex-col gap-2"
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="classic_9" id="mode_9" />
                  <Label htmlFor="mode_9">{t('room.mode_classic_9')}</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="classic_12" id="mode_12" />
                  <Label htmlFor="mode_12">{t('room.mode_classic_12')}</Label>
                </div>
              </RadioGroup>
            </div>

            {/* Wolf King Variant Selection (Only for 12 players) */}
            {gameMode === 'classic_12' && (
              <div className="space-y-3 pt-2 pl-4 border-l-2 border-accent/20">
                <Label>{t('room.wolf_king_variant')}</Label>
                <RadioGroup
                  value={wolfKingVariant}
                  onValueChange={(v) => setWolfKingVariant(v as WolfKingVariant)}
                  className="flex flex-col gap-2"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="wolf_king" id="wk_normal" />
                    <Label htmlFor="wk_normal">{t('room.variant_wolf_king')}</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="white_wolf_king" id="wk_white" />
                    <Label htmlFor="wk_white">{t('room.variant_white_wolf_king')}</Label>
                  </div>
                </RadioGroup>
              </div>
            )}

            {/* Create Button */}
            <Button
              onClick={handleCreateRoom}
              disabled={!nickname.trim() || createRoomMutation.isPending}
              className="w-full"
            >
              {createRoomMutation.isPending ? t('room.creating') : t('room.create_room')}
            </Button>
          </CardContent>
        </Card>

        {/* Room List */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-foreground">
            {t('room.waiting_rooms')} ({rooms?.length || 0})
          </h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
          >
            {t('room.refresh')}
          </Button>
        </div>

        {/* Room Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rooms?.length === 0 && (
            <div className="col-span-full text-center py-12">
              <p className="text-muted-foreground text-lg">{t('room.no_rooms')}</p>
              <p className="text-muted-foreground/60 mt-2">{t('room.create_hint')}</p>
            </div>
          )}

          {rooms?.map((room) => (
            <Card
              key={room.id}
              className="bg-card/50 border-border hover:border-accent transition-colors backdrop-blur-sm"
            >
              <CardHeader>
                <CardTitle className="text-lg">{room.name}</CardTitle>
                <CardDescription>
                  {t('room.creator')}: {room.creator_nickname}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t('room.player_count')}</span>
                    <span className="text-foreground font-semibold">
                      {room.current_players}/{room.max_players}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t('room.status')}</span>
                    <span className="text-green-500 font-semibold">
                      {t('room.waiting')}
                    </span>
                  </div>

                  <Button
                    className="w-full"
                    variant={room.current_players >= room.max_players ? "secondary" : "default"}
                    onClick={() => handleJoinRoom(room.id)}
                    disabled={
                      !nickname.trim() ||
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
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
