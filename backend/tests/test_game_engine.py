"""Tests for the game engine core — roles, phases, actions, win conditions."""

import pytest

from app.models.game import (
    Faction,
    Game,
    GameEvent,
    NightActions,
    Phase,
    Player,
    Role,
)


def _make_9player_game() -> Game:
    """Create a standard 9-player game with players but no role assignment."""
    players = []
    for i in range(9):
        players.append(Player(
            seat=i,
            user_id=100 + i,
            nickname=f"P{i}",
            is_ai=(i >= 1),  # only seat 0 is human
        ))
    game = Game(id=1, room_id=1, mode="classic_9", players=players)
    game._rebuild_seat_map()
    return game


def _start_game() -> Game:
    game = _make_9player_game()
    game.start()
    return game


def _find_player_by_role(game: Game, role: Role) -> Player:
    p = game.get_player_by_role(role)
    assert p is not None, f"No player with role {role}"
    return p


# -----------------------------------------------------------------------
# Role assignment
# -----------------------------------------------------------------------


class TestRoleAssignment:
    def test_correct_role_count(self):
        game = _start_game()
        roles = [p.role for p in game.players]
        assert roles.count(Role.WEREWOLF) == 3
        assert roles.count(Role.VILLAGER) == 3
        assert roles.count(Role.SEER) == 1
        assert roles.count(Role.WITCH) == 1
        assert roles.count(Role.HUNTER) == 1

    def test_all_players_have_roles(self):
        game = _start_game()
        for p in game.players:
            assert p.role is not None

    def test_faction_assignment(self):
        game = _start_game()
        for p in game.players:
            if p.role == Role.WEREWOLF:
                assert p.faction == Faction.WOLF
            else:
                assert p.faction == Faction.VILLAGE

    def test_witch_starts_with_both_potions(self):
        game = _start_game()
        witch = _find_player_by_role(game, Role.WITCH)
        assert witch.has_antidote is True
        assert witch.has_poison is True


# -----------------------------------------------------------------------
# Night actions
# -----------------------------------------------------------------------


