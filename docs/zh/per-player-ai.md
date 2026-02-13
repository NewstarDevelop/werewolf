# 玩家级别 AI 配置

Werewolf AI 的独特功能之一是可以为不同游戏座位配置不同的 AI 模型，创造多样化且不可预测的游戏体验。

## 概览

在一场典型游戏中：
- 2-9 号座位可以是 AI 玩家
- 每个座位可以使用不同的 LLM Provider
- 不同模型会创造出独特的"性格"

## 配置方式

有三种方式配置玩家级别 AI：

### 方式 1：Provider 映射（推荐）

将座位映射到已有的 Provider：

```bash
# 首先配置 Provider
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# 然后映射座位到 Provider
AI_PLAYER_2_PROVIDER=openai
AI_PLAYER_3_PROVIDER=deepseek
AI_PLAYER_4_PROVIDER=anthropic
AI_PLAYER_5_PROVIDER=openai
```

### 方式 2：JSON 批量映射

一次性配置多个座位：

```bash
AI_PLAYER_MAPPING={"2":"openai","3":"deepseek","4":"anthropic","5":"moonshot"}
```

### 方式 3：专用配置

为单个座位完整配置：

```bash
AI_PLAYER_2_API_KEY=sk-custom-key
AI_PLAYER_2_BASE_URL=https://api.openai.com/v1
AI_PLAYER_2_MODEL=gpt-4o
AI_PLAYER_2_TEMPERATURE=0.8
AI_PLAYER_2_MAX_TOKENS=600
AI_PLAYER_2_MAX_RETRIES=3
```

## 优先级顺序

当存在多种配置时：

1. 专用配置（`AI_PLAYER_N_*`）
2. Provider 映射（`AI_PLAYER_N_PROVIDER`）
3. JSON 映射（`AI_PLAYER_MAPPING`）
4. 默认 Provider（`OPENAI_API_KEY`）

## 配置示例

### 多样化对战（4 个不同 Provider）

```bash
# Provider 密钥
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
MOONSHOT_API_KEY=sk-xxx

# 座位映射
AI_PLAYER_MAPPING={"2":"openai","3":"deepseek","4":"anthropic","5":"moonshot","6":"openai","7":"deepseek"}
```

### 成本优化（混合高低价模型）

```bash
# 关键角色使用 GPT-4
AI_PLAYER_2_PROVIDER=openai
AI_PLAYER_2_MODEL=gpt-4o

# 其他使用低价模型
AI_PLAYER_3_PROVIDER=deepseek
AI_PLAYER_4_PROVIDER=deepseek
AI_PLAYER_5_PROVIDER=deepseek
```

### 开发测试

```bash
# 在一个座位上测试特定 Provider
AI_PLAYER_2_PROVIDER=anthropic
AI_PLAYER_2_MODEL=claude-3-opus-20240229

# 其他使用 Mock
LLM_USE_MOCK=true
```

## 模型行为差异

不同模型表现出不同的行为特征：

| 模型 | 行为特征 |
|------|----------|
| GPT-4 | 逻辑性强，分析细致 |
| GPT-4o-mini | 反应快，回复简洁 |
| Claude | 创造性强，解释详细 |
| DeepSeek | 均衡表现，性价比高 |
| Moonshot | 中文支持好 |

## 座位号说明

| 座位 | 备注 |
|------|------|
| 1 | 通常为人类玩家（房主） |
| 2-9 | 可以是 AI 或人类 |

## 回退行为

当配置的 Provider 失败时：
1. 系统根据 `MAX_RETRIES` 进行重试
2. 所有重试失败后，该回合可能超时
3. 不会自动回退到其他 Provider

## 监控

可通过以下方式查看每个座位使用的 Provider：
- 管理面板
- 后端日志（`LOG_LEVEL=DEBUG`）
- API 端点 `/api/admin/providers`

## 最佳实践

1. **单独测试 Provider** - 混合使用前先单独验证
2. **设置合理的速率限制** - 避免 API 限流
3. **使用 JSON 映射** - 方便快速实验
4. **监控费用** - 使用多个付费 API 时注意成本
5. **考虑延迟** - 部分 Provider 响应较慢
