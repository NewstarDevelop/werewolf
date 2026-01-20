# LLM Provider Configuration

Werewolf AI supports multiple LLM providers through a unified configuration system.

## Supported Providers

| Provider | Prefix | Default Model | Notes |
|----------|--------|---------------|-------|
| OpenAI | `OPENAI` | gpt-4o-mini | Default provider |
| DeepSeek | `DEEPSEEK` | deepseek-chat | Cost-effective |
| Anthropic | `ANTHROPIC` | claude-3-haiku | Advanced reasoning |
| Moonshot | `MOONSHOT` | moonshot-v1-8k | Chinese provider |
| Qwen | `QWEN` | qwen-turbo | Alibaba Cloud |
| GLM | `GLM` | glm-4-flash | Zhipu AI |
| Doubao | `DOUBAO` | doubao-pro-4k | ByteDance |
| MiniMax | `MINIMAX` | abab6.5s-chat | MiniMax AI |
| Custom | `AI_PROVIDER_N` | - | Any compatible API |

## Configuration Pattern

Each provider uses the same configuration pattern:

```bash
{PREFIX}_API_KEY=your-api-key
{PREFIX}_BASE_URL=https://api.provider.com/v1
{PREFIX}_MODEL=model-name
{PREFIX}_MAX_RETRIES=2
{PREFIX}_TEMPERATURE=0.7
{PREFIX}_MAX_TOKENS=500
```

## Provider Examples

### OpenAI (Default)

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### DeepSeek

```bash
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

### Anthropic Claude

```bash
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
ANTHROPIC_MODEL=claude-3-haiku-20240307
```

### Custom Provider

For any OpenAI-compatible API:

```bash
AI_PROVIDER_1_NAME=my-custom
AI_PROVIDER_1_API_KEY=xxx
AI_PROVIDER_1_BASE_URL=https://my-api.com/v1
AI_PROVIDER_1_MODEL=my-model
```

You can define up to 9 custom providers (AI_PROVIDER_1 through AI_PROVIDER_9).

## Provider Selection

### Default Provider

Without explicit configuration, the system uses OpenAI with `LLM_MODEL`.

### Analysis Provider

Separate provider for post-game analysis:

```bash
ANALYSIS_PROVIDER=anthropic
ANALYSIS_MODEL=claude-3-opus-20240229
```

### Per-Player Provider

See [Per-Player AI](per-player-ai.md) for seat-level configuration.

## API Compatibility

All providers must be OpenAI API compatible. The system uses the OpenAI SDK with custom base URLs.

### Required Endpoints

- `POST /chat/completions` - Chat completion endpoint

### Expected Response Format

```json
{
  "choices": [
    {
      "message": {
        "content": "AI response"
      }
    }
  ]
}
```

## Rate Limiting

Per-provider rate limits can be configured:

```bash
DEFAULT_REQUESTS_PER_MINUTE=60
DEFAULT_MAX_CONCURRENCY=5
DEFAULT_BURST=3
```

The system includes built-in retry logic with exponential backoff.

## Cost Optimization

### Strategy 1: Mixed Providers

Use expensive models for important roles:

```bash
AI_PLAYER_2_PROVIDER=openai    # Seer - needs reasoning
AI_PLAYER_3_PROVIDER=deepseek  # Villager - cost-effective
```

### Strategy 2: Analysis Separation

Use advanced model only for analysis:

```bash
LLM_MODEL=gpt-4o-mini              # Game AI
ANALYSIS_MODEL=gpt-4o              # Post-game analysis
```

### Strategy 3: Mock Mode

For testing without API costs:

```bash
LLM_USE_MOCK=true
```

## Troubleshooting

### Provider Not Found

Ensure all required variables are set:
- `{PREFIX}_API_KEY` is mandatory
- `{PREFIX}_BASE_URL` may be required for non-OpenAI providers

### Authentication Error

- Verify API key is valid
- Check if key has required permissions
- Ensure base URL is correct

### Rate Limit Exceeded

- Reduce `DEFAULT_REQUESTS_PER_MINUTE`
- Increase `LLM_MAX_WAIT_SECONDS`
- Consider using multiple providers to distribute load
