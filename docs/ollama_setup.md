# Ollama 本地 LLM 配置指南

本项目的 `OpenAICompatibleProvider` 兼容任何 OpenAI API 格式的服务，包括本地运行的 [Ollama](https://ollama.com/)。

## 前置条件

1. 安装 [Ollama](https://ollama.com/download)
2. 拉取所需模型，例如：

```bash
ollama pull qwen2.5:7b    # 推荐：中文推理强，适合狼人杀
ollama pull llama3.1:8b   # 英文环境可选
```

3. 确认 Ollama 正在运行：

```bash
ollama serve   # 默认监听 http://localhost:11434
```

## 安全限制（SSRF 防护）

本项目的 `_validate_base_url` 默认**禁止**指向 localhost、127.0.0.1 及私有网络的 URL，以防止 SSRF 攻击。

### 解除限制

设置以下任一环境变量为 `true` 即可跳过验证：

- `OPENAI_ALLOW_LOCALHOST=true`
- `STITCH_ALLOW_LOCALHOST=true`（别名）

## 配置方式

### 方式一：环境变量（推荐）

```bash
# Bash / PowerShell
set OPENAI_ALLOW_LOCALHOST=true
set OPENAI_BASE_URL=http://localhost:11434/v1
set OPENAI_API_KEY=ollama          # Ollama 忽略 API Key，但必须设置
set OPENAI_MODEL=qwen2.5:7b

# 然后运行项目
python -m app.main
```

### 方式二：.env 文件

在项目根目录创建 `.env` 文件：

```
OPENAI_ALLOW_LOCALHOST=true
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen2.5:7b
```

## 验证配置

```bash
# 从项目目录运行测试
pytest tests/llm/test_openai_provider.py -v

# 确认以下测试通过：
# ✅ test_load_settings_accepts_localhost_when_env_var_set
# ✅ test_load_settings_rejects_localhost_without_env_var
```

## 注意事项

| 项目 | 说明 |
|------|------|
| **API Key** | Ollama 不校验密钥，但 `OPENAI_API_KEY` 必须设置（不可为空） |
| **Base URL** | 必须包含 `/v1` 路径后缀，如 `http://localhost:11434/v1` |
| **模型名** | 需与 `ollama list` 输出一致 |
| **安全** | 生产环境勿设置 `ALLOW_LOCALHOST=true`，仅在本地开发时使用 |
| **备用端口** | 如 Ollama 使用自定义端口（如 11435），对应修改即可 |
