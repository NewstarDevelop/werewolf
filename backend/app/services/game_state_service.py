"""Game state serialization and pending action computation.

Extracted from Game model (NEW-11) to reduce model responsibilities.
The Game dataclass retains thin wrapper methods for backward compatibility.
"""
from typing import Optional, TYPE_CHECKING

from app.schemas.enums import (
    GameStatus, GamePhase, Role, ActionType, MessageType, Winner
)
from app.i18n import t

if TYPE_CHECKING:
    from app.models.game import Game, Player

# Wolf roles set (mirrors game.py constant)
WOLF_ROLES = {Role.WEREWOLF, Role.WOLF_KING, Role.WHITE_WOLF_KING}


def get_pending_action_for_player(game: "Game", player: "Player") -> Optional[dict]:
    """
    Determine what action the player needs to take.

    Returns a dict matching PendingAction schema, or None if no action needed.
    """
    phase = game.phase
    role = player.role

    # Last words phase
    if phase == GamePhase.DAY_LAST_WORDS:
        if game.current_actor_seat == player.seat_id and not player.is_alive:
            return {
                "type": ActionType.SPEAK.value,
                "choices": [],
                "message": t("pending_action.last_words_prompt", language=game.language)
            }

    # Hunter can shoot after being eliminated (by vote/kill)
    # Wolf king can shoot when voted out during day
    if phase == GamePhase.DEATH_SHOOT:
        if game.current_actor_seat == player.seat_id:
            # Hunter must be able to shoot (not poisoned)
            if player.role == Role.HUNTER and not player.can_shoot:
                return None
            # Wolf king can always shoot when in this phase
            if player.role in [Role.HUNTER, Role.WOLF_KING]:
                alive_seats = game.get_alive_seats()
                return {
                    "type": ActionType.SHOOT.value,
                    "choices": alive_seats + [0],  # 0 = skip
                    "message": t("pending_action.shoot_prompt", language=game.language)
                }

    # Legacy hunter shoot phase (backward compatibility)
    if phase == GamePhase.HUNTER_SHOOT and role == Role.HUNTER:
        if game.current_actor_seat == player.seat_id and player.can_shoot:
            alive_seats = game.get_alive_seats()
            return {
                "type": ActionType.SHOOT.value,
                "choices": alive_seats + [0],  # 0 = skip
                "message": t("pending_action.shoot_prompt", language=game.language)
            }

    if not player.is_alive:
        return None

    alive_seats = game.get_alive_seats()
    other_alive = [s for s in alive_seats if s != player.seat_id]

    # Night werewolf chat phase - all wolf-aligned roles participate
    if phase == GamePhase.NIGHT_WEREWOLF_CHAT and role in WOLF_ROLES:
        if player.seat_id not in game.wolf_chat_completed:
            return {
                "type": ActionType.SPEAK.value,
                "choices": [],
                "message": t("pending_action.wolf_chat_prompt", language=game.language)
            }

    # Night werewolf phase - regular werewolf and wolf king vote (white wolf king handled separately below)
    if phase == GamePhase.NIGHT_WEREWOLF and role in {Role.WEREWOLF, Role.WOLF_KING}:
        if player.seat_id not in game.wolf_votes:
            # 狼人可以击杀任何存活玩家（包括自己，实现自刀策略）
            kill_targets = alive_seats[:]
            return {
                "type": ActionType.KILL.value,
                "choices": kill_targets,
                "message": t("pending_action.wolf_kill_prompt", language=game.language)
            }

    # Night werewolf phase - White wolf king can choose to self-destruct
    elif phase == GamePhase.NIGHT_WEREWOLF and role == Role.WHITE_WOLF_KING:
        if player.seat_id not in game.wolf_votes:
            # White wolf king can either vote for kill OR self-destruct
            if not game.white_wolf_king_used_explode:
                kill_targets = alive_seats[:]
                return {
                    "type": ActionType.KILL.value,  # Frontend will show both KILL and SELF_DESTRUCT options
                    "choices": kill_targets,
                    "message": t("pending_action.white_wolf_king_prompt", language=game.language)
                }
            else:
                # Already used self-destruct, can only vote for normal kill
                kill_targets = alive_seats[:]
                return {
                    "type": ActionType.KILL.value,
                    "choices": kill_targets,
                    "message": t("pending_action.wolf_kill_prompt", language=game.language)
                }

    # Night guard phase
    elif phase == GamePhase.NIGHT_GUARD and role == Role.GUARD:
        # Check if guard has already made decision this night
        if game.guard_decided:
            return None

        # Guard can protect any alive player (including self)
        # Filter out last night's target (cannot guard same person consecutively)
        protect_choices = alive_seats.copy()
        if game.guard_last_target and game.guard_last_target in protect_choices:
            protect_choices.remove(game.guard_last_target)

        return {
            "type": ActionType.PROTECT.value,
            "choices": protect_choices + [0],  # 0 = skip
            "message": t("pending_action.guard_prompt", language=game.language)
        }

    # Night seer phase
    elif phase == GamePhase.NIGHT_SEER and role == Role.SEER:
        if game.seer_verified_this_night:
            return None
        unverified = [s for s in other_alive if s not in player.verified_players]
        if not unverified:
            return None
        return {
            "type": ActionType.VERIFY.value,
            "choices": unverified,
            "message": t("pending_action.seer_prompt", language=game.language)
        }

    # Night witch phase
    elif phase == GamePhase.NIGHT_WITCH and role == Role.WITCH:
        used_save_this_night = any(
            a.day == game.day
            and a.player_id == player.seat_id
            and a.action_type == ActionType.SAVE
            for a in game.actions
        )

        # Step 1: Save potion decision
        if not game.witch_save_decided:
            if player.has_save_potion and game.night_kill_target:
                return {
                    "type": ActionType.SAVE.value,
                    "choices": [game.night_kill_target, 0],  # 0 = skip
                    "message": t("pending_action.witch_save_prompt", language=game.language, target=game.night_kill_target)
                }

            msg_key = "pending_action.witch_no_target" if game.night_kill_target is None else "pending_action.witch_no_antidote"
            return {
                "type": ActionType.SAVE.value,
                "choices": [0],
                "message": t(msg_key, language=game.language)
            }

        # Step 2: Poison potion decision
        if not game.witch_poison_decided:
            if used_save_this_night:
                return {
                    "type": ActionType.POISON.value,
                    "choices": [0],
                    "message": t("pending_action.witch_used_save", language=game.language)
                }

            if player.has_poison_potion:
                return {
                    "type": ActionType.POISON.value,
                    "choices": other_alive + [0],  # 0 = skip
                    "message": t("pending_action.witch_poison_prompt", language=game.language, target=game.night_kill_target)
                    if game.night_kill_target is not None
                    else t("pending_action.witch_poison_prompt_no_kill", language=game.language)
                }

            return {
                "type": ActionType.POISON.value,
                "choices": [0],
                "message": t("pending_action.witch_no_poison", language=game.language)
            }

    # Day speech phase
    elif phase == GamePhase.DAY_SPEECH:
        if (game.current_speech_index < len(game.speech_order) and
            game.speech_order[game.current_speech_index] == player.seat_id):
            return {
                "type": ActionType.SPEAK.value,
                "choices": [],
                "message": t("pending_action.speech_prompt", language=game.language)
            }

    # Day vote phase
    elif phase == GamePhase.DAY_VOTE:
        if player.seat_id not in game.day_votes:
            return {
                "type": ActionType.VOTE.value,
                "choices": other_alive + [0],  # 0 = abstain
                "message": t("pending_action.vote_prompt", language=game.language)
            }

    return None


