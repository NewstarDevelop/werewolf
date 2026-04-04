import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api-client';

interface HistoryListItem {
  id: number;
  room_id: number;
  mode: string;
  winner: string | null;
  player_count: number;
  duration_seconds: number | null;
  finished_at: string | null;
}

interface HistoryListResponse {
  items: HistoryListItem[];
  total: number;
  page: number;
  page_size: number;
}

interface HistoryParticipant {
  seat: number;
  nickname: string;
  role: string;
  faction: string;
  is_ai: boolean;
  survived: boolean;
}

interface HistoryDetail {
  id: number;
  room_id: number;
  mode: string;
  winner: string | null;
  player_count: number;
  duration_seconds: number | null;
  finished_at: string | null;
  participants: HistoryParticipant[];
  events: { type: string; phase: string; round: number; data: Record<string, unknown>; timestamp: string }[];
}

export default function HistoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data, isLoading } = useQuery<HistoryListResponse>({
    queryKey: ['history', page],
    queryFn: () => api.get(`/game-history/?page=${page}&page_size=10`),
  });

  const { data: detail } = useQuery<HistoryDetail>({
    queryKey: ['history-detail', selectedId],
    queryFn: () => api.get(`/game-history/${selectedId}`),
    enabled: !!selectedId,
  });

  const items = data?.items ?? [];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Game History</h1>
          <button onClick={() => navigate('/lobby')} className="text-sm text-gray-500 hover:underline">
            Back to Lobby
          </button>
        </div>

        {isLoading && <p className="text-gray-500">Loading...</p>}

        {!isLoading && items.length === 0 && (
          <div className="text-center py-20 text-gray-400">No games played yet.</div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          {/* List */}
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelectedId(item.id)}
                className={`bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-md transition ${
                  selectedId === item.id ? 'ring-2 ring-blue-500' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold">Game #{item.id}</h3>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      item.winner === 'village'
                        ? 'bg-green-100 text-green-700'
                        : item.winner === 'wolf'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {item.winner === 'village' ? 'Village Win' : item.winner === 'wolf' ? 'Wolf Win' : 'N/A'}
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  {item.mode === 'classic_9' ? '9 Players' : '12 Players'} · {item.player_count} players
                  {item.duration_seconds != null && ` · ${Math.floor(item.duration_seconds / 60)}m ${item.duration_seconds % 60}s`}
                </div>
                {item.finished_at && (
                  <div className="text-xs text-gray-400 mt-1">
                    {new Date(item.finished_at).toLocaleString()}
                  </div>
                )}
              </div>
            ))}

            {/* Pagination */}
            {data && data.total > data.page_size && (
              <div className="flex items-center justify-center gap-2 pt-4">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                  className="px-3 py-1 border rounded text-sm disabled:opacity-30"
                >
                  Prev
                </button>
                <span className="text-sm text-gray-500">
                  Page {page} / {Math.ceil(data.total / data.page_size)}
                </span>
                <button
                  disabled={page * data.page_size >= data.total}
                  onClick={() => setPage(page + 1)}
                  className="px-3 py-1 border rounded text-sm disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            )}
          </div>

          {/* Detail */}
          <div>
            {selectedId && detail ? (
              <div className="bg-white rounded-lg shadow p-5">
                <h2 className="text-lg font-bold mb-3">
                  Game #{detail.id} Detail
                  <span className="ml-2 text-sm font-normal text-gray-500">
                    {detail.mode === 'classic_9' ? '9 Players' : '12 Players'}
                    {detail.duration_seconds != null &&
                      ` · ${Math.floor(detail.duration_seconds / 60)}m ${detail.duration_seconds % 60}s`}
                  </span>
                </h2>

                <h3 className="font-semibold text-sm text-gray-600 mb-2">Players</h3>
                <div className="space-y-1 mb-4">
                  {detail.participants.map((p) => (
                    <div key={p.seat} className="flex items-center justify-between text-sm py-1 border-b border-gray-100">
                      <div>
                        <span className="text-gray-400 mr-2">#{p.seat}</span>
                        <span>{p.nickname}</span>
                        {p.is_ai && <span className="ml-1 text-xs text-gray-400">(AI)</span>}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          p.faction === 'wolf' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                        }`}>
                          {p.role}
                        </span>
                        <span className={`text-xs ${p.survived ? 'text-green-600' : 'text-red-400'}`}>
                          {p.survived ? 'Survived' : 'Dead'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <h3 className="font-semibold text-sm text-gray-600 mb-2">Event Log</h3>
                <div className="h-64 overflow-y-auto bg-gray-50 rounded p-3 text-xs space-y-1">
                  {detail.events.map((e, i) => (
                    <div key={i} className="flex gap-2 py-0.5">
                      <span className="text-gray-400 w-20 shrink-0">
                        R{e.round} {e.phase.replace('_', ' ')}
                      </span>
                      <span className="font-medium capitalize w-24 shrink-0">{e.type.replace('_', ' ')}</span>
                      <span className="text-gray-600 truncate">
                        {e.type === 'death'
                          ? `${(e.data as Record<string, unknown>).nickname || ''} died`
                          : e.type === 'speech'
                            ? `${(e.data as Record<string, unknown>).nickname || ''}: ${(e.data as Record<string, unknown>).content || ''}`
                            : e.type === 'vote_result'
                              ? ((e.data as Record<string, unknown>).tied ? 'Tied vote' : `${(e.data as Record<string, unknown>).nickname || ''} eliminated`)
                              : e.type === 'hunter_shot'
                                ? `Hunter shot ${(e.data as Record<string, unknown>).nickname || ''}`
                                : e.type === 'seer_result'
                                  ? `Checked ${(e.data as Record<string, unknown>).seat}: ${(e.data as Record<string, unknown>).result || ''}`
                                  : ''
                        }
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow p-5 text-center text-gray-400">
                {selectedId ? 'Loading...' : 'Select a game to view details'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
