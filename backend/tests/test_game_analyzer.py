"""Unit tests for game_analyzer client configuration."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestGameAnalyzerClientConfig:
    """Test that game_analyzer uses same client config as llm.py."""

    def test_custom_user_agent_imported(self):
        """验证 game_analyzer 导入了与 llm.py 相同的 CUSTOM_USER_AGENT."""
        from app.services.llm import CUSTOM_USER_AGENT as LLM_USER_AGENT
        from app.services.game_analyzer import CUSTOM_USER_AGENT as ANALYZER_USER_AGENT

        # 应该是同一个常量（通过导入共享）
        assert LLM_USER_AGENT == ANALYZER_USER_AGENT
        assert "Mozilla/5.0" in ANALYZER_USER_AGENT
        assert "Chrome" in ANALYZER_USER_AGENT

    def test_no_httpx_import_in_analyzer(self):
        """验证 game_analyzer 不再直接导入 httpx."""
        import app.services.game_analyzer as analyzer_module
        import sys

        # 检查模块是否有 httpx 属性（不应该有）
        assert not hasattr(analyzer_module, 'httpx'), \
            "game_analyzer should not import httpx directly anymore"

    @pytest.mark.asyncio
    async def test_async_openai_uses_default_headers(self):
        """验证 AsyncOpenAI 使用 default_headers 而非 http_client."""
        from app.services.game_analyzer import _call_ai_analyzer
        from app.core.config import AIProviderConfig

        # Mock provider
        mock_provider = AIProviderConfig(
            name="test",
            api_key="test-key",
            base_url="https://api.test.com/v1",
            model="test-model",
            max_retries=2,
            temperature=0.7,
            max_tokens=4000,
        )

        with patch('app.services.game_analyzer.settings') as mock_settings, \
             patch('app.services.game_analyzer.AsyncOpenAI') as MockAsyncOpenAI:

            mock_settings.get_analysis_provider.return_value = mock_provider

            # Setup mock client
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test analysis content that is long enough"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value = mock_client

            # Call the function
            result = await _call_ai_analyzer("test prompt", "zh", "comprehensive")

            # Verify AsyncOpenAI was called with default_headers (not http_client)
            MockAsyncOpenAI.assert_called_once()
            call_kwargs = MockAsyncOpenAI.call_args[1]

            assert 'default_headers' in call_kwargs, \
                "AsyncOpenAI should be initialized with default_headers"
            assert 'http_client' not in call_kwargs, \
                "AsyncOpenAI should NOT be initialized with http_client"
            assert call_kwargs['default_headers']['User-Agent'] is not None
            assert 'timeout' in call_kwargs
            assert call_kwargs['timeout'] == 120.0

    def test_llm_and_analyzer_use_same_pattern(self):
        """验证 llm.py 和 game_analyzer.py 使用相同的客户端初始化模式."""
        import inspect
        from app.services import llm, game_analyzer

        # 读取两个模块的源代码
        llm_source = inspect.getsource(llm)
        analyzer_source = inspect.getsource(game_analyzer)

        # 验证两者都使用 default_headers
        assert 'default_headers={"User-Agent": CUSTOM_USER_AGENT}' in llm_source or \
               "default_headers={'User-Agent': CUSTOM_USER_AGENT}" in llm_source, \
               "llm.py should use default_headers"

        assert 'default_headers={"User-Agent": CUSTOM_USER_AGENT}' in analyzer_source or \
               "default_headers={'User-Agent': CUSTOM_USER_AGENT}" in analyzer_source, \
               "game_analyzer.py should use default_headers"

        # 验证 analyzer 不再使用 httpx.AsyncClient
        assert 'httpx.AsyncClient' not in analyzer_source, \
            "game_analyzer should not use httpx.AsyncClient anymore"
        assert 'http_client=' not in analyzer_source, \
            "game_analyzer should not pass http_client to AsyncOpenAI"
