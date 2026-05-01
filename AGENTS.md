# AGENTS.md — Werewolf (AI 狼人杀单机文字版)

> 项目级 Codex 指令。完整设计上下文请参阅根目录 `.impeccable.md`。

## Project Overview

基于 FastAPI + WebSocket + React 的单机 AI 狼人杀（9 人局：1 真人 + 8 AI）。前端位于 `frontend/`，后端位于 `backend/`，协议详见 `docs/技术.md`。

## Design Context

> 本节与 `.impeccable.md` 保持一致，二处任一更新另一处需同步。

### Users

- 主受众：想玩狼人杀但懒得等人/组局的 solo 玩家（18–35 岁，有狼人杀基础）
- 使用场景：一人独处（午休/睡前/通勤），10–20 分钟单局
- 反模式受众：完全不懂规则的纯新手需 onboarding 兜底；硬核开黑不是第一目标

### Brand Personality

**墨色 · 克制 · 松动**

- **墨色** — 东方水墨/活字印刷的含蓄色谱，非饱和油画
- **克制** — 装饰极少，留白极大，每元素必须能解释"为什么在这里"
- **松动** — 不死板的极简，允许纸张纤维、印章位移等"不完美的温度"

目标情绪：安静专注（入场）→ 克制紧张（推理）→ 分量感（关键决策）→ 留白收尾（终局）

反情绪：激情澎湃、可爱萌、SaaS 工具感、赛博霓虹

### Aesthetic Direction

**基底参考**：Notion / Obsidian 极简文稿排版 × 东方水墨桌游剧本

- **Light 主题**：宣纸白 + 松烟墨 + 朱砂印 + 琥珀金
- **Dark 主题**（日夜切换）：泼墨深蓝 + 月白 + 朱砂（提亮）+ 灯笼金
- **字体**：Source Han Serif SC（标题）+ Source Han Sans SC（正文）+ 霞鹜文楷（特色）
- **布局**：单焦点、桌面为中心（环形/拱形座位）、文稿式聊天流、装饰仅保留印章/墨渍/纸纹

色彩 token 使用 OKLCH（详见 `.impeccable.md` 和未来的 `frontend/src/styles/tokens.css`）。

### Design Principles

1. **墨胜于色** — 用墨色浓淡建立层级，强调色 ≤ 10%，禁止引入第三种强调色
2. **留白即信息** — 屏幕留白 ≥ 40%，靠字号/字重/缩进/行距分区，不靠卡片边框
3. **文人不喊叫** — 删除 eyebrow caps、装饰性英文大字、代码常量泄漏；kicker 用中文低调分节
4. **仪式是张力来源** — destructive 二段确认、死亡揭示仪式动画、日夜切换过渡、终局卷轴收束
5. **新手能懂，老手不烦** — 首次触发时自动说明规则（如"女巫只能救一次"），老手默认折叠

## Frontend Conventions

- 前端技术栈：React 18 + TypeScript + Vite + 纯 CSS（无 tailwind、无 UI 库）
- 组件位置：`frontend/src/components/`
- 样式：`frontend/src/styles.css`（目标：拆为 `styles/tokens.css` + 若干模块）
- 测试：Vitest + @testing-library/react
- **所有前端 UI 改动必须先读 `.impeccable.md` 的 Design Context 与 Design Principles**
- **任何 CSS 值不得硬编码**：颜色走 `--color-*` 令牌、间距走 `--space-*`、半径走 `--radius-*`、阴影走 `--shadow-*`、字重字号走 `--font-*`
- 文案规范：所有 action_type 在 UI 层走 `actionTypeCopy` 映射表，不可直接 `.replace(/_/g, " ")`

## Backend Conventions

- Python 3.11+ · FastAPI · WebSocket
- 协议文档详见 `docs/技术.md`、`docs/状态机架构.md`
- **不改不提**：`docs/werewolf_project.csv`、`docs/需求.md`、`docs/技术.md`、`docs/状态机架构.md`、`docs/补充.md`

## Workflow

- 前端美化工作流遵循 Impeccable 12 步序列：teach → normalize → distill → clarify → harden → onboard → arrange → typeset → animate → delight → optimize → polish
- 每阶段结束后重跑 `/ccg:audit` 或 `/ccg:critique` 校验分数
