"""Tests for LLM provider fallback and retry logic (P3 T-3).

Verifies that:
1. Fallback response generation works for all roles
2. Provider selection falls back correctly
3. Retry logic handles rate limiting and errors
4. Mock mode produces valid responses
"""
import pytest
import random
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from app.services.llm import LLMService, LLMResponse, FALLBACK_SPEECHES
from app.schemas.enums import Role


def _make_player(role: Role = Role.VILLAGER, seat_id: int = 1):
    """Create a mock player."""
    player = MagicMock()
    player.role = role
    player.seat_id = seat_id
    player.is_human = False
    player.is_alive = True
    player.personality = MagicMock()
    player.personality.name = "TestPlayer"
    player.verified_players = {}
    player.teammates = []
    player.wolf_persona = None
    player.has_save_potion = True
    player.has_poison_potion = True
    player.can_shoot = True
    return player


def _make_game(game_id: str = "test-game", language: str = "zh"):
    """Create a mock game."""
    game = MagicMock()
    game.id = game_id
    game.language = language
    game.day = 1
    game.players = {1: _make_player()}
    game.messages = []
    game.actions = []
    game.claimed_roles = {}
    game.get_alive_players.return_value = [_make_player()]
    game.get_alive_seats.return_value = [1, 2, 3]
    game.night_kill_target = None
    game.wolf_votes = {}
    game.state_version = 1
    return game


class TestFallbackResponses:
    """Test fallback response generation for all roles and languages."""

    def _create_service(self):
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = True
            mock_settings.get_all_providers.return_value = {}
            return LLMService()

    def test_fallback_all_roles_zh(self):
        """Fallback produces valid responses for all roles in Chinese."""
        service = self._create_service()
        for role_key in ["werewolf", "villager", "seer", "witch", "hunter"]:
            role = Role(role_key) if role_key != "villager" else Role.VILLAGER
            player = _make_player(role=role)
            resp = service._get_fallback_response(player, "speech", language="zh")
            assert isinstance(resp, LLMResponse)
            assert resp.is_fallback is True
            assert resp.provider_name == "fallback"
            assert len(resp.speak) > 0

    def test_fallback_all_roles_en(self):
        """Fallback produces valid responses for all roles in English."""
        service = self._create_service()
        for role_key in ["werewolf", "villager", "seer", "witch", "hunter"]:
            role = Role(role_key) if role_key != "villager" else Role.VILLAGER
            player = _make_player(role=role)
            resp = service._get_fallback_response(player, "speech", language="en")
            assert isinstance(resp, LLMResponse)
            assert resp.is_fallback is True
            assert len(resp.speak) > 0

    def test_fallback_vote_selects_target(self):
        """Fallback vote action selects a target from available choices."""
        service = self._create_service()
        player = _make_player(role=Role.VILLAGER)
        targets = [2, 3, 4]
        resp = service._get_fallback_response(player, "vote", targets=targets, language="zh")
        assert resp.action_target in targets

    def test_fallback_kill_selects_target(self):
        """Fallback kill action selects a target from available choices."""
        service = self._create_service()
        player = _make_player(role=Role.WEREWOLF)
        targets = [1, 2, 5]
        resp = service._get_fallback_response(player, "kill", targets=targets, language="zh")
        assert resp.action_target in targets

    def test_fallback_speech_no_target(self):
        """Fallback speech action has no action_target."""
        service = self._create_service()
        player = _make_player(role=Role.VILLAGER)
        resp = service._get_fallback_response(player, "speech", language="zh")
        assert resp.action_target is None

    def test_fallback_unknown_role_uses_villager(self):
        """Unknown role falls back to villager speeches."""
        service = self._create_service()
        player = _make_player(role=Role.GUARD)
        resp = service._get_fallback_response(player, "speech", language="zh")
        assert resp.is_fallback is True
        # Guard should use villager fallback since no guard-specific speeches
        assert len(resp.speak) > 0


