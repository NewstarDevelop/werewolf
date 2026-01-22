# 速率限制监控告警建议

本文档提供针对速率限制安全修复的监控和告警建议。

## 📊 关键监控指标

### 1. LoginRateLimiter 内存使用监控

**监控目标**: 防止内存泄漏导致的 OOM

**指标**:
- `login_rate_limiter_records_count`: 当前记录数量
- `login_rate_limiter_cleanup_count`: 每次清理的记录数

**实现示例**:
```python
# 在 login_rate_limiter.py 中添加
def get_metrics(self) -> dict:
    """Get metrics for monitoring."""
    with self._lock:
        return {
            "records_count": len(self._records),
            "lockout_count": len(self._lockout_counts),
            "oldest_record_age": self._get_oldest_record_age(),
        }

def _get_oldest_record_age(self) -> float:
    """Get age of oldest record in seconds."""
    if not self._records:
        return 0.0
    now = time.time()
    oldest = min(r.last_attempt_at for r in self._records.values() if r.last_attempt_at > 0)
    return now - oldest if oldest > 0 else 0.0
```

**告警规则**:
```yaml
# Prometheus 告警规则示例
- alert: LoginRateLimiterMemoryLeak
  expr: login_rate_limiter_records_count > 10000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Login rate limiter 记录数过多"
    description: "当前记录数: {{ $value }}，可能存在内存泄漏"

- alert: LoginRateLimiterCleanupFailed
  expr: rate(login_rate_limiter_cleanup_count[1h]) == 0
  for: 2h
  labels:
    severity: warning
  annotations:
    summary: "Login rate limiter 清理任务未运行"
    description: "过去 2 小时内没有清理记录"
```

---

### 2. XFF 伪造攻击检测

**监控目标**: 检测 X-Forwarded-For 伪造尝试

**日志模式监控**:
```python
# 在 client_ip.py 中已添加的日志
logger.warning(f"Suspicious XFF chain length: {len(ips)} hops")
logger.warning(f"Invalid IP in X-Forwarded-For chain: '{ip}'")
logger.warning(f"XFF chain mismatch: rightmost IP '{rightmost_ip}' != peer IP '{peer_ip}'")
```

**告警规则**:
```yaml
# 基于日志的告警（使用 Loki/ELK）
- alert: XFFSpoofingAttempt
  expr: |
    sum(rate({job="werewolf-backend"} |= "Suspicious XFF chain length"[5m])) > 10
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "检测到 XFF 伪造攻击"
    description: "过去 5 分钟内有 {{ $value }} 次可疑 XFF 链"

- alert: XFFChainMismatch
  expr: |
    sum(rate({job="werewolf-backend"} |= "XFF chain mismatch"[5m])) > 5
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "XFF 链不一致"
    description: "可能的代理配置错误或攻击尝试"
```

---

### 3. 速率限制器性能监控

**监控目标**: 确保速率限制器正常工作

**指标**:
- `rate_limiter_timeout_count`: 速率限制超时次数
- `rate_limiter_wait_time_seconds`: 等待时间分布
- `rate_limiter_active_games`: 活跃游戏数量

**实现示例**:
```python
# 在 rate_limiter.py 中添加
class PerGameSoftLimiter:
    def get_metrics(self) -> dict:
        """Get metrics for monitoring."""
        return {
            "active_games": len(self._semaphores),
            "tracked_games": len(self._last_call),
        }
```

**告警规则**:
```yaml
- alert: RateLimiterHighTimeout
  expr: rate(rate_limiter_timeout_count[5m]) > 10
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "速率限制器超时频繁"
    description: "可能需要调整 RPM 或并发限制"

- alert: RateLimiterMemoryGrowth
  expr: rate_limiter_active_games > 1000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "活跃游戏数过多"
    description: "可能存在游戏清理问题"
```

---

### 4. LLM 服务并发监控

**监控目标**: 检测并发竞态和限流效果

**指标**:
- `llm_limiter_created_count`: 动态创建的 limiter 数量
- `llm_concurrent_requests`: 当前并发请求数
- `llm_rate_limit_hits`: 触发速率限制的次数

**告警规则**:
```yaml
- alert: LLMLimiterDuplicateCreation
  expr: increase(llm_limiter_created_count{provider="same_provider"}[5m]) > 1
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "检测到 limiter 重复创建"
    description: "可能存在并发竞态问题"

- alert: LLMRateLimitExceeded
  expr: rate(llm_rate_limit_hits[5m]) > 50
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "LLM 速率限制频繁触发"
    description: "可能需要增加 RPM 配额或优化请求频率"
```

---

## 🔍 日志监控建议

### 关键日志模式

**1. 安全相关日志**:
```bash
# 监控这些日志模式
grep "Suspicious XFF chain length" /var/log/werewolf/backend.log
grep "Invalid IP in X-Forwarded-For" /var/log/werewolf/backend.log
grep "XFF chain mismatch" /var/log/werewolf/backend.log
grep "Login attempt blocked" /var/log/werewolf/backend.log
grep "locked out for" /var/log/werewolf/backend.log
```

