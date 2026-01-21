/**
 * Environment Variables Table
 * Displays list of environment variables with segmented view (Pending/Configured)
 */

import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Edit, Trash2, Eye, EyeOff, AlertTriangle } from 'lucide-react';
import { EnvVariable } from '@/types/config';

// 环境变量名到中文描述的映射
const ENV_VAR_LABELS: Record<string, string> = {
  // 核心配置
  JWT_SECRET_KEY: 'JWT 密钥',
  OPENAI_API_KEY: 'OpenAI API 密钥',
  OPENAI_BASE_URL: 'OpenAI API 地址',

  // LLM 模型配置
  LLM_MODEL: '默认 LLM 模型',
  LLM_MAX_RETRIES: 'API 最大重试次数',
  LLM_USE_MOCK: '模拟模式开关',

  // 应用配置
  DEBUG: '调试模式',
  LOG_LEVEL: '日志级别',
  DATA_DIR: '数据存储目录',

  // 管理功能配置
  ENV_MANAGEMENT_ENABLED: '环境变量管理开关',

  // 安全配置
  ADMIN_PASSWORD: '管理员密码',
  ADMIN_KEY: '管理员密钥',
  ADMIN_KEY_ENABLED: '管理密钥开关',
  DEBUG_MODE: '调试接口开关',
  TRUSTED_PROXIES: '可信代理列表',
  CORS_ORIGINS: 'CORS 允许来源',

  // JWT 认证配置
  JWT_ALGORITHM: 'JWT 签名算法',
  JWT_EXPIRE_MINUTES: 'JWT 过期时间',

  // OAuth SSO (linux.do)
  LINUXDO_CLIENT_ID: 'LinuxDo 客户端 ID',
  LINUXDO_CLIENT_SECRET: 'LinuxDo 客户端密钥',
  LINUXDO_REDIRECT_URI: 'LinuxDo 回调 URL',
  LINUXDO_AUTHORIZE_URL: 'LinuxDo 授权 URL',
  LINUXDO_TOKEN_URL: 'LinuxDo 令牌 URL',
  LINUXDO_USERINFO_URL: 'LinuxDo 用户信息 URL',
  LINUXDO_SCOPES: 'LinuxDo 授权范围',

  // AI 游戏分析配置
  ANALYSIS_PROVIDER: '分析服务商',
  ANALYSIS_MODEL: '分析模型',
  ANALYSIS_MODE: '分析模式',
  ANALYSIS_LANGUAGE: '分析语言',
  ANALYSIS_CACHE_ENABLED: '分析缓存开关',
  ANALYSIS_MAX_TOKENS: '分析最大令牌数',
  ANALYSIS_TEMPERATURE: '分析温度参数',

  // 多服务商配置 - DeepSeek
  DEEPSEEK_API_KEY: 'DeepSeek API 密钥',
  DEEPSEEK_BASE_URL: 'DeepSeek API 地址',
  DEEPSEEK_MODEL: 'DeepSeek 模型',
  DEEPSEEK_MAX_RETRIES: 'DeepSeek 重试次数',
  DEEPSEEK_TEMPERATURE: 'DeepSeek 温度',
  DEEPSEEK_MAX_TOKENS: 'DeepSeek 最大令牌',

  // 多服务商配置 - Anthropic
  ANTHROPIC_API_KEY: 'Anthropic API 密钥',
  ANTHROPIC_BASE_URL: 'Anthropic API 地址',
  ANTHROPIC_MODEL: 'Anthropic 模型',
  ANTHROPIC_MAX_RETRIES: 'Anthropic 重试次数',
  ANTHROPIC_TEMPERATURE: 'Anthropic 温度',
  ANTHROPIC_MAX_TOKENS: 'Anthropic 最大令牌',

  // 多服务商配置 - Moonshot
  MOONSHOT_API_KEY: '月之暗面 API 密钥',
  MOONSHOT_BASE_URL: '月之暗面 API 地址',
  MOONSHOT_MODEL: '月之暗面模型',
  MOONSHOT_MAX_RETRIES: '月之暗面重试次数',
  MOONSHOT_TEMPERATURE: '月之暗面温度',
  MOONSHOT_MAX_TOKENS: '月之暗面最大令牌',

  // 多服务商配置 - Qwen
  QWEN_API_KEY: '通义千问 API 密钥',
  QWEN_BASE_URL: '通义千问 API 地址',
  QWEN_MODEL: '通义千问模型',
  QWEN_MAX_RETRIES: '通义千问重试次数',
  QWEN_TEMPERATURE: '通义千问温度',
  QWEN_MAX_TOKENS: '通义千问最大令牌',

  // 多服务商配置 - GLM
  GLM_API_KEY: '智谱 API 密钥',
  GLM_BASE_URL: '智谱 API 地址',
  GLM_MODEL: '智谱模型',
  GLM_MAX_RETRIES: '智谱重试次数',
  GLM_TEMPERATURE: '智谱温度',
  GLM_MAX_TOKENS: '智谱最大令牌',

  // 多服务商配置 - Doubao
  DOUBAO_API_KEY: '豆包 API 密钥',
  DOUBAO_BASE_URL: '豆包 API 地址',
  DOUBAO_MODEL: '豆包模型',
  DOUBAO_MAX_RETRIES: '豆包重试次数',
  DOUBAO_TEMPERATURE: '豆包温度',
  DOUBAO_MAX_TOKENS: '豆包最大令牌',

  // 多服务商配置 - MiniMax
  MINIMAX_API_KEY: 'MiniMax API 密钥',
  MINIMAX_BASE_URL: 'MiniMax API 地址',
  MINIMAX_MODEL: 'MiniMax 模型',
  MINIMAX_MAX_RETRIES: 'MiniMax 重试次数',
  MINIMAX_TEMPERATURE: 'MiniMax 温度',
  MINIMAX_MAX_TOKENS: 'MiniMax 最大令牌',

  // 速率限制配置
  DEFAULT_REQUESTS_PER_MINUTE: '默认每分钟请求数',
  DEFAULT_MAX_CONCURRENCY: '默认最大并发数',
  DEFAULT_BURST: '默认突发请求数',
  LLM_MAX_WAIT_SECONDS: 'LLM 最大等待秒数',
  LLM_PER_GAME_MIN_INTERVAL: '单局最小请求间隔',
  LLM_PER_GAME_MAX_CONCURRENCY: '单局最大并发数',

  // Redis 配置
  REDIS_URL: 'Redis 连接 URL',

  // 前端配置
  VITE_API_URL: '后端 API 地址',
  VITE_API_BASE_URL: '后端 API 基础地址',
  VITE_SENTRY_DSN: 'Sentry DSN',
  VITE_SENTRY_ENV: 'Sentry 环境',
  VITE_SENTRY_TRACES_SAMPLE_RATE: 'Sentry 追踪采样率',
  VITE_SENTRY_ENABLE_REPLAY: 'Sentry 回放开关',
  VITE_SENTRY_REPLAYS_SESSION_SAMPLE_RATE: 'Sentry 回放采样率',
  VITE_SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE: 'Sentry 错误回放采样率',

  // 数据库配置
  RUN_DB_MIGRATIONS: '启动时运行迁移',
};