def build_state_for_player(game: "Game", player_id: Optional[str] = None) -> dict:
    """
    Get game state filtered for specific player's perspective.

    Args:
        game: The Game instance.
        player_id: Player identifier. If None, returns observer view.

    Returns:
        Filtered game state dictionary safe for the requesting player.
    """
    # Find the player's seat using player_mapping
    seat = game.player_mapping.get(player_id) if player_id else None
    player = game.get_player(seat) if seat else None

    # Base state (always safe to share)
    state = {
        "game_id": game.id,
        "room_id": game.id,  # Game ID doubles as room ID for redirect on reset
        "status": game.status.value,
        "state_version": game.state_version,
        "day": game.day,
        "phase": game.phase.value,
        "current_actor": game.current_actor_seat,  # Renamed: current_actor_seat -> current_actor
        "alive_seats": game.get_alive_seats(),
        "pending_deaths": game.pending_deaths,
        "current_speech_index": game.current_speech_index,
    }

    # Add players list (frontend expects this field)
    players = []
    for p in game.players.values():
        player_public = {
            "seat_id": p.seat_id,
            "is_alive": p.is_alive,
            "is_human": p.is_human,
            "name": p.personality.name if p.personality else None,
            "role": None  # Default: hide role
        }

        # Show role when: 1) Game finished, or 2) It's the requesting player
        if game.status == GameStatus.FINISHED:
            player_public["role"] = p.role.value
        elif player and p.seat_id == seat:
            player_public["role"] = p.role.value

        players.append(player_public)

    state["players"] = players

    # Filter messages - remove vote_thought and wolf_chat from non-privileged players
    filtered_messages = []
    for msg in game.messages:
        # Always hide vote_thought
        if msg.msg_type == MessageType.VOTE_THOUGHT:
            continue
        # Hide wolf_chat unless player is a werewolf
        if msg.msg_type == MessageType.WOLF_CHAT:
            if not player or player.role not in WOLF_ROLES:
                continue
        msg_dict = {
            "seat_id": msg.seat_id,
            "text": msg.content,  # Renamed: content -> text
            "type": msg.msg_type.value,
            "day": msg.day
        }
        if msg.i18n_key:
            msg_dict["i18n_key"] = msg.i18n_key
        if msg.i18n_params:
            msg_dict["i18n_params"] = msg.i18n_params
        filtered_messages.append(msg_dict)
    state["message_log"] = filtered_messages  # Renamed: messages -> message_log

    # Add winner field (always include, null if game not finished)
    state["winner"] = game.winner.value if game.winner else None

    # Add player-specific info if authenticated
    if player:
        state["my_seat"] = seat
        state["my_role"] = player.role.value

        # Werewolf-specific info
        if player.role in WOLF_ROLES:
            state["wolf_teammates"] = player.teammates
            state["night_kill_target"] = game.night_kill_target
            # Wolf votes visible (for frontend to show teammate votes)
            state["wolf_votes_visible"] = game.wolf_votes
        else:
            state["wolf_votes_visible"] = {}

        # Witch-specific info
        if player.role == Role.WITCH:
            state["has_save_potion"] = player.has_save_potion
            state["has_poison_potion"] = player.has_poison_potion
            # Only show kill target while witch is making night decisions
            if game.phase == GamePhase.NIGHT_WITCH and not game.witch_poison_decided:
                state["night_kill_target"] = game.night_kill_target

        # Guard-specific info
        if player.role == Role.GUARD:
            state["guard_last_target"] = game.guard_last_target

        # Seer-specific info
        if player.role == Role.SEER:
            state["verified_results"] = player.verified_players

        # Calculate pending_action for human player
        state["pending_action"] = get_pending_action_for_player(game, player)
    else:
        # Observer view - minimal info
        state["my_seat"] = None
        state["my_role"] = None
        state["wolf_votes_visible"] = {}
        state["pending_action"] = None

    # WL-BUG-001 Fix: Ensure all required fields have default values
    # This prevents "Cannot convert undefined or null to object" errors
    # when frontend receives incomplete state (e.g., token mismatch)
    if "wolf_teammates" not in state:
        state["wolf_teammates"] = []
    if "verified_results" not in state:
        state["verified_results"] = {}

    return state