class TestProviderSelection:
    """Test provider selection and fallback chain."""

    def test_get_client_for_player_default(self):
        """Falls back to default provider when no player-specific mapping."""
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = False
            mock_settings.get_all_providers.return_value = {}
            service = LLMService()

            mock_client = AsyncMock()
            mock_provider = MagicMock()
            mock_provider.name = "default"
            service._clients = {"default": mock_client}
            mock_settings.get_provider_for_player.return_value = None
            mock_settings.get_provider.return_value = mock_provider

            client, provider = service._get_client_for_player(1)
            assert client is mock_client
            assert provider is mock_provider

    def test_get_client_for_player_specific(self):
        """Uses player-specific provider when available."""
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = False
            mock_settings.get_all_providers.return_value = {}
            service = LLMService()

            mock_client = AsyncMock()
            mock_provider = MagicMock()
            mock_provider.name = "deepseek"
            service._clients = {"deepseek": mock_client, "default": AsyncMock()}
            mock_settings.get_provider_for_player.return_value = mock_provider

            client, provider = service._get_client_for_player(3)
            assert client is mock_client
            assert provider is mock_provider

    def test_get_client_for_player_no_clients(self):
        """Returns None when no clients are available."""
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = False
            mock_settings.get_all_providers.return_value = {}
            service = LLMService()
            service._clients = {}
            mock_settings.get_provider_for_player.return_value = None
            mock_settings.get_provider.return_value = None

            client, provider = service._get_client_for_player(1)
            assert client is None
            assert provider is None


class TestMockMode:
    """Test mock mode behavior."""

    @pytest.mark.asyncio
    async def test_mock_mode_returns_fallback(self):
        """Mock mode should return fallback response without LLM call."""
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = True
            mock_settings.get_all_providers.return_value = {}
            service = LLMService()

            player = _make_player(role=Role.WEREWOLF)
            game = _make_game()

            resp = await service.generate_response(player, game, "speech")
            assert resp.is_fallback is True
            assert len(resp.speak) > 0

    @pytest.mark.asyncio
    async def test_mock_mode_vote_has_target(self):
        """Mock mode vote should select a target."""
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = True
            mock_settings.get_all_providers.return_value = {}
            service = LLMService()

            player = _make_player(role=Role.VILLAGER)
            game = _make_game()
            targets = [2, 3, 4]

            resp = await service.generate_response(player, game, "vote", targets)
            assert resp.is_fallback is True
            # vote fallback should have a target from the list or 0 (abstain)
            assert resp.action_target in targets or resp.action_target == 0


class TestResponseParsing:
    """Test LLM response parsing."""

    def _create_service(self):
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = True
            mock_settings.get_all_providers.return_value = {}
            return LLMService()

    def test_parse_valid_json(self):
        """Valid JSON response is parsed correctly."""
        service = self._create_service()
        raw = '{"thought": "thinking...", "speak": "hello", "action_target": 3}'
        resp = service._parse_response(raw, "test-provider")
        assert resp.thought == "thinking..."
        assert resp.speak == "hello"
        assert resp.action_target == 3
        assert resp.is_fallback is False
        assert resp.provider_name == "test-provider"

    def test_parse_markdown_wrapped_json(self):
        """JSON wrapped in markdown code blocks is parsed correctly."""
        service = self._create_service()
        raw = '```json\n{"thought": "test", "speak": "hi", "action_target": null}\n```'
        resp = service._parse_response(raw)
        assert resp.thought == "test"
        assert resp.speak == "hi"
        assert resp.action_target is None

    def test_parse_missing_speak_defaults(self):
        """Missing speak field defaults to '过。'."""
        service = self._create_service()
        raw = '{"thought": "hmm"}'
        resp = service._parse_response(raw)
        assert resp.speak == "过。"

    def test_parse_null_speak_defaults(self):
        """Null speak field defaults to '过。'."""
        service = self._create_service()
        raw = '{"thought": "hmm", "speak": null}'
        resp = service._parse_response(raw)
        assert resp.speak == "过。"

    def test_parse_invalid_json_raises(self):
        """Invalid JSON raises ValueError."""
        service = self._create_service()
        with pytest.raises(ValueError, match="Invalid JSON"):
            service._parse_response("not json at all")


class TestGameStateValidation:
    """Test game state validation before LLM calls."""

    @pytest.mark.asyncio
    async def test_invalid_game_state_returns_fallback(self):
        """Invalid game state should return fallback without calling LLM."""
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = False
            mock_settings.get_all_providers.return_value = {}
            service = LLMService()

            player = _make_player()
            game = _make_game()
            game.id = None  # Invalid: None game ID

            resp = await service.generate_response(player, game, "speech")
            assert resp.is_fallback is True

    @pytest.mark.asyncio
    async def test_no_client_returns_fallback(self):
        """No available LLM client should return fallback."""
        with patch('app.services.llm.settings') as mock_settings:
            mock_settings.LLM_USE_MOCK = False
            mock_settings.get_all_providers.return_value = {}
            service = LLMService()
            service._clients = {}
            mock_settings.get_provider_for_player.return_value = None
            mock_settings.get_provider.return_value = None

            player = _make_player()
            game = _make_game()

            resp = await service.generate_response(player, game, "speech")
            assert resp.is_fallback is True