// 获取变量的中文标签
const getVarLabel = (name: string): string => {
  // 直接匹配
  if (ENV_VAR_LABELS[name]) {
    return ENV_VAR_LABELS[name];
  }

  // 自定义服务商匹配 (AI_PROVIDER_1_xxx)
  const customProviderMatch = name.match(/^AI_PROVIDER_(\d+)_(.+)$/);
  if (customProviderMatch) {
    const [, num, suffix] = customProviderMatch;
    const suffixLabels: Record<string, string> = {
      NAME: '名称',
      API_KEY: 'API 密钥',
      BASE_URL: 'API 地址',
      MODEL: '模型',
      MAX_RETRIES: '重试次数',
      TEMPERATURE: '温度',
      MAX_TOKENS: '最大令牌',
    };
    return `自定义服务商 ${num} ${suffixLabels[suffix] || suffix}`;
  }

  // 玩家专属 AI 配置匹配 (AI_PLAYER_2_xxx)
  const playerMatch = name.match(/^AI_PLAYER_(\d+)_(.+)$/);
  if (playerMatch) {
    const [, seat, suffix] = playerMatch;
    const suffixLabels: Record<string, string> = {
      PROVIDER: '服务商',
      API_KEY: 'API 密钥',
      BASE_URL: 'API 地址',
      MODEL: '模型',
      TEMPERATURE: '温度',
      MAX_TOKENS: '最大令牌',
      MAX_RETRIES: '重试次数',
    };
    return `玩家 ${seat} ${suffixLabels[suffix] || suffix}`;
  }

  // AI_PLAYER_MAPPING 特殊处理
  if (name === 'AI_PLAYER_MAPPING') {
    return '玩家服务商映射';
  }

  return '';
};

