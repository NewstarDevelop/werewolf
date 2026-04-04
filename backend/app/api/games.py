from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.game import Game, Phase, Role
from app.models.user import User
from app.services.game_lifecycle import GameLifecycleService
from app.services.game_store import GameStore

router = APIRouter(prefix="/games", tags=["games"])

store = GameStore.get_instance()


async def _get_game_or_404(game_id: int) -> Game:
    game = store.get(game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return game


@router.get("/{game_id}/state")
async def get_game_state(
    game_id: int,
    user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(game_id)
    player = game.get_player_by_user(user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a player in this game")
    return game.get_player_perspective(player.seat)


@router.post("/{game_id}/action")
async def submit_action(
    game_id: int,
    body: dict,
    user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(game_id)
    player = game.get_player_by_user(user.id)
    if not player or not player.alive:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an active player")

    action_type = body.get("action")
    if not action_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing action type")

    try:
        if game.phase == Phase.NIGHT:
            role = player.role
            if role not in [Role.GUARD, Role.WEREWOLF, Role.SEER, Role.WITCH]:
                raise ValueError("Your role has no night action")
            game.submit_night_action(role, body)
            result = {"status": "ok", "pending": list(game.pending_night_actors)}

            # Auto-resolve when all actions in
            if game.night_complete():
                events = game.resolve_night()
                # Check if hunter needs to shoot
                dead_seats = [e.data["seat"] for e in events if e.event_type == "death"]
                from app.models.game import Role as R
                for seat in dead_seats:
                    dp = game.get_player_by_seat(seat)
                    if dp and dp.role == R.HUNTER:
                        # Check if killed by witch poison (cannot shoot)
                        # For simplicity: wolf kill = can shoot, poison = cannot
                        if game.night_actions.witch_poison_target == seat:
                            continue
                        game.hunter_pending = True
                result["resolved"] = True
                result["events"] = [
                    {"type": e.event_type, "data": e.data}
                    for e in events
                ]
            return result

        elif game.phase == Phase.DAY_SPEECH:
            if action_type == "speech":
                content = body.get("content", "")
                event = game.add_speech(player.seat, content)
                return {"status": "ok", "event": {"type": event.event_type, "data": event.data}}
            elif action_type == "start_vote":
                game.start_vote()
                return {"status": "ok", "phase": "day_vote"}
            else:
                raise ValueError("Invalid action for speech phase")

        elif game.phase == Phase.DAY_VOTE:
            if action_type != "vote":
                raise ValueError("Only vote action allowed in vote phase")
            target = body.get("target_seat")
            if target is None:
                raise ValueError("Missing target_seat")
            game.submit_vote(player.seat, target)
            result = {"status": "ok"}
            if game.all_voted():
                events = game.resolve_vote()
                result["resolved"] = True
                result["events"] = [
                    {"type": e.event_type, "data": e.data}
                    for e in events
                ]
            return result

        elif game.phase == Phase.HUNTER_SHOT:
            if action_type == "hunter_shoot":
                target = body.get("target_seat")
                if target is None:
                    raise ValueError("Missing target_seat")
                event = game.hunter_shoot(player.seat, target)
                return {"status": "ok", "event": {"type": event.event_type, "data": event.data}}
            elif action_type == "hunter_skip":
                event = game.skip_hunter_shot(player.seat)
                return {"status": "ok", "event": {"type": event.event_type, "data": event.data}}
            else:
                raise ValueError("Invalid hunter action")

        else:
            raise ValueError(f"Game phase {game.phase.value} does not accept actions")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
