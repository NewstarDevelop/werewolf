"""WebSocket endpoint for real-time game state."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.models.game import Game, Phase, Role, Player, GameEvent
from app.services.ai_service import ai_service
from app.services.game_store import GameStore

router = APIRouter(tags=["websocket"])

store = GameStore.get_instance()


class ConnectionManager:
    """Manage WebSocket connections per game."""

    def __init__(self) -> None:
        self._connections: dict[int, dict[int, WebSocket]] = {}

    def connect(self, game_id: int, user_id: int, ws: WebSocket) -> None:
        if game_id not in self._connections:
            self._connections[game_id] = {}
        self._connections[game_id][user_id] = ws

    def disconnect(self, game_id: int, user_id: int) -> None:
        if game_id in self._connections:
            self._connections[game_id].pop(user_id, None)
            if not self._connections[game_id]:
                del self._connections[game_id]

    async def send_to_user(self, game_id: int, user_id: int, data: dict) -> None:
        conns = self._connections.get(game_id, {})
        ws = conns.get(user_id)
        if ws:
            await ws.send_json(data)

    async def broadcast_to_game(self, game_id: int, data: dict, exclude_user: int | None = None) -> None:
        conns = self._connections.get(game_id, {})
        for uid, ws in conns.items():
            if exclude_user is not None and uid == exclude_user:
                continue
            await ws.send_json(data)

    def get_game_users(self, game_id: int) -> set[int]:
        return set(self._connections.get(game_id, {}).keys())


manager = ConnectionManager()


def _authenticate_ws(token: str | None) -> int | None:
    if not token:
        return None
    user_id = decode_access_token(token)
    if user_id:
        return int(user_id)
    return None


@router.websocket("/ws/game/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: int, token: str | None = Query(None)):
    await websocket.accept()
    ws_token = token or websocket.cookies.get("access_token")
    user_id = _authenticate_ws(ws_token)

    if not user_id:
        await websocket.send_json({"type": "error", "detail": "Not authenticated"})
        await websocket.close(code=4001)
        return

    game = store.get(game_id)
    if not game:
        await websocket.send_json({"type": "error", "detail": "Game not found"})
        await websocket.close(code=4004)
        return

    player = game.get_player_by_user(user_id)
    if not player:
        await websocket.send_json({"type": "error", "detail": "Not a player in this game"})
        await websocket.close(code=4003)
        return

    manager.connect(game_id, user_id, websocket)

    # Send initial state
    perspective = game.get_player_perspective(player.seat)
    await websocket.send_json({"type": "state", **perspective})

    # Auto-trigger AI actions on connection
    await _process_ai_actions(game)

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_game_message(game, player, data, user_id)
    except WebSocketDisconnect:
        manager.disconnect(game_id, user_id)
    except Exception:
        manager.disconnect(game_id, user_id)


# ---------------------------------------------------------------------------
# AI action processing
# ---------------------------------------------------------------------------

async def _process_ai_actions(game: Game) -> None:
    """Auto-execute actions for all AI players in current phase."""
    if game.phase == Phase.NIGHT:
        await _process_ai_night(game)
    elif game.phase == Phase.DAY_SPEECH:
        await _process_ai_speech(game)
    elif game.phase == Phase.DAY_VOTE:
        await _process_ai_votes(game)
    elif game.phase == Phase.HUNTER_SHOT:
        await _process_ai_hunter(game)


async def _process_ai_night(game: Game) -> None:
    """Auto-submit night actions for all AI players with pending roles."""
    for role in list(game.pending_night_actors):
        # Find an live AI player with this role
        ai_player = None
        for p in game.alive_players():
            if p.is_ai and p.alive and p.role == role:
                ai_player = p
                break
        if ai_player is None:
            continue

        action = ai_service.generate_night_action(game, ai_player)
        if not action:
            continue

        try:
            game.submit_night_action(role, action)
        except ValueError:
            continue
        await asyncio.sleep(0.3)

    if game.night_complete():
        events = game.resolve_night()
        await _handle_night_deaths(game, events)
        await _broadcast_state(game)
        # Auto-advance dawn -> speech after delay
        await asyncio.sleep(2)
        if game.phase == Phase.DAWN:
            game.start_speech()
            await _broadcast_state(game)
            await _process_ai_speech(game)


async def _handle_night_deaths(game: Game, events: list[GameEvent]) -> None:
    """Handle deaths from night resolution, check for hunter pending."""
    dead_seats = [e.data["seat"] for e in events if e.event_type == "death"]
    hunter_pending_seats = set()
    for seat in dead_seats:
        dp = game.get_player_by_seat(seat)
        if dp and dp.role == Role.HUNTER:
            # Killed by poison = cannot shoot
            if game.night_actions.witch_poison_target == seat:
                continue
            game.hunter_pending = True
            hunter_pending_seats.add(seat)

    # Notify human hunters
    for seat in hunter_pending_seats:
        hp = game.get_player_by_seat(seat)
        if hp and not hp.is_ai and hp.user_id:
            await manager.send_to_user(
                game.id, hp.user_id,
                {"type": "hunter_pending", "seat": seat},
            )


async def _process_ai_speech(game: Game) -> None:
    """AI players give speeches."""
    for p in game.alive_players():
        if p.is_ai:
            speech = ai_service.generate_speech(game, p)
            game.add_speech(p.seat, speech)
            await manager.broadcast_to_game(game.id, {
                "type": "speech",
                "seat": p.seat,
                "nickname": p.nickname,
                "content": speech,
            })
            await asyncio.sleep(0.3)

    # After AI speeches, auto-start vote after a delay
    await asyncio.sleep(3)
    if game.phase == Phase.DAY_SPEECH:
        game.start_vote()
        await _broadcast_state(game)
        await _process_ai_votes(game)


async def _process_ai_votes(game: Game) -> None:
    """AI players submit votes."""
    for p in game.alive_players():
        if p.is_ai:
            target = ai_service.generate_vote(game, p)
            if target is not None:
                try:
                    game.submit_vote(p.seat, target)
                    await manager.broadcast_to_game(game.id, {
                        "type": "vote_cast",
                        "voter": p.seat,
                    })
                except ValueError:
                    continue

    if game.all_voted():
        events = game.resolve_vote()
        vote_data = {}
        for e in events:
            if e.event_type == "vote_result":
                vote_data = e.data
        await manager.broadcast_to_game(game.id, {"type": "vote_result", **vote_data})
        await _broadcast_state(game)

        # Check for hunter pending after vote
        if game.phase == Phase.HUNTER_SHOT:
            await _process_ai_hunter(game)
        elif game.phase == Phase.NIGHT:
            await asyncio.sleep(2)
            await _process_ai_night(game)


async def _process_ai_hunter(game: Game) -> None:
    """Handle AI hunter shot."""
    for p in game.players:
        if p.role == Role.HUNTER and not p.alive and game.hunter_pending:
            if p.is_ai:
                target = ai_service.generate_hunter_shot(game, p)
                if target is not None:
                    event = game.hunter_shoot(p.seat, target)
                    await manager.broadcast_to_game(game.id, {
                        "type": "hunter_shot",
                        "hunter": p.seat,
                        "target": target,
                    })
                else:
                    game.skip_hunter_shot(p.seat)
                await _broadcast_state(game)

                if game.phase == Phase.NIGHT:
                    await asyncio.sleep(2)
                    await _process_ai_night(game)
            # Human hunter waits for their action


# ---------------------------------------------------------------------------
# Human player message handler
# ---------------------------------------------------------------------------

async def _handle_game_message(game: Game, player: Player, data: dict, user_id: int) -> None:
    action_type = data.get("action")
    game_id = game.id

    try:
        if game.phase == Phase.NIGHT:
            role = player.role
            game.submit_night_action(role, data)
            await manager.send_to_user(game_id, user_id, {"type": "action_ack", "action": action_type})
            # Trigger AI night actions
            await _process_ai_night(game)

        elif game.phase == Phase.DAWN:
            if action_type == "start_speech":
                game.start_speech()
                await _broadcast_state(game)
                await _process_ai_speech(game)

        elif game.phase == Phase.DAY_SPEECH:
            if action_type == "speech":
                content = data.get("content", "")
                game.add_speech(player.seat, content)
                await manager.broadcast_to_game(game_id, {
                    "type": "speech",
                    "seat": player.seat,
                    "nickname": player.nickname,
                    "content": content,
                })
            elif action_type == "start_vote":
                game.start_vote()
                await _broadcast_state(game)
                await _process_ai_votes(game)

        elif game.phase == Phase.DAY_VOTE:
            if action_type == "vote":
                target = data.get("target_seat")
                game.submit_vote(player.seat, target)
                await manager.broadcast_to_game(game_id, {
                    "type": "vote_cast",
                    "voter": player.seat,
                }, exclude_user=user_id)
                await _process_ai_votes(game)

        elif game.phase == Phase.HUNTER_SHOT:
            if action_type == "hunter_shoot":
                target = data.get("target_seat")
                game.hunter_shoot(player.seat, target)
                await manager.broadcast_to_game(game_id, {
                    "type": "hunter_shot",
                    "hunter": player.seat,
                    "target": target,
                })
                await _broadcast_state(game)
                if game.phase == Phase.NIGHT:
                    await asyncio.sleep(2)
                    await _process_ai_night(game)
            elif action_type == "hunter_skip":
                game.skip_hunter_shot(player.seat)
                await _broadcast_state(game)
                if game.phase == Phase.NIGHT:
                    await asyncio.sleep(2)
                    await _process_ai_night(game)

        elif game.phase == Phase.GAME_OVER:
            await _broadcast_state(game)

    except ValueError as e:
        await manager.send_to_user(game_id, user_id, {"type": "error", "detail": str(e)})


async def _broadcast_state(game: Game) -> None:
    """Send personalized state to all connected players."""
    game_id = game.id
    for user_id in list(manager.get_game_users(game_id)):
        player = game.get_player_by_user(user_id)
        if not player:
            continue
        perspective = game.get_player_perspective(player.seat)
        await manager.send_to_user(game_id, user_id, {"type": "state", **perspective})
