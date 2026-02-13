# 对局分析配置

Werewolf AI 内置 AI 驱动的赛后分析功能，帮助玩家理解游戏过程并提升策略水平。

## 概览

游戏结束后，分析系统可以：
- 评估玩家表现
- 识别关键决策点
- 分析投票模式
- 提供策略反馈
- 生成游戏总结

## 配置

### 基本设置

分析默认使用全局 LLM Provider，无需额外配置：

```bash
# 使用默认 OpenAI 配置
# 无需额外设置
```

### 专用分析 Provider

为获得更好的分析质量，可使用更强的模型：

```bash
ANALYSIS_PROVIDER=openai
ANALYSIS_MODEL=gpt-4o
```

或使用完全不同的 Provider：

```bash
ANALYSIS_PROVIDER=anthropic
ANALYSIS_MODEL=claude-3-opus-20240229
```

### 分析模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `comprehensive` | 详细分析 | 赛后复盘 |
| `quick` | 快速总结 | 休闲对局 |
| `custom` | 自定义参数 | 高级用户 |

```bash
ANALYSIS_MODE=comprehensive
```

### 语言设置

```bash
# 根据游戏内容自动检测
ANALYSIS_LANGUAGE=auto

# 强制使用中文
ANALYSIS_LANGUAGE=zh

# 强制使用英文
ANALYSIS_LANGUAGE=en
```

### 生成参数

```bash
ANALYSIS_MAX_TOKENS=4000
ANALYSIS_TEMPERATURE=0.7
```

- 较高温度 = 分析更具创意
- 较低温度 = 分析更偏事实

### 缓存

```bash
# 启用缓存（默认）
ANALYSIS_CACHE_ENABLED=true
```

缓存分析结果以避免对同一局游戏重复调用 API。

## 分析内容

### 玩家表现

- 角色识别准确度
- 投票一致性
- 发言分析
- 策略决策

### 游戏进程

- 关键转折点
- 关键失误
- 制胜策略
- 险胜时刻

### 建议

- 哪些地方可以做得更好
- 各角色的最优策略
- 应避免的常见陷阱

## API 集成

分析结果可通过以下方式获取：

- 游戏结束后的 WebSocket 事件
- REST API 端点
- 管理面板查看

## 费用考量

分析比常规游戏使用更多 Token：

| 模式 | 大约 Token 数 |
|------|---------------|
| 快速 | 1000-2000 |
| 详细 | 3000-5000 |

降低费用的方法：
- 休闲对局使用 `quick` 模式
- 测试游戏禁用分析
- 使用高性价比 Provider

## 禁用分析

分析是可选功能。未配置时，游戏正常运行，不会有赛后分析。

如需显式禁用（已配置的情况下）：
- 移除 `ANALYSIS_PROVIDER` 设置
- 或将 `ANALYSIS_MODE` 设为不支持的值

## 故障排查

### 分析未生成

- 检查 `ANALYSIS_PROVIDER` 是否有效
- 确认 API Key 有足够额度
- 查看后端日志中的错误

### 分析质量不佳

- 尝试更强的模型
- 增加 `ANALYSIS_MAX_TOKENS`
- 使用 `comprehensive` 模式

### 分析速度慢

- 复杂游戏的分析可能需要 30-60 秒
- 考虑使用 `quick` 模式
- 启用缓存加速重复查看
