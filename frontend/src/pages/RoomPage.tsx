import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../lib/api-client';
import type { Room, RoomPlayer } from '../types';

export default function RoomPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const {
    data: room,
    isLoading,
    error,
  } = useQuery<Room>({
    queryKey: ['room', roomId],
    queryFn: () => api.get(`/rooms/${roomId}`),
    refetchInterval: 3_000,
    enabled: !!roomId,
  });

  const joinMutation = useMutation({
    mutationFn: () => api.post<Room>(`/rooms/${roomId}/join`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['room', roomId] }),
  });

  const leaveMutation = useMutation({
    mutationFn: () => api.post(`/rooms/${roomId}/leave`),
    onSuccess: () => navigate('/lobby'),
  });

  const readyMutation = useMutation({
    mutationFn: () => api.post<{ is_ready: boolean }>(`/rooms/${roomId}/ready`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['room', roomId] }),
  });

  const fillAiMutation = useMutation({
    mutationFn: (count: number) => api.post<Room>(`/rooms/${roomId}/fill-ai`, { count }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['room', roomId] }),
  });

  const startMutation = useMutation({
    mutationFn: () => api.post<{ game_id: number }>(`/rooms/${roomId}/start`),
    onSuccess: (data) => navigate(`/game/${data.game_id}`),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/rooms/${roomId}`),
    onSuccess: () => navigate('/lobby'),
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading room...</p>
      </div>
    );
  }

  if (error || !room) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
        <p className="text-red-600">
          {error instanceof ApiError ? error.detail : 'Room not found'}
        </p>
        <button onClick={() => navigate('/lobby')} className="text-blue-600 hover:underline">
          Back to Lobby
        </button>
      </div>
    );
  }

  const playerCount = room.players.length;
  const allReady = room.players.every((p) => p.is_ready);
  const isFull = playerCount >= room.max_players;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <button onClick={() => navigate('/lobby')} className="text-sm text-gray-500 hover:underline mb-2">
              &larr; Back to Lobby
            </button>
            <h1 className="text-2xl font-bold">{room.name}</h1>
            <p className="text-sm text-gray-500 mt-1">
              {room.mode === 'classic_9' ? '9 Players' : '12 Players'}
              {room.variant ? ` · ${room.variant}` : ''} · {playerCount}/{room.max_players}
            </p>
          </div>
          <div className="flex gap-2">
            {room.status === 'waiting' && (
              <button
                onClick={() => joinMutation.mutate()}
                disabled={joinMutation.isPending || isFull}
                className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition disabled:opacity-50"
              >
                Join
              </button>
            )}
            {room.status === 'waiting' && (
              <button
                onClick={() => leaveMutation.mutate()}
                disabled={leaveMutation.isPending}
                className="px-4 py-2 text-sm border border-red-300 text-red-600 rounded hover:bg-red-50 transition disabled:opacity-50"
              >
                Leave
              </button>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <h2 className="font-semibold">Players ({playerCount}/{room.max_players})</h2>
          </div>
          <div className="divide-y">
            {room.players.map((player) => (
              <PlayerRow key={player.seat} player={player} />
            ))}
            {Array.from({ length: room.max_players - playerCount }).map((_, i) => (
              <div key={`empty-${i}`} className="px-4 py-3 text-sm text-gray-300">
                Seat {playerCount + i} — Empty
              </div>
            ))}
          </div>
        </div>

        {room.status === 'waiting' && (
          <div className="mt-6 flex gap-3 justify-center">
            <button
              onClick={() => readyMutation.mutate()}
              disabled={readyMutation.isPending}
              className="px-6 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 transition disabled:opacity-50"
            >
              Toggle Ready
            </button>
            <button
              onClick={() => fillAiMutation.mutate(room.max_players - playerCount)}
              disabled={fillAiMutation.isPending || isFull}
              className="px-6 py-2 border rounded hover:bg-gray-100 transition disabled:opacity-50"
            >
              Fill AI
            </button>
            <button
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending || !isFull || !allReady}
              className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition disabled:opacity-50"
            >
              Start Game
            </button>
            <button
              onClick={() => {
                if (confirm('Delete this room?')) deleteMutation.mutate();
              }}
              disabled={deleteMutation.isPending}
              className="px-6 py-2 border border-red-300 text-red-600 rounded hover:bg-red-50 transition disabled:opacity-50"
            >
              Delete
            </button>
          </div>
        )}

        {room.status === 'playing' && (
          <div className="mt-6 text-center">
            <p className="text-yellow-600 font-semibold mb-3">Game in progress!</p>
            <button
              onClick={() => navigate(`/game/${room.id}`)}
              className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
            >
              Watch Game
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function PlayerRow({ player }: { player: RoomPlayer }) {
  return (
    <div className="px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-400 w-8">#{player.seat}</span>
        <span className="font-medium">
          {player.is_ai ? `AI (${player.ai_provider || 'mock'})` : `Player ${player.user_id}`}
        </span>
      </div>
      <span
        className={`text-xs px-2 py-0.5 rounded-full ${
          player.is_ready ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
        }`}
      >
        {player.is_ready ? 'Ready' : 'Not Ready'}
      </span>
    </div>
  );
}
