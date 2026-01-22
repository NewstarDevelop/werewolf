#!/bin/bash
# Werewolf AI 部署脚本
# 用法: ./deploy.sh [start|stop|restart|logs|status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查并创建数据目录，设置正确权限
ensure_data_dir() {
    DATA_DIR="./data"
    REQUIRED_UID=1000

    if [ ! -d "$DATA_DIR" ]; then
        log_info "创建数据目录: $DATA_DIR"
        mkdir -p "$DATA_DIR"
    fi

    # 检查目录所有者
    if [ "$(uname)" = "Linux" ]; then
        CURRENT_UID=$(stat -c '%u' "$DATA_DIR" 2>/dev/null || echo "unknown")
        if [ "$CURRENT_UID" != "$REQUIRED_UID" ]; then
            log_warn "数据目录权限需要修复 (当前 UID: $CURRENT_UID, 需要: $REQUIRED_UID)"
            log_info "执行: sudo chown -R $REQUIRED_UID:$REQUIRED_UID $DATA_DIR"
            sudo chown -R "$REQUIRED_UID:$REQUIRED_UID" "$DATA_DIR" || {
                log_error "权限修复失败，请手动执行: sudo chown -R $REQUIRED_UID:$REQUIRED_UID $DATA_DIR"
                exit 1
            }
            log_info "权限修复完成"
        fi
    elif [ "$(uname)" = "Darwin" ]; then
        # macOS: Docker Desktop 通常不需要特殊权限处理
        log_info "macOS 环境，跳过权限检查"
    fi
}

# 检查 .env 文件
check_env() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            log_warn ".env 文件不存在，从 .env.example 复制"
            cp .env.example .env
            log_warn "请编辑 .env 文件配置必要的环境变量后重新运行"
            exit 1
        else
            log_error ".env 和 .env.example 都不存在"
            exit 1
        fi
    fi
}

# 启动服务
start() {
    log_info "Werewolf AI 启动中..."
    check_env
    ensure_data_dir

    docker compose up -d --build

    log_info "等待服务健康检查..."
    sleep 5

    if docker compose ps | grep -q "unhealthy"; then
        log_error "服务健康检查失败，查看日志: ./deploy.sh logs"
        docker compose ps
        exit 1
    fi

    log_info "服务已启动"
    echo ""
    echo "访问地址:"
    echo "  - 前端: http://localhost:8081"
    echo "  - API:  http://localhost:8082"
    echo "  - 文档: http://localhost:8082/docs"
}

# 停止服务
stop() {
    log_info "停止服务..."
    docker compose down
    log_info "服务已停止"
}

# 重启服务
restart() {
    stop
    start
}

# 查看日志
logs() {
    docker compose logs -f --tail=100 "$@"
}

# 查看状态
status() {
    docker compose ps
}

# 主入口
case "${1:-start}" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    logs)    shift; logs "$@" ;;
    status)  status ;;
    *)
        echo "用法: $0 [start|stop|restart|logs|status]"
        echo ""
        echo "命令:"
        echo "  start   - 启动所有服务（默认）"
        echo "  stop    - 停止所有服务"
        echo "  restart - 重启所有服务"
        echo "  logs    - 查看日志（可指定服务名，如: logs backend）"
        echo "  status  - 查看服务状态"
        exit 1
        ;;
esac
