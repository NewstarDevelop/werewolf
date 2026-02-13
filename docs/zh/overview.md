# 项目概述

## 什么是 Werewolf AI？

Werewolf AI 是一款支持人类玩家与 AI 玩家混合对战的在线狼人杀游戏。AI 玩家由大语言模型（LLM）驱动，具备以下能力：

- 自然语言对话
- 逻辑推理与分析
- 策略决策
- 适应不同游戏局势

## 核心特性

### 多模型支持

项目支持 9+ 种 LLM Provider：

| Provider | 模型 |
|----------|------|
| OpenAI | GPT-4, GPT-4o, GPT-4o-mini |
| DeepSeek | deepseek-chat |
| Anthropic | Claude 3 Haiku/Sonnet/Opus |
| Moonshot | moonshot-v1-8k/32k |
| Qwen | qwen-turbo/plus/max |
| GLM | glm-4-flash/air/plus |
| Doubao | doubao-pro-4k/32k |
| MiniMax | abab6.5s-chat |
| 自定义 | 任何 OpenAI 兼容 API |

### 玩家级别 AI 配置

独特功能：可为不同游戏座位配置不同的 AI 模型：

- 2 号位使用 GPT-4o 进行高级推理
- 3 号位使用 DeepSeek 以降低成本
- 4 号位使用 Claude 获取创意回复

这创造了多样化且不可预测的游戏体验。

### 实时对战

- 基于 WebSocket 的状态同步
- 即时消息传递
- 实时游戏状态更新
- 使用 React Query 的响应式 UI

### 国际化

- 中英文双语界面
- 基于 i18next 的翻译系统
- 语言自动检测

### 对局分析

赛后 AI 分析提供：

- 玩家表现评估
- 策略评估
- 关键时刻分析
- 改进建议

## 游戏角色

| 角色 | 阵营 | 能力 |
|------|------|------|
| 狼人 | 狼人阵营 | 每晚可击杀一名玩家 |
| 村民 | 好人阵营 | 无特殊能力，通过投票找出狼人 |
| 预言家 | 好人阵营 | 每晚可查验一名玩家身份 |
| 女巫 | 好人阵营 | 拥有一瓶解药和一瓶毒药 |
| 猎人 | 好人阵营 | 死亡时可开枪带走一名玩家 |

## 游戏流程

1. **角色分配** - 系统随机分配角色
2. **夜晚阶段** - 狼人击杀，神职行动
3. **白天阶段** - 发言讨论与投票
4. **胜负判定** - 一方阵营获胜时游戏结束

## 架构概览

```
前端 (React)        <-->    后端 (FastAPI)
     |                              |
     +-- WebSocket -----------------+
     |                              |
     +-- REST API ------------------+
                                    |
                              LLM Providers
```

详见 [系统架构](architecture.md)。
