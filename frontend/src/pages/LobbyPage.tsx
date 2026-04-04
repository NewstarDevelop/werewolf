import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../lib/api-client';
import type { RoomListResponse, RoomCreateRequest } from '../types';

export default function LobbyPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [createError, setCreateError] = useState('');

  const { data, isLoading, error } = useQuery<RoomListResponse>({
    queryKey: ['rooms'],
    queryFn: () => api.get('/rooms/'),
    refetchInterval: 5_000,
  });

  const createMutation = useMutation({
    mutationFn: (body: RoomCreateRequest) => api.post<{ id: number }>('/rooms/', body),
    onSuccess: (data) => {
      setShowCreate(false);
      setCreateError('');
      qc.invalidateQueries({ queryKey: ['rooms'] });
      navigate(`/room/${data.id}`);
    },
    onError: (err) => {
      if (err instanceof ApiError) setCreateError(err.detail || err.error);
      else setCreateError('Failed to create room');
    },
  });

  const rooms = data?.items ?? [];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Lobby</h1>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/history')}
              className="px-4 py-2 text-sm border rounded hover:bg-gray-100 transition"
            >
              History
            </button>
            <button
              onClick={() => navigate('/settings')}
              className="px-4 py-2 text-sm border rounded hover:bg-gray-100 transition"
            >
              Settings
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition"
            >
              Create Room
            </button>
          </div>
        </div>

        {isLoading && <p className="text-gray-500">Loading rooms...</p>}
        {error && <p className="text-red-600">Failed to load rooms</p>}

        {!isLoading && rooms.length === 0 && (
          <div className="text-center py-20 text-gray-400">
            No rooms available. Create one to start playing!
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {rooms.map((room) => (
            <div
              key={room.id}
              className="bg-white rounded-lg shadow p-5 hover:shadow-md transition cursor-pointer"
              onClick={() => navigate(`/room/${room.id}`)}
            >
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-lg truncate">{room.name}</h3>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    room.status === 'waiting'
                      ? 'bg-green-100 text-green-700'
                      : room.status === 'playing'
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {room.status}
                </span>
              </div>
              <div className="text-sm text-gray-500 space-y-1">
                <p>
                  {room.mode === 'classic_9' ? '9 Players' : '12 Players'}
                  {room.variant ? ` · ${room.variant}` : ''}
                </p>
                <p>
                  {room.player_count}/{room.max_players} players
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {showCreate && (
        <CreateRoomModal
          onSubmit={(body) => createMutation.mutate(body)}
          onClose={() => { setShowCreate(false); setCreateError(''); }}
          isLoading={createMutation.isPending}
          error={createError}
        />
      )}
    </div>
  );
}

function CreateRoomModal({
  onSubmit,
  onClose,
  isLoading,
  error,
}: {
  onSubmit: (body: RoomCreateRequest) => void;
  onClose: () => void;
  isLoading: boolean;
  error: string;
}) {
  const [name, setName] = useState('');
  const [mode, setMode] = useState<'classic_9' | 'classic_12'>('classic_9');
  const [variant, setVariant] = useState<'wolf_king' | 'white_wolf_king' | ''>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      name,
      mode,
      variant: variant || undefined,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
        className="bg-white rounded-lg shadow-xl w-full max-w-md p-6"
      >
        <h2 className="text-xl font-bold mb-4">Create Room</h2>

        {error && <div className="mb-4 p-3 text-sm text-red-700 bg-red-50 rounded">{error}</div>}

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Room Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={100}
            className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="My Room"
          />
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Mode</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as 'classic_9' | 'classic_12')}
            className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="classic_9">9 Players (Classic)</option>
            <option value="classic_12">12 Players</option>
          </select>
        </div>

        {mode === 'classic_12' && (
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Variant</label>
            <select
              value={variant}
              onChange={(e) => setVariant(e.target.value as 'wolf_king' | 'white_wolf_king' | '')}
              className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="wolf_king">Wolf King</option>
              <option value="white_wolf_king">White Wolf King</option>
            </select>
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <button type="button" onClick={onClose} className="px-4 py-2 border rounded hover:bg-gray-100 transition">
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition disabled:opacity-50"
          >
            {isLoading ? 'Creating...' : 'Create'}
          </button>
        </div>
      </form>
    </div>
  );
}