**2. 性能相关日志**:
```bash
# 监控速率限制器等待时间
grep "Rate limiter waiting" /var/log/werewolf/backend.log
grep "Per-game limiter waiting" /var/log/werewolf/backend.log
grep "Timed out waiting for" /var/log/werewolf/backend.log
```

**3. 清理任务日志**:
```bash
# 监控清理任务执行
grep "Rate limiter cleanup" /var/log/werewolf/backend.log
grep "Cleaned up.*rate limit records" /var/log/werewolf/backend.log
grep "Cleaned up rate limiter resources for game" /var/log/werewolf/backend.log
```

---

## 📈 Grafana 仪表板建议

### 仪表板布局

**Panel 1: 速率限制器健康状态**
- 当前记录数（LoginRateLimiter）
- 活跃游戏数（PerGameSoftLimiter）
- 清理任务执行频率

**Panel 2: 安全事件**
- XFF 伪造尝试次数（时间序列）
- 登录锁定事件（时间序列）
- 可疑 IP 列表（表格）

**Panel 3: 性能指标**
- 速率限制等待时间分布（直方图）
- 超时事件频率
- LLM 并发请求数

**Panel 4: 内存使用**
- LoginRateLimiter 记录数趋势
- PerGameSoftLimiter 游戏数趋势
- 清理效果（清理前后对比）

---

## 🚨 告警通知配置

### 告警级别定义

**Critical (紧急)**:
- XFF 伪造攻击（> 10 次/5分钟）
- Limiter 重复创建（并发竞态）
- 内存泄漏（记录数 > 50000）

**Warning (警告)**:
- 记录数持续增长（> 10000）
- 清理任务未运行（> 2 小时）
- 速率限制频繁触发

**Info (信息)**:
- 清理任务执行成功
- 游戏资源正常清理

### 通知渠道建议

```yaml
# Alertmanager 配置示例
route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
  - match:
      severity: critical
    receiver: 'pagerduty'
  - match:
      severity: warning
    receiver: 'slack'

receivers:
- name: 'pagerduty'
  pagerduty_configs:
  - service_key: '<your-key>'

- name: 'slack'
  slack_configs:
  - api_url: '<your-webhook>'
    channel: '#werewolf-alerts'
```

---

## 🔧 运维建议

### 日常检查清单

**每日**:
- [ ] 检查 LoginRateLimiter 记录数是否正常（< 1000）
- [ ] 检查是否有 XFF 伪造告警
- [ ] 检查清理任务是否正常运行

**每周**:
- [ ] 分析速率限制触发模式
- [ ] 检查是否需要调整 RPM 配额
- [ ] 审查可疑 IP 列表

**每月**:
- [ ] 审查告警规则有效性
- [ ] 优化速率限制参数
- [ ] 更新监控仪表板

### 故障排查指南

**问题 1: 内存持续增长**
```bash
# 1. 检查记录数
curl http://localhost:8082/admin/metrics | grep login_rate_limiter

# 2. 检查清理任务日志
grep "Rate limiter cleanup" /var/log/werewolf/backend.log | tail -20

# 3. 手动触发清理（如果需要）
# 通过管理面板或 API 调用 cleanup_expired()
```

**问题 2: XFF 告警频繁**
```bash
# 1. 检查代理配置
echo $TRUSTED_PROXIES
echo $MAX_PROXY_HOPS

# 2. 分析 XFF 模式
grep "XFF:" /var/log/werewolf/backend.log | tail -50

# 3. 验证代理是否正确剥离外部 XFF
# 检查 nginx/CDN 配置
```

**问题 3: 速率限制失效**
```bash
# 1. 检查 limiter 创建日志
grep "Dynamically created rate limiter" /var/log/werewolf/backend.log

# 2. 检查是否有重复创建
grep "rate limiter for.*:" /var/log/werewolf/backend.log | sort | uniq -c

# 3. 重启服务以重置状态（如果必要）
docker compose restart backend
```

---

## 📝 指标导出实现

### Prometheus 指标导出示例

```python
# backend/app/api/endpoints/metrics.py
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi import APIRouter, Response

router = APIRouter()

# 定义指标
login_records_gauge = Gauge('login_rate_limiter_records', 'Number of login rate limit records')
xff_spoofing_counter = Counter('xff_spoofing_attempts', 'XFF spoofing attempts detected')
rate_limit_timeout_counter = Counter('rate_limiter_timeouts', 'Rate limiter timeout events')
rate_limit_wait_histogram = Histogram('rate_limiter_wait_seconds', 'Rate limiter wait time')

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from app.services.login_rate_limiter import admin_login_limiter, user_login_limiter

    # 更新指标
    admin_count = len(admin_login_limiter._records)
    user_count = len(user_login_limiter._records)
    login_records_gauge.set(admin_count + user_count)

    return Response(content=generate_latest(), media_type="text/plain")
```

---

## 🎯 总结

实施以上监控和告警机制可以：

1. **及早发现问题**: 在内存泄漏或攻击造成严重影响前发出告警
2. **快速定位根因**: 通过详细的日志和指标快速诊断问题
3. **持续优化**: 基于监控数据优化速率限制参数
4. **安全防护**: 实时检测和响应安全威胁

建议优先实施 Critical 级别的告警，然后逐步完善其他监控指标。
