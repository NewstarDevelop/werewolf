# Game Analysis Configuration

Werewolf AI includes AI-powered post-game analysis to help players understand gameplay and improve strategies.

## Overview

After a game ends, the analysis system can:
- Evaluate player performance
- Identify key decision points
- Analyze voting patterns
- Provide strategic feedback
- Generate game summaries

## Configuration

### Basic Setup

Analysis uses the default LLM provider unless configured separately:

```bash
# Use default OpenAI configuration
# No additional config needed
```

### Dedicated Analysis Provider

For better analysis quality, use a more capable model:

```bash
ANALYSIS_PROVIDER=openai
ANALYSIS_MODEL=gpt-4o
```

Or use a different provider entirely:

```bash
ANALYSIS_PROVIDER=anthropic
ANALYSIS_MODEL=claude-3-opus-20240229
```

### Analysis Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `comprehensive` | Detailed analysis | Post-tournament review |
| `quick` | Fast summary | Casual games |
| `custom` | Custom parameters | Advanced users |

```bash
ANALYSIS_MODE=comprehensive
```

### Language Settings

```bash
# Auto-detect based on game content
ANALYSIS_LANGUAGE=auto

# Force Chinese
ANALYSIS_LANGUAGE=zh

# Force English
ANALYSIS_LANGUAGE=en
```

### Generation Parameters

```bash
ANALYSIS_MAX_TOKENS=4000
ANALYSIS_TEMPERATURE=0.7
```

- Higher temperature = more creative analysis
- Lower temperature = more factual analysis

### Caching

```bash
# Enable caching (default)
ANALYSIS_CACHE_ENABLED=true
```

Cached analyses are stored to avoid redundant API calls for the same game.

## Analysis Content

### Player Performance

- Role identification accuracy
- Vote consistency
- Speech analysis
- Strategic decisions

### Game Flow

- Key turning points
- Critical mistakes
- Winning strategies
- Close calls

### Recommendations

- What could have been done differently
- Optimal strategies for each role
- Common pitfalls to avoid

## API Integration

Analysis results are available via:

- WebSocket events after game end
- REST API endpoint
- Admin panel view

## Cost Considerations

Analysis uses more tokens than regular gameplay:

| Mode | Approximate Tokens |
|------|-------------------|
| Quick | 1000-2000 |
| Comprehensive | 3000-5000 |

To reduce costs:
- Use `quick` mode for casual games
- Disable analysis for test games
- Use a cost-effective provider

## Disabling Analysis

Analysis is optional. Without configuration, games work normally without post-game analysis.

To explicitly disable if configured:
- Remove `ANALYSIS_PROVIDER` setting
- Or set `ANALYSIS_MODE` to an unsupported value

## Troubleshooting

### Analysis Not Generated

- Check `ANALYSIS_PROVIDER` is valid
- Verify API key has sufficient credits
- Check backend logs for errors

### Analysis Quality Issues

- Try a more capable model
- Increase `ANALYSIS_MAX_TOKENS`
- Use `comprehensive` mode

### Slow Analysis

- Analysis may take 30-60 seconds for complex games
- Consider using `quick` mode
- Enable caching to speed up repeated views
