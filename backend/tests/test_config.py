"""Unit tests for configuration priority logic."""
import os
import json
import pytest
from unittest.mock import patch

from app.core.config import Settings, AIProviderConfig


class TestConfigPriority:
    """Test AI provider configuration priority logic."""

    @patch.dict(os.environ, {}, clear=True)
    def test_default_provider_fallback(self):
        """测试未配置的玩家使用 default provider."""
        # 只配置默认 provider
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-default-key",
            "OPENAI_MODEL": "gpt-4o-mini",
            "LLM_MODEL": "gpt-4o-mini",
        }):
            settings = Settings()

            # 验证 default provider 已创建
            assert "default" in settings.get_all_providers()
            default_provider = settings.get_provider("default")
            assert default_provider is not None
            assert default_provider.api_key == "sk-default-key"
            assert default_provider.model == "gpt-4o-mini"

            # 验证未配置的玩家（座位2-9）使用 default provider
            for seat_id in range(2, 10):
                provider = settings.get_provider_for_player(seat_id)
                assert provider is not None
                assert provider.name == "default"
                assert provider.api_key == "sk-default-key"

            # 验证没有玩家映射（除了 default 兜底）
            mappings = settings.get_player_mappings()
            assert len(mappings) == 0  # 没有显式映射

    @patch.dict(os.environ, {}, clear=True)
    def test_player_specific_config_priority(self):
        """测试玩家专属配置（player_{seat}）不会被默认配置覆盖."""
        # 配置 default provider 和玩家3的专属 provider
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-default-key",
            "OPENAI_MODEL": "gpt-4o-mini",
            "LLM_MODEL": "gpt-4o-mini",
            "AI_PLAYER_3_API_KEY": "sk-player3-key",
            "AI_PLAYER_3_MODEL": "gpt-4",
            "AI_PLAYER_3_BASE_URL": "https://custom.api.com/v1",
        }):
            settings = Settings()

            # 验证 default provider 已创建
            default_provider = settings.get_provider("default")
            assert default_provider is not None
            assert default_provider.api_key == "sk-default-key"

            # 验证 player_3 专属 provider 已创建
            player3_provider = settings.get_provider("player_3")
            assert player3_provider is not None
            assert player3_provider.api_key == "sk-player3-key"
            assert player3_provider.model == "gpt-4"
            assert player3_provider.base_url == "https://custom.api.com/v1"

            # 验证玩家3使用专属配置（优先级3：自动映射）
            provider = settings.get_provider_for_player(3)
            assert provider is not None
            assert provider.name == "player_3"
            assert provider.api_key == "sk-player3-key"
            assert provider.model == "gpt-4"

            # 验证其他玩家仍使用 default provider
            for seat_id in [2, 4, 5, 6, 7, 8, 9]:
                provider = settings.get_provider_for_player(seat_id)
                assert provider.name == "default"
                assert provider.api_key == "sk-default-key"

            # 验证玩家映射
            mappings = settings.get_player_mappings()
            assert mappings[3] == "player_3"

    @patch.dict(os.environ, {}, clear=True)
    def test_provider_mapping_highest_priority(self):
        """测试 AI_PLAYER_{seat}_PROVIDER 拥有最高优先级."""
        # 配置多个 provider 和多种映射方式
        with patch.dict(os.environ, {
            # Default provider
            "OPENAI_API_KEY": "sk-default-key",
            "LLM_MODEL": "gpt-4o-mini",

            # Named provider: Anthropic
            "ANTHROPIC_API_KEY": "sk-anthropic-key",
            "ANTHROPIC_MODEL": "claude-3-haiku-20240307",

            # Player 3: 专属配置（优先级3：自动映射到 player_3）
            "AI_PLAYER_3_API_KEY": "sk-player3-deepseek-key",
            "AI_PLAYER_3_MODEL": "deepseek-chat",

            # Player 4: JSON批量映射（优先级2：映射到 anthropic）
            "AI_PLAYER_MAPPING": json.dumps({"4": "anthropic"}),

            # Player 3 & 5: 单独映射（优先级1：最高）
            "AI_PLAYER_3_PROVIDER": "anthropic",  # 覆盖 player_3 自动映射
            "AI_PLAYER_5_PROVIDER": "anthropic",  # 直接映射到 anthropic
        }):
            settings = Settings()

            # 验证所有 provider 已创建
            assert "default" in settings.get_all_providers()
            assert "anthropic" in settings.get_all_providers()
            assert "player_3" in settings.get_all_providers()

            # 玩家3: AI_PLAYER_3_PROVIDER=anthropic 应覆盖 player_3 自动映射
            # 最高优先级（个别映射）应该生效
            provider3 = settings.get_provider_for_player(3)
            assert provider3 is not None
            assert provider3.name == "anthropic"  # 不是 player_3
            assert provider3.api_key == "sk-anthropic-key"
            assert provider3.model == "claude-3-haiku-20240307"

            # 玩家4: JSON映射到 anthropic
            provider4 = settings.get_provider_for_player(4)
            assert provider4 is not None
            assert provider4.name == "anthropic"
            assert provider4.api_key == "sk-anthropic-key"

            # 玩家5: AI_PLAYER_5_PROVIDER=anthropic（没有专属配置，直接映射）
            provider5 = settings.get_provider_for_player(5)
            assert provider5 is not None
            assert provider5.name == "anthropic"
            assert provider5.api_key == "sk-anthropic-key"

            # 玩家2: 使用 default（没有任何配置）
            provider2 = settings.get_provider_for_player(2)
            assert provider2 is not None
            assert provider2.name == "default"
            assert provider2.api_key == "sk-default-key"

            # 验证映射优先级
            mappings = settings.get_player_mappings()
            assert mappings[3] == "anthropic"  # 个别映射覆盖了自动映射
            assert mappings[4] == "anthropic"  # JSON映射
            assert mappings[5] == "anthropic"  # 个别映射

    @patch.dict(os.environ, {}, clear=True)
    def test_json_mapping_priority(self):
        """测试 AI_PLAYER_MAPPING JSON批量映射的优先级（覆盖自动映射）."""
        with patch.dict(os.environ, {
            # Default provider
            "OPENAI_API_KEY": "sk-default-key",
            "LLM_MODEL": "gpt-4o-mini",

            # Named provider: DeepSeek
            "DEEPSEEK_API_KEY": "sk-deepseek-key",
            "DEEPSEEK_MODEL": "deepseek-chat",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",

            # Player 3: 专属配置（会自动映射到 player_3）
            "AI_PLAYER_3_API_KEY": "sk-player3-key",
            "AI_PLAYER_3_MODEL": "gpt-4",

            # JSON批量映射：玩家3映射到 deepseek（应覆盖自动映射）
            "AI_PLAYER_MAPPING": json.dumps({"3": "deepseek", "4": "deepseek"}),
        }):
            settings = Settings()

            # 验证 provider 已创建
            assert "player_3" in settings.get_all_providers()
            assert "deepseek" in settings.get_all_providers()

            # 玩家3: JSON映射应覆盖自动映射
            # 优先级2（JSON）> 优先级3（自动映射）
            provider3 = settings.get_provider_for_player(3)
            assert provider3 is not None
            assert provider3.name == "deepseek"  # 不是 player_3
            assert provider3.api_key == "sk-deepseek-key"

            # 玩家4: JSON映射
            provider4 = settings.get_provider_for_player(4)
            assert provider4 is not None
            assert provider4.name == "deepseek"

            # 验证映射
            mappings = settings.get_player_mappings()
            assert mappings[3] == "deepseek"  # JSON覆盖了自动映射
            assert mappings[4] == "deepseek"

    @patch.dict(os.environ, {}, clear=True)
    def test_invalid_provider_mapping_warning(self):
        """测试映射到不存在的 provider 会使用回退."""
        with patch.dict(os.environ, {
            # Default provider
            "OPENAI_API_KEY": "sk-default-key",
            "LLM_MODEL": "gpt-4o-mini",

            # 映射到不存在的 provider
            "AI_PLAYER_3_PROVIDER": "nonexistent",
        }):
            settings = Settings()

            # 玩家3应该回退到 default（因为 'nonexistent' 不存在）
            provider3 = settings.get_provider_for_player(3)
            assert provider3 is not None
            assert provider3.name == "default"

            # 映射不应该建立（因为 provider 不存在）
            mappings = settings.get_player_mappings()
            assert 3 not in mappings or mappings[3] != "nonexistent"

    @patch.dict(os.environ, {}, clear=True)
    def test_no_api_key_no_player_provider(self):
        """测试没有 API_KEY 时不会创建 player_{seat} provider."""
        with patch.dict(os.environ, {
            # Default provider
            "OPENAI_API_KEY": "sk-default-key",
            "LLM_MODEL": "gpt-4o-mini",

            # 只配置 MODEL，没有 API_KEY
            "AI_PLAYER_3_MODEL": "gpt-4",
            "AI_PLAYER_3_BASE_URL": "https://custom.api.com/v1",
        }):
            settings = Settings()

            # player_3 provider 不应该被创建
            assert "player_3" not in settings.get_all_providers()

            # 玩家3应该使用 default provider
            provider3 = settings.get_provider_for_player(3)
            assert provider3 is not None
            assert provider3.name == "default"
            assert provider3.api_key == "sk-default-key"

            # 没有玩家3的映射
            mappings = settings.get_player_mappings()
            assert 3 not in mappings
