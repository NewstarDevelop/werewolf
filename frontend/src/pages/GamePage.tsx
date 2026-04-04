import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../lib/api-client';

interface PlayerView {
  seat: number;
  nickname: string;
  alive: boolean;
  is_ai: boolean;
  role?: string | null;
}

interface GameEvent {
  type: string;
  phase: string;
  round: number;
  data: Record<string, unknown>;
  timestamp: string;
}

interface GameState {
  game_id: number;
  room_id: number;
  mode: string;
  phase: string;
  round: number;
  winner: string | null;
  my_seat: number;
  my_role: string | null;
  players: PlayerView[];
  events: GameEvent[];
}

type WsMessage =
  | { type: 'state' } & GameState
  | { type: 'action_ack'; action: string }
  | { type: 'hunter_pending'; seat: number }
  | { type: 'speech'; seat: number; nickname: string; content: string }
  | { type: 'vote_cast'; voter: number }
  | { type: 'vote_result' } & Record<string, unknown>
  | { type: 'hunter_shot'; hunter: number; target: number; nickname: string }
  | { type: 'error'; detail: string };

export default function GamePage() {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<GameState | null>(null);
  const [error, setError] = useState('');
  const [speechText, setSpeechText] = useState('');
  const [messages, setMessages] = useState<string[]>([]);

  // Connect WebSocket
  useEffect(() => {
    if (!gameId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/game/${gameId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg: WsMessage = JSON.parse(event.data);

      if (msg.type === 'state') {
        setState(msg as unknown as GameState);
      } else if (msg.type === 'error') {
        setError(msg.detail);
      } else if (msg.type === 'speech') {
        setMessages((prev) => [...prev, `${msg.nickname} (#${msg.seat}): ${msg.content}`]);
      } else if (msg.type === 'vote_cast') {
        setMessages((prev) => [...prev, `Player #${msg.voter} voted.`]);
      } else if (msg.type === 'hunter_shot') {
        setMessages((prev) => [...prev, `Hunter shot ${msg.nickname}!`]);
      } else if (msg.type === 'action_ack') {
        // nothing
      }
    };

    ws.onerror = () => setError('WebSocket connection error');
    ws.onclose = () => {
      setState((prev) => {
        if (prev?.phase !== 'game_over') {
          setError('Disconnected from game');
        }
        return prev;
      });
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId]);

  const sendAction = (action: string, data: Record<string, unknown> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...data }));
    }
  };

  // Fallback: if WebSocket fails, try REST API
  useEffect(() => {
    if (error && gameId && !state) {
      api
        .get<GameState>(`/games/${gameId}/state`)
        .then(setState)
        .catch(() => setError('Failed to load game state'));
    }
  }, [error, gameId, state]);

  if (!state) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        {error ? (
          <div className="text-center">
            <p className="text-red-400 mb-4">{error}</p>
            <button onClick={() => navigate('/lobby')} className="text-blue-400 hover:underline">
              Back to Lobby
            </button>
          </div>
        ) : (
          <p className="text-gray-400">Loading game...</p>
        )}
      </div>
    );
  }

  const alivePlayers = state.players.filter((p) => p.alive);
  const isNight = state.phase === 'night';
  const isDawn = state.phase === 'dawn';
  const isSpeech = state.phase === 'day_speech';
  const isVote = state.phase === 'day_vote';
  const isHunterShot = state.phase === 'hunter_shot';
  const isGameOver = state.phase === 'game_over';

  const myPlayer = state.players.find((p) => p.seat === state.my_seat);
  const isAlive = myPlayer?.alive ?? false;

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">
              Game #{state.game_id} — Round {state.round}
            </h1>
            <p className="text-sm text-gray-400">
              Phase:{' '}
              <span className="capitalize text-yellow-400">{state.phase.replace('_', ' ')}</span>
              {' | '}
              Your role: <span className="text-blue-400 capitalize">{state.my_role || '?'}</span>
              {' | '}
              {alivePlayers.length} alive
            </p>
          </div>
          <button onClick={() => navigate('/lobby')} className="text-sm text-gray-400 hover:text-white">
            Leave
          </button>
        </div>

        {isGameOver && (
          <div className="mb-6 p-4 rounded-lg bg-yellow-900/50 border border-yellow-600 text-center">
            <h2 className="text-2xl font-bold mb-2">
              {state.winner === 'village' ? 'Village Wins!' : 'Wolves Win!'}
            </h2>
            <p className="text-yellow-300">
              {state.winner === 'village'
                ? 'All werewolves have been eliminated.'
                : 'The werewolves have taken over.'}
            </p>
            <button
              onClick={() => navigate('/lobby')}
              className="mt-4 px-6 py-2 bg-blue-600 rounded hover:bg-blue-700"
            >
              Back to Lobby
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Players panel */}
          <div className="lg:col-span-1">
            <div className="bg-gray-800 rounded-lg p-4">
              <h2 className="font-semibold mb-3">Players</h2>
              <div className="space-y-2">
                {state.players.map((p) => (
                  <div
                    key={p.seat}
                    className={`flex items-center justify-between p-2 rounded ${
                      p.seat === state.my_seat ? 'bg-blue-900/40 border border-blue-600' : 'bg-gray-700/50'
                    } ${!p.alive ? 'opacity-40' : ''}`}
                  >
                    <div>
                      <span className="text-sm text-gray-400 mr-2">#{p.seat}</span>
                      <span className="font-medium">{p.nickname}</span>
                      {p.role && p.seat !== state.my_seat && (
                        <span className="ml-2 text-xs text-red-400">({p.role})</span>
                      )}
                      {p.seat === state.my_seat && p.role && (
                        <span className="ml-2 text-xs text-blue-400">({p.role})</span>
                      )}
                    </div>
                    <span className={`text-xs ${p.alive ? 'text-green-400' : 'text-red-400'}`}>
                      {p.alive ? 'Alive' : 'Dead'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Main game area */}
          <div className="lg:col-span-2 space-y-4">
            {/* Night actions */}
            {isNight && isAlive && <NightActionPanel role={state.my_role} sendAction={sendAction} players={alivePlayers} mySeat={state.my_seat} />}

            {/* Dawn */}
            {isDawn && (
              <div className="bg-gray-800 rounded-lg p-4 text-center">
                <p className="text-yellow-400 mb-3">Night has ended. Review the results.</p>
                <button
                  onClick={() => sendAction('start_speech')}
                  className="px-6 py-2 bg-yellow-600 rounded hover:bg-yellow-700"
                >
                  Start Discussion
                </button>
              </div>
            )}

            {/* Speech */}
            {isSpeech && (
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="font-semibold mb-2">Discussion Phase</h3>
                <div className="h-40 overflow-y-auto bg-gray-900 rounded p-2 mb-3 text-sm space-y-1">
                  {messages.length === 0 && <p className="text-gray-500">No messages yet.</p>}
                  {messages.map((msg, i) => (
                    <p key={i} className="text-gray-300">{msg}</p>
                  ))}
                </div>
                {isAlive && (
                  <div className="flex gap-2">
                    <input
                      value={speechText}
                      onChange={(e) => setSpeechText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && speechText.trim()) {
                          sendAction('speech', { content: speechText.trim() });
                          setSpeechText('');
                        }
                      }}
                      placeholder="Type your message..."
                      className="flex-1 px-3 py-2 bg-gray-700 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={() => {
                        if (speechText.trim()) {
                          sendAction('speech', { content: speechText.trim() });
                          setSpeechText('');
                        }
                      }}
                      className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700"
                    >
                      Send
                    </button>
                    <button
                      onClick={() => sendAction('start_vote')}
                      className="px-4 py-2 bg-red-600 rounded hover:bg-red-700"
                    >
                      Start Vote
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Vote */}
            {isVote && isAlive && (
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="font-semibold mb-3">Vote — Select a player to eliminate</h3>
                <div className="grid grid-cols-2 gap-2">
                  {alivePlayers
                    .filter((p) => p.seat !== state.my_seat)
                    .map((p) => (
                      <button
                        key={p.seat}
                        onClick={() => sendAction('vote', { target_seat: p.seat })}
                        className="p-3 bg-gray-700 rounded hover:bg-red-700 transition text-left"
                      >
                        <span className="text-gray-400 mr-2">#{p.seat}</span>
                        {p.nickname}
                      </button>
                    ))}
                </div>
              </div>
            )}

            {/* Hunter shot */}
            {isHunterShot && state.my_role === 'hunter' && isAlive && (
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="font-semibold mb-3 text-yellow-400">Hunter — Choose who to shoot!</h3>
                <div className="grid grid-cols-2 gap-2 mb-3">
                  {alivePlayers
                    .filter((p) => p.seat !== state.my_seat)
                    .map((p) => (
                      <button
                        key={p.seat}
                        onClick={() => sendAction('hunter_shoot', { target_seat: p.seat })}
                        className="p-3 bg-red-900/50 rounded hover:bg-red-700 transition text-left"
                      >
                        #{p.seat} {p.nickname}
                      </button>
                    ))}
                </div>
                <button
                  onClick={() => sendAction('hunter_skip')}
                  className="px-4 py-2 border border-gray-600 rounded hover:bg-gray-700"
                >
                  Skip (don't shoot)
                </button>
              </div>
            )}

            {/* Error */}
            {error && <div className="p-3 bg-red-900/50 border border-red-600 rounded text-red-300 text-sm">{error}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function NightActionPanel({
  role,
  sendAction,
  players,
  mySeat,
}: {
  role: string | null;
  sendAction: (action: string, data?: Record<string, unknown>) => void;
  players: PlayerView[];
  mySeat: number;
}) {
  const [witchSave, setWitchSave] = useState(false);
  const [witchPoison, setWitchPoison] = useState<number | null>(null);

  const targets = players.filter((p) => p.seat !== mySeat);

  if (role === 'werewolf') {
    const nonWolves = targets.filter((p) => p.role !== 'werewolf');
    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="font-semibold mb-3 text-red-400">Werewolf — Choose your target</h3>
        <div className="grid grid-cols-2 gap-2">
          {nonWolves.map((p) => (
            <button
              key={p.seat}
              onClick={() => {
                sendAction('night_action', { wolf_target: p.seat });
              }}
              className="p-3 bg-red-900/30 rounded hover:bg-red-700 transition text-left"
            >
              #{p.seat} {p.nickname}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (role === 'seer') {
    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="font-semibold mb-3 text-blue-400">Seer — Choose someone to investigate</h3>
        <div className="grid grid-cols-2 gap-2">
          {targets.map((p) => (
            <button
              key={p.seat}
              onClick={() => {
                sendAction('night_action', { seer_target: p.seat });
              }}
              className="p-3 bg-blue-900/30 rounded hover:bg-blue-700 transition text-left"
            >
              #{p.seat} {p.nickname}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (role === 'witch') {
    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="font-semibold mb-3 text-purple-400">Witch — Use your potions</h3>
        <p className="text-sm text-gray-400 mb-3">
          You can save the victim, poison someone, or do nothing.
        </p>
        <div className="space-y-3">
          <button
            onClick={() => {
              if (witchPoison !== null) setWitchPoison(null);
              setWitchSave(true);
            }}
            className={`w-full p-2 rounded ${witchSave ? 'bg-green-700' : 'bg-green-900/30 hover:bg-green-700'} transition`}
          >
            Use Antidote (Save)
          </button>
          <p className="text-sm text-gray-400">Or poison someone:</p>
          <div className="grid grid-cols-2 gap-2">
            {targets.map((p) => (
              <button
                key={p.seat}
                onClick={() => {
                  if (witchSave) setWitchSave(false);
                  setWitchPoison(p.seat);
                }}
                className={`p-2 rounded transition text-left ${
                  witchPoison === p.seat ? 'bg-purple-700' : 'bg-purple-900/30 hover:bg-purple-700'
                }`}
              >
                #{p.seat} {p.nickname}
              </button>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => {
                const data: Record<string, unknown> = {};
                if (witchSave) data.witch_save = true;
                if (witchPoison !== null) data.witch_poison_target = witchPoison;
                sendAction('night_action', data);
              }}
              className="px-4 py-2 bg-purple-600 rounded hover:bg-purple-700"
            >
              Confirm
            </button>
            <button
              onClick={() => sendAction('night_action', {})}
              className="px-4 py-2 border border-gray-600 rounded hover:bg-gray-700"
            >
              Do Nothing
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (role === 'guard') {
    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="font-semibold mb-3 text-cyan-400">Guard — Choose someone to protect</h3>
        <div className="grid grid-cols-2 gap-2">
          {targets.map((p) => (
            <button
              key={p.seat}
              onClick={() => {
                sendAction('night_action', { guard_target: p.seat });
              }}
              className="p-3 bg-cyan-900/30 rounded hover:bg-cyan-700 transition text-left"
            >
              #{p.seat} {p.nickname}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // Villager or other — no night action
  return (
    <div className="bg-gray-800 rounded-lg p-4 text-center">
      <p className="text-gray-400">Night phase — wait for others to act...</p>
    </div>
  );
}
