# LLM Provider 配置

Werewolf AI 通过统一的配置系统支持多种 LLM Provider。

## 支持的 Provider

| Provider | 前缀 | 默认模型 | 备注 |
|----------|------|----------|------|
| OpenAI | `OPENAI` | gpt-4o-mini | 默认 Provider |
| DeepSeek | `DEEPSEEK` | deepseek-chat | 高性价比 |
| Anthropic | `ANTHROPIC` | claude-3-haiku | 高级推理 |
| Moonshot | `MOONSHOT` | moonshot-v1-8k | 国产 Provider |
| Qwen | `QWEN` | qwen-turbo | 阿里云 |
| GLM | `GLM` | glm-4-flash | 智谱 AI |
| Doubao | `DOUBAO` | doubao-pro-4k | 字节跳动 |
| MiniMax | `MINIMAX` | abab6.5s-chat | MiniMax AI |
| 自定义 | `AI_PROVIDER_N` | - | 任何兼容 API |

## 配置模式

每个 Provider 使用相同的配置模式：

```bash
{PREFIX}_API_KEY=your-api-key
{PREFIX}_BASE_URL=https://api.provider.com/v1
{PREFIX}_MODEL=model-name
{PREFIX}_MAX_RETRIES=2
{PREFIX}_TEMPERATURE=0.7
{PREFIX}_MAX_TOKENS=500
```

## Provider 配置示例

### OpenAI（默认）

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

### 自定义 Provider

适用于任何 OpenAI 兼容 API：

```bash
AI_PROVIDER_1_NAME=my-custom
AI_PROVIDER_1_API_KEY=xxx
AI_PROVIDER_1_BASE_URL=https://my-api.com/v1
AI_PROVIDER_1_MODEL=my-model
```

最多可定义 9 个自定义 Provider（AI_PROVIDER_1 到 AI_PROVIDER_9）。

## Provider 选择

### 默认 Provider

未显式配置时，系统使用 OpenAI 和 `LLM_MODEL`。

### 分析 Provider

赛后分析可使用独立的 Provider：

```bash
ANALYSIS_PROVIDER=anthropic
ANALYSIS_MODEL=claude-3-opus-20240229
```

### 玩家级别 Provider

详见 [玩家级别 AI](per-player-ai.md) 了解座位级配置。

## API 兼容性

所有 Provider 必须兼容 OpenAI API。系统使用 OpenAI SDK 配合自定义 base URL。

### 必要端点

- `POST /chat/completions` - 对话补全端点

### 预期响应格式

```json
{
  "choices": [
    {
      "message": {
        "content": "AI 响应"
      }
    }
  ]
}
```

## 速率限制

可按 Provider 配置速率限制：

```bash
DEFAULT_REQUESTS_PER_MINUTE=60
DEFAULT_MAX_CONCURRENCY=5
DEFAULT_BURST=3
```

系统内置指数退避重试逻辑。

## 成本优化

### 策略 1：混合 Provider

为重要角色使用高级模型：

```bash
AI_PLAYER_2_PROVIDER=openai    # 预言家 - 需要推理能力
AI_PLAYER_3_PROVIDER=deepseek  # 村民 - 高性价比
```

### 策略 2：分析分离

仅在分析时使用高级模型：

```bash
LLM_MODEL=gpt-4o-mini              # 游戏 AI
ANALYSIS_MODEL=gpt-4o              # 赛后分析
```

### 策略 3：Mock 模式

无 API 费用的测试模式：

```bash
LLM_USE_MOCK=true
```

## 故障排查

### Provider 未找到

确保所有必要变量已设置：
- `{PREFIX}_API_KEY` 为必填项
- 非 OpenAI Provider 可能需要设置 `{PREFIX}_BASE_URL`

### 认证错误

- 验证 API Key 是否有效
- 检查 Key 是否有必要权限
- 确保 base URL 正确

### 超出速率限制

- 降低 `DEFAULT_REQUESTS_PER_MINUTE`
- 增加 `LLM_MAX_WAIT_SECONDS`
- 考虑使用多个 Provider 分散负载