interface EnvVariablesTableProps {
  variables: EnvVariable[];
  onEdit: (variable: EnvVariable) => void;
  onDelete: (variable: EnvVariable) => void;
}

export function EnvVariablesTable({ variables, onEdit, onDelete }: EnvVariablesTableProps) {
  const [visibleValues, setVisibleValues] = useState<Set<string>>(new Set());

  const toggleVisibility = (name: string) => {
    setVisibleValues(prev => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  // Split variables into pending and configured
  const pendingVars = variables.filter(v => !v.is_set && v.is_required);
  const configuredVars = variables.filter(v => v.is_set);

  if (variables.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No environment variables found. Click "Add Variable" to create one.
      </div>
    );
  }

  const renderRow = (variable: EnvVariable, isPending: boolean) => {
    const isVisible = visibleValues.has(variable.name);
    const showValue = variable.is_sensitive ? (isVisible ? variable.value || '(empty)' : '********') : variable.value || '(empty)';
    const label = getVarLabel(variable.name);

    return (
      <TableRow key={variable.name}>
        <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
          {label || '-'}
        </TableCell>
        <TableCell className="font-mono font-semibold">
          <div className="flex items-center gap-2">
            {variable.name}
            {isPending && (
              <Badge variant="destructive" className="h-5 text-[10px]">
                Missing
              </Badge>
            )}
            {variable.is_sensitive && (
              <Badge variant="secondary" className="text-xs">
                Sensitive
              </Badge>
            )}
            {!isPending && variable.is_required && (
              <Badge variant="outline" className="text-xs">
                Required
              </Badge>
            )}
          </div>
        </TableCell>
        <TableCell>
          {isPending ? (
            <span className="italic text-muted-foreground text-sm">Required in .env.example</span>
          ) : (
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm truncate max-w-md">
                {showValue}
              </span>
              {variable.is_sensitive && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleVisibility(variable.name)}
                  className="h-6 w-6 p-0"
                >
                  {isVisible ? (
                    <EyeOff className="h-3 w-3" />
                  ) : (
                    <Eye className="h-3 w-3" />
                  )}
                </Button>
              )}
            </div>
          )}
        </TableCell>
        <TableCell className="text-right">
          <div className="flex items-center justify-end gap-2">
            {isPending ? (
              <Button
                size="sm"
                onClick={() => onEdit(variable)}
              >
                Configure
              </Button>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onEdit(variable)}
                  disabled={!variable.is_editable}
                  title={!variable.is_editable ? 'This variable cannot be edited via UI' : ''}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDelete(variable)}
                  disabled={!variable.is_editable}
                  title={!variable.is_editable ? 'This variable cannot be deleted via UI' : ''}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </>
            )}
          </div>
        </TableCell>
      </TableRow>
    );
  };

  return (
    <div className="border rounded-md overflow-hidden">
      <Table>
        {/* Pending Configuration Section */}
        {pendingVars.length > 0 && (
          <>
            <TableHeader className="bg-yellow-50 dark:bg-yellow-950/30">
              <TableRow>
                <TableHead colSpan={4} className="text-yellow-700 dark:text-yellow-400 font-bold">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    Pending Configuration ({pendingVars.length})
                  </div>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableHeader className="bg-yellow-50/50 dark:bg-yellow-950/10">
              <TableRow>
                <TableHead>描述</TableHead>
                <TableHead>Variable Name</TableHead>
                <TableHead>Value</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="bg-yellow-50/30 dark:bg-yellow-950/10">
              {pendingVars.map((variable) => renderRow(variable, true))}
            </TableBody>
          </>
        )}

        {/* Active Variables Section */}
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead colSpan={4} className="font-semibold">
              ✅ Active Variables
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableHeader>
          <TableRow>
            <TableHead>描述</TableHead>
            <TableHead>Variable Name</TableHead>
            <TableHead>Value</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {configuredVars.length > 0 ? (
            configuredVars.map((variable) => renderRow(variable, false))
          ) : (
            <TableRow>
              <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                No configured variables. Configure the required variables above to get started.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
