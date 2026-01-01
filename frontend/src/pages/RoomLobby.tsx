/**
 * Room Lobby Page - displays room list and allows creating/joining rooms
 */
import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { createRoom, getRooms, joinRoom } from '@/services/roomApi';
import { getPlayerId, getNickname, setNickname as saveNickname } from '@/utils/player';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { z } from 'zod';

const nicknameSchema = z.string()
  .min(1, 'Nickname is required')
  .max(20, 'Nickname too long (max 20 characters)')
  .regex(/^[^<>]*$/, 'Invalid characters in nickname');

const roomNameSchema = z.string()
  .max(50, 'Room name too long (max 50 characters)')
  .regex(/^[^<>]*$/, 'Invalid characters in room name');

export default function RoomLobby() {
  const navigate = useNavigate();
  const { t } = useTranslation('common');
  const playerId = getPlayerId();

  const [nickname, setNickname] = useState(getNickname() || '');
  const [roomName, setRoomName] = useState('');

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
    });
  };

  const handleJoinRoom = (roomId: string) => {
    const nicknameResult = nicknameSchema.safeParse(nickname.trim());
    if (!nicknameResult.success) {
      toast.error(nicknameResult.error.errors[0].message);
      return;
    }

    joinRoomMutation.mutate({ roomId, nickname: nicknameResult.data });
  };

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Ambient background effect */}
      <div className="absolute inset-0 bg-gradient-to-b from-background via-background/90 to-background z-0" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-background to-background z-0" />

      <div className="container relative z-10 mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8 relative">
          <div className="absolute right-0 top-0">
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