class TestNightActions:
    def test_wolf_kill(self):
        game = _start_game()
        wolf = _find_player_by_role(game, Role.WEREWOLF)
        # Pick a non-wolf target
        target = next(p for p in game.alive_players() if not p.is_wolf)
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": target.seat})
        game.submit_night_action(Role.SEER, {"seer_target": wolf.seat})
        # Witch does nothing
        game.submit_night_action(Role.WITCH, {})

        assert game.night_complete()
        events = game.resolve_night()
        death_events = [e for e in events if e.event_type == "death"]
        assert len(death_events) == 1
        assert death_events[0].data["seat"] == target.seat
        assert not game.seat_map[target.seat].alive

    def test_guard_protects_in_12player(self):
        """Guard protection is only available in 12-player mode."""
        players = []
        for i in range(12):
            players.append(Player(seat=i, user_id=100 + i, nickname=f"P{i}"))
        game = Game(id=2, room_id=2, mode="classic_12", players=players)
        game._rebuild_seat_map()
        game.start()

        guard = _find_player_by_role(game, Role.GUARD)
        target = next(p for p in game.alive_players() if not p.is_wolf and p.role != Role.GUARD)

        game.submit_night_action(Role.GUARD, {"guard_target": target.seat})
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": target.seat})
        game.submit_night_action(Role.SEER, {"seer_target": guard.seat})
        game.submit_night_action(Role.WITCH, {})
        events = game.resolve_night()

        # Target should be saved by guard
        death_events = [e for e in events if e.event_type == "death"]
        assert len(death_events) == 0
        assert game.seat_map[target.seat].alive

    def test_witch_save(self):
        game = _start_game()
        target = next(p for p in game.alive_players() if not p.is_wolf)
        witch = _find_player_by_role(game, Role.WITCH)
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": target.seat})
        game.submit_night_action(Role.SEER, {"seer_target": target.seat})
        game.submit_night_action(Role.WITCH, {"witch_save": True})

        events = game.resolve_night()
        death_events = [e for e in events if e.event_type == "death"]
        # Target should be saved
        assert len(death_events) == 0
        assert game.seat_map[target.seat].alive
        assert witch.has_antidote is False

    def test_witch_poison(self):
        game = _start_game()
        wolves = [p for p in game.players if p.is_wolf]
        non_wolves = [p for p in game.alive_players() if not p.is_wolf]
        wolf_target = non_wolves[0]
        poison_target = non_wolves[1]
        witch = _find_player_by_role(game, Role.WITCH)

        game.submit_night_action(Role.WEREWOLF, {"wolf_target": wolf_target.seat})
        game.submit_night_action(Role.SEER, {"seer_target": wolves[0].seat})
        game.submit_night_action(Role.WITCH, {"witch_poison_target": poison_target.seat})

        events = game.resolve_night()
        death_events = [e for e in events if e.event_type == "death"]
        assert len(death_events) == 2
        assert witch.has_poison is False

    def test_witch_cannot_use_both_same_night(self):
        game = _start_game()
        non_wolves = [p for p in game.alive_players() if not p.is_wolf]
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": non_wolves[0].seat})
        game.submit_night_action(Role.SEER, {"seer_target": non_wolves[1].seat})

        with pytest.raises(ValueError, match="Cannot use both"):
            game.submit_night_action(Role.WITCH, {
                "witch_save": True,
                "witch_poison_target": non_wolves[2].seat,
            })

    def test_seer_check(self):
        game = _start_game()
        seer = _find_player_by_role(game, Role.SEER)
        wolf = _find_player_by_role(game, Role.WEREWOLF)
        villager = next(p for p in game.players if p.role == Role.VILLAGER)

        # Check a wolf
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": villager.seat})
        game.submit_night_action(Role.SEER, {"seer_target": wolf.seat})
        game.submit_night_action(Role.WITCH, {})

        events = game.resolve_night()
        seer_events = [e for e in events if e.event_type == "seer_result"]
        assert len(seer_events) == 1
        assert seer_events[0].data["result"] == "wolf"

    def test_wolves_cannot_target_wolf(self):
        game = _start_game()
        wolf = _find_player_by_role(game, Role.WEREWOLF)
        with pytest.raises(ValueError, match="cannot target another wolf"):
            game.submit_night_action(Role.WEREWOLF, {"wolf_target": wolf.seat})

    def test_guard_cannot_repeat(self):
        """Guard cannot guard same person two nights in a row (12-player)."""
        players = []
        for i in range(12):
            players.append(Player(seat=i, user_id=100 + i, nickname=f"P{i}"))
        game = Game(id=2, room_id=2, mode="classic_12", players=players)
        game._rebuild_seat_map()
        game.start()

        guard = _find_player_by_role(game, Role.GUARD)
        target = next(p for p in game.alive_players() if p.role not in (Role.GUARD, Role.WEREWOLF))

        # Night 1
        game.submit_night_action(Role.GUARD, {"guard_target": target.seat})
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": target.seat})
        game.submit_night_action(Role.SEER, {"seer_target": guard.seat})
        game.submit_night_action(Role.WITCH, {})
        game.resolve_night()

        # Dawn -> speech -> vote -> resolve -> night 2
        game.start_speech()
        game.start_vote()
        for p in game.alive_players():
            game.submit_vote(p.seat, game.alive_players()[0].seat)
        game.resolve_vote()

        # Night 2: guard tries same target
        assert guard.last_guarded_seat == target.seat
        with pytest.raises(ValueError, match="Cannot guard the same person"):
            game.submit_night_action(Role.GUARD, {"guard_target": target.seat})


# -----------------------------------------------------------------------
# Day vote
# -----------------------------------------------------------------------


class TestDayVote:
    def test_vote_elimination(self):
        game = _start_game()
        # Simulate through night
        target = next(p for p in game.alive_players() if not p.is_wolf)
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": target.seat})
        game.submit_night_action(Role.SEER, {"seer_target": target.seat})
        game.submit_night_action(Role.WITCH, {})
        game.resolve_night()

        # Dawn -> speech -> vote
        game.start_speech()
        game.start_vote()

        alive = game.alive_players()
        vote_target = alive[0]
        for p in alive:
            game.submit_vote(p.seat, vote_target.seat)

        assert game.all_voted()
        events = game.resolve_vote()
        assert any(e.event_type == "death" for e in events)
        assert not game.seat_map[vote_target.seat].alive

    def test_vote_tie_no_elimination(self):
        game = _start_game()
        target = next(p for p in game.alive_players() if not p.is_wolf)
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": target.seat})
        game.submit_night_action(Role.SEER, {"seer_target": target.seat})
        game.submit_night_action(Role.WITCH, {})
        game.resolve_night()

        game.start_speech()
        game.start_vote()

        alive = game.alive_players()
        if len(alive) >= 4:
            half = len(alive) // 2
            t1, t2 = alive[0], alive[1]
            for i, p in enumerate(alive):
                game.submit_vote(p.seat, t1.seat if i < half else t2.seat)

            events = game.resolve_vote()
            vote_result = [e for e in events if e.event_type == "vote_result"]
            assert len(vote_result) == 1
            assert vote_result[0].data.get("tied") is True

    def test_double_vote_rejected(self):
        game = _start_game()
        target = next(p for p in game.alive_players() if not p.is_wolf)
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": target.seat})
        game.submit_night_action(Role.SEER, {"seer_target": target.seat})
        game.submit_night_action(Role.WITCH, {})
        game.resolve_night()
        game.start_speech()
        game.start_vote()

        alive = game.alive_players()
        game.submit_vote(alive[0].seat, alive[1].seat)
        with pytest.raises(ValueError, match="Already voted"):
            game.submit_vote(alive[0].seat, alive[2].seat)


