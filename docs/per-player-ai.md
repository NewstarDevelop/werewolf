# Per-Player AI Configuration

One of Werewolf AI's unique features is the ability to configure different AI models for different game seats, creating diverse and unpredictable gameplay.

## Overview

In a typical game:
- Seats 2-9 can be AI players
- Each seat can use a different LLM provider
- Different models create unique "personalities"

## Configuration Methods

There are three ways to configure per-player AI:

### Method 1: Provider Mapping (Recommended)

Map seats to existing providers:

```bash
# First, configure the providers
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# Then map seats to providers
AI_PLAYER_2_PROVIDER=openai
AI_PLAYER_3_PROVIDER=deepseek
AI_PLAYER_4_PROVIDER=anthropic
AI_PLAYER_5_PROVIDER=openai
```

### Method 2: JSON Batch Mapping

Configure multiple seats at once:

```bash
AI_PLAYER_MAPPING={"2":"openai","3":"deepseek","4":"anthropic","5":"moonshot"}
```

### Method 3: Dedicated Configuration

Full configuration per seat:

```bash
AI_PLAYER_2_API_KEY=sk-custom-key
AI_PLAYER_2_BASE_URL=https://api.openai.com/v1
AI_PLAYER_2_MODEL=gpt-4o
AI_PLAYER_2_TEMPERATURE=0.8
AI_PLAYER_2_MAX_TOKENS=600
AI_PLAYER_2_MAX_RETRIES=3
```

## Priority Order

When multiple configurations exist:

1. Dedicated configuration (`AI_PLAYER_N_*`)
2. Provider mapping (`AI_PLAYER_N_PROVIDER`)
3. JSON mapping (`AI_PLAYER_MAPPING`)
4. Default provider (`OPENAI_API_KEY`)

## Example Configurations

### Diverse Battle (4 Different Providers)

```bash
# Provider keys
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
MOONSHOT_API_KEY=sk-xxx

# Seat mapping
AI_PLAYER_MAPPING={"2":"openai","3":"deepseek","4":"anthropic","5":"moonshot","6":"openai","7":"deepseek"}
```

### Cost-Optimized (Mix Expensive and Cheap)

```bash
# Use GPT-4 for key roles
AI_PLAYER_2_PROVIDER=openai
AI_PLAYER_2_MODEL=gpt-4o

# Use cheaper models for others
AI_PLAYER_3_PROVIDER=deepseek
AI_PLAYER_4_PROVIDER=deepseek
AI_PLAYER_5_PROVIDER=deepseek
```

### Development Testing

```bash
# Test specific provider on one seat
AI_PLAYER_2_PROVIDER=anthropic
AI_PLAYER_2_MODEL=claude-3-opus-20240229

# Others use mock
LLM_USE_MOCK=true
```

## Model Personality Differences

Different models exhibit different behaviors:

| Model | Behavior |
|-------|----------|
| GPT-4 | Logical, thorough analysis |
| GPT-4o-mini | Quick, concise responses |
| Claude | Creative, detailed explanations |
| DeepSeek | Balanced, cost-effective |
| Moonshot | Good Chinese language support |

## Seat Numbers

| Seat | Notes |
|------|-------|
| 1 | Usually human player (host) |
| 2-9 | Can be AI or human |

## Fallback Behavior

If a configured provider fails:
1. System retries based on `MAX_RETRIES`
2. If all retries fail, the turn may time out
3. No automatic fallback to other providers

## Monitoring

Check which provider each seat uses via:
- Admin panel
- Backend logs (`LOG_LEVEL=DEBUG`)
- API endpoint `/api/admin/providers`

## Best Practices

1. **Test providers individually** before mixing
2. **Set appropriate rate limits** to avoid API throttling
3. **Use JSON mapping** for quick experimentation
4. **Monitor costs** when using multiple paid APIs
5. **Consider latency** - some providers are slower than others