# -----------------------------------------------------------------------
# Hunter
# -----------------------------------------------------------------------


class TestHunter:
    def test_hunter_shoot_on_vote_death(self):
        game = _start_game()
        hunter = _find_player_by_role(game, Role.HUNTER)

        # Night: no deaths (witch saves)
        villager = next(p for p in game.players if p.role == Role.VILLAGER)
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": villager.seat})
        game.submit_night_action(Role.SEER, {"seer_target": villager.seat})
        game.submit_night_action(Role.WITCH, {"witch_save": True})
        game.resolve_night()

        # Vote out hunter
        game.start_speech()
        game.start_vote()
        for p in game.alive_players():
            game.submit_vote(p.seat, hunter.seat)
        events = game.resolve_vote()

        assert game.hunter_pending is True
        assert game.phase == Phase.HUNTER_SHOT

        # Hunter shoots someone
        shoot_target = next(p for p in game.alive_players() if p.seat != hunter.seat)
        event = game.hunter_shoot(hunter.seat, shoot_target.seat)
        assert event.event_type == "hunter_shot"
        assert not game.seat_map[shoot_target.seat].alive
        assert game.hunter_pending is False

    def test_hunter_skip(self):
        game = _start_game()
        hunter = _find_player_by_role(game, Role.HUNTER)
        villager = next(p for p in game.players if p.role == Role.VILLAGER)

        game.submit_night_action(Role.WEREWOLF, {"wolf_target": villager.seat})
        game.submit_night_action(Role.SEER, {"seer_target": villager.seat})
        game.submit_night_action(Role.WITCH, {})
        game.resolve_night()

        game.start_speech()
        game.start_vote()
        for p in game.alive_players():
            game.submit_vote(p.seat, hunter.seat)
        game.resolve_vote()

        event = game.skip_hunter_shot(hunter.seat)
        assert event.event_type == "hunter_skip"
        assert game.hunter_pending is False


# -----------------------------------------------------------------------
# Win conditions
# -----------------------------------------------------------------------


class TestWinConditions:
    def test_village_wins_when_all_wolves_dead(self):
        game = _start_game()
        wolves = [p for p in game.players if p.is_wolf]
        for w in wolves:
            w.alive = False
        assert game.check_win() == Faction.VILLAGE

    def test_wolf_wins_when_equal_or_more(self):
        game = _start_game()
        # Kill enough villagers to make wolves >= villagers
        non_wolves = [p for p in game.players if not p.is_wolf]
        # Kill 4 of 6 non-wolves -> 2 non-wolves vs 3 wolves
        for p in non_wolves[:4]:
            p.alive = False
        assert game.check_win() == Faction.WOLF

    def test_no_winner_mid_game(self):
        game = _start_game()
        assert game.check_win() is None

    def test_game_over_sets_winner(self):
        game = _start_game()
        wolves = [p for p in game.players if p.is_wolf]
        for w in wolves:
            w.alive = False
        game._advance_to_next_night_or_end()
        assert game.phase == Phase.GAME_OVER
        assert game.winner == Faction.VILLAGE
        assert game.finished_at is not None


# -----------------------------------------------------------------------
# Perspective / visibility
# -----------------------------------------------------------------------


class TestPerspective:
    def test_wolf_sees_wolves(self):
        game = _start_game()
        wolf = _find_player_by_role(game, Role.WEREWOLF)
        perspective = game.get_player_perspective(wolf.seat)
        wolf_in_view = [p for p in perspective["players"] if p.get("role") == "werewolf"]
        assert len(wolf_in_view) >= 2  # at least sees self + another wolf

    def test_villager_sees_no_roles(self):
        game = _start_game()
        villager = next(p for p in game.players if p.role == Role.VILLAGER)
        perspective = game.get_player_perspective(villager.seat)
        others_with_role = [
            p for p in perspective["players"]
            if p["seat"] != villager.seat and p.get("role") is not None
        ]
        assert len(others_with_role) == 0

    def test_seer_sees_own_role(self):
        game = _start_game()
        seer = _find_player_by_role(game, Role.SEER)
        perspective = game.get_player_perspective(seer.seat)
        assert perspective["my_role"] == "seer"

    def test_seer_result_private(self):
        game = _start_game()
        seer = _find_player_by_role(game, Role.SEER)
        villager = next(p for p in game.players if p.role == Role.VILLAGER)
        wolf = _find_player_by_role(game, Role.WEREWOLF)

        game.submit_night_action(Role.WEREWOLF, {"wolf_target": villager.seat})
        game.submit_night_action(Role.SEER, {"seer_target": wolf.seat})
        game.submit_night_action(Role.WITCH, {})
        game.resolve_night()

        # Seer sees result
        seer_view = game.get_player_perspective(seer.seat)
        seer_events = [e for e in seer_view["events"] if e["type"] == "seer_result"]
        assert len(seer_events) == 1

        # Villager does not see seer result
        other = next(p for p in game.players if p.role == Role.VILLAGER and p.alive)
        other_view = game.get_player_perspective(other.seat)
        other_seer = [e for e in other_view["events"] if e["type"] == "seer_result"]
        assert len(other_seer) == 0


# -----------------------------------------------------------------------
# Serialization
# -----------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_and_back(self):
        game = _start_game()
        d = game.to_dict()
        assert d["id"] == 1
        assert d["mode"] == "classic_9"
        assert d["phase"] == "night"
        assert len(d["players"]) == 9
        assert d["night_actions"]["wolf_target"] is None
        assert len(d["events"]) > 0  # phase_change event


# -----------------------------------------------------------------------
# GameStore
# -----------------------------------------------------------------------


class TestGameStore:
    def test_add_and_get(self):
        from app.services.game_store import GameStore
        store = GameStore()
        game = _make_9player_game()
        game.start()
        store.add(game)
        assert store.get(game.id) is game
        assert store.get(999) is None

    def test_remove(self):
        from app.services.game_store import GameStore
        store = GameStore()
        game = _make_9player_game()
        game.start()
        store.add(game)
        removed = store.remove(game.id)
        assert removed is game
        assert store.get(game.id) is None

    def test_list_active(self):
        from app.services.game_store import GameStore
        from app.models.game import Phase
        store = GameStore()
        g1 = _make_9player_game()
        g1.id = 10
        g1.start()
        store.add(g1)

        g2 = _make_9player_game()
        g2.id = 11
        g2.start()
        g2.phase = Phase.GAME_OVER
        g2.winner = Faction.WOLF
        store.add(g2)

        active = store.list_active()
        assert len(active) == 1
        assert active[0].id == 10


# -----------------------------------------------------------------------
# Full game flow integration
# -----------------------------------------------------------------------


class TestFullGameFlow:
    """Simulate a complete 9-player game: night -> day -> ... -> game over."""

    def test_complete_game_village_win(self):
        game = _start_game()
        assert game.phase == Phase.NIGHT

        wolves = [p for p in game.players if p.is_wolf]

        # Night 1: wolves kill, seer checks, witch does nothing
        non_wolf_alive = [p for p in game.alive_players() if not p.is_wolf]
        game.submit_night_action(Role.WEREWOLF, {"wolf_target": non_wolf_alive[0].seat})
        game.submit_night_action(Role.SEER, {"seer_target": wolves[0].seat})
        game.submit_night_action(Role.WITCH, {})
        game.resolve_night()

        assert game.phase == Phase.DAWN

        # Day 1: vote out a wolf
        game.start_speech()
        game.start_vote()
        alive = game.alive_players()
        wolf_alive = [p for p in alive if p.is_wolf][0]
        for p in alive:
            game.submit_vote(p.seat, wolf_alive.seat)
        game.resolve_vote()

        # Continue until game ends
        for _ in range(10):  # safety limit
            if game.phase == Phase.GAME_OVER:
                break
            if game.phase == Phase.NIGHT:
                non_wolf_alive = [p for p in game.alive_players() if not p.is_wolf]
                wolf_alive_list = [p for p in game.alive_players() if p.is_wolf]
                if not non_wolf_alive or not wolf_alive_list:
                    break
                game.submit_night_action(Role.WEREWOLF, {"wolf_target": non_wolf_alive[0].seat})
                seer = game.get_player_by_role(Role.SEER)
                if seer and seer.alive:
                    game.submit_night_action(Role.SEER, {"seer_target": wolf_alive_list[0].seat})
                witch = game.get_player_by_role(Role.WITCH)
                if witch and witch.alive:
                    game.submit_night_action(Role.WITCH, {})
                game.resolve_night()

            if game.phase == Phase.DAWN:
                game.start_speech()
                game.start_vote()
                alive = game.alive_players()
                wolves_alive = [p for p in alive if p.is_wolf]
                if wolves_alive:
                    for p in alive:
                        game.submit_vote(p.seat, wolves_alive[0].seat)
                    game.resolve_vote()
                else:
                    break

            if game.phase == Phase.HUNTER_SHOT:
                hunter = game.get_player_by_role(Role.HUNTER)
                if hunter:
                    target = next((p for p in game.alive_players() if p.seat != hunter.seat), None)
                    if target:
                        game.hunter_shoot(hunter.seat, target.seat)
                    else:
                        game.skip_hunter_shot(hunter.seat)

        assert game.phase == Phase.GAME_OVER
        assert game.winner is not None
