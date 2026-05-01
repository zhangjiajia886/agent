#!/bin/bash

# ============================================================
# TTS 语音平台 —— 启动 / 停止 / 重启 脚本
# 用法：./start.sh [start|stop|restart|status]
#   start   — 默认，启动全部服务
#   stop    — 停止前后端进程（Docker 容器保留）
#   restart — 先 stop 再 start
#   status  — 查看当前服务状态
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
NPM_REGISTRY="https://registry.npmmirror.com"

# Singer SSH 隧道配置（V100 实例，Singer Gradio 运行在远程 6006 → 本地 7862）
SINGER_TUNNEL_HOST="autodl-singer"
SINGER_TUNNEL_LOCAL_PORT=7862
SINGER_TUNNEL_REMOTE_PORT=6006

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[TTS]${NC} $1"; }
warn() { echo -e "${YELLOW}[TTS]${NC} $1"; }
err()  { echo -e "${RED}[TTS]${NC} $1"; }
info() { echo -e "${CYAN}[TTS]${NC} $1"; }

# ---------------------- 通用工具 ----------------------

port_in_use() {
  lsof -i :"$1" -sTCP:LISTEN -t > /dev/null 2>&1
}

find_free_port() {
  local primary=$1; shift
  local candidates=("$primary" "$@")
  for p in "${candidates[@]}"; do
    if ! port_in_use "$p"; then echo "$p"; return; fi
    warn "端口 $p 已被占用，尝试下一个..."
  done
  local rand_port=$(( RANDOM % 10000 + 20000 ))
  warn "所有候选端口均被占用，使用随机端口 $rand_port"
  echo "$rand_port"
}

# 检查本地 MySQL 是否可连接
check_mysql() {
  mysql -u root -h 127.0.0.1 -e "SELECT 1" > /dev/null 2>&1
}

# 检查本地 Redis 是否可连接
check_redis() {
  redis-cli ping > /dev/null 2>&1
}

# ---------------------- stop ----------------------

kill_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null)
  [ -z "$pids" ] && return
  kill -9 $pids 2>/dev/null
  local waited=0
  while port_in_use "$port" && [ $waited -lt 5 ]; do
    sleep 0.5; waited=$((waited+1))
  done
}

do_stop() {
  log "停止前后端进程..."
  pkill -9 -f "uvicorn app.main" 2>/dev/null
  pkill -9 -f "vite" 2>/dev/null
  # 强制释放端口（防止 TN/Stopped 进程残留）
  kill_port 8000
  kill_port 3000
  sleep 0.5
  for f in .backend.pid .frontend.pid .backend.port .frontend.port; do
    [ -f "$PROJECT_DIR/$f" ] && rm "$PROJECT_DIR/$f"
  done
  log "前后端服务已停止"

  # 关闭 Singer SSH 隧道（只杀 ssh 进程，不误杀其他服务）
  local tunnel_pid
  tunnel_pid=$(pgrep -f "ssh.*$SINGER_TUNNEL_LOCAL_PORT.*$SINGER_TUNNEL_HOST" 2>/dev/null | head -1)
  if [ -z "$tunnel_pid" ]; then
    tunnel_pid=$(pgrep -f "ssh.*-L.*$SINGER_TUNNEL_LOCAL_PORT" 2>/dev/null | head -1)
  fi
  if [ -n "$tunnel_pid" ]; then
    kill "$tunnel_pid" 2>/dev/null && log "Singer SSH 隧道已关闭 (PID=$tunnel_pid)"
  fi

  echo "  本地 MySQL/Redis 仍在运行（brew services 管理）"
}

# ---------------------- Singer SSH 隧道 ----------------------

start_singer_tunnel() {
  if port_in_use "$SINGER_TUNNEL_LOCAL_PORT"; then
    log "Singer SSH 隧道已在运行 (本地 127.0.0.1:$SINGER_TUNNEL_LOCAL_PORT)"
    return 0
  fi

  if ! grep -q "Host $SINGER_TUNNEL_HOST" ~/.ssh/config 2>/dev/null; then
    warn "SSH Host '$SINGER_TUNNEL_HOST' 未在 ~/.ssh/config 中配置，跳过 Singer 隧道"
    warn "Singer 服务将不可用，SVS/SVC/转写接口均无法使用"
    return 0
  fi

  log "建立 Singer SSH 隧道 ($SINGER_TUNNEL_HOST 远程:$SINGER_TUNNEL_REMOTE_PORT → 本地:$SINGER_TUNNEL_LOCAL_PORT)..."
  ssh -CNfg \
    -L "${SINGER_TUNNEL_LOCAL_PORT}":127.0.0.1:"${SINGER_TUNNEL_REMOTE_PORT}" \
    "$SINGER_TUNNEL_HOST" 2>/dev/null

  sleep 1
  if port_in_use "$SINGER_TUNNEL_LOCAL_PORT"; then
    log "Singer SSH 隧道已就绪 ✅ (127.0.0.1:$SINGER_TUNNEL_LOCAL_PORT)"
  else
    warn "Singer SSH 隧道建立失败 ⚠️  (检查 $SINGER_TUNNEL_HOST 是否可达)"
    warn "手动命令: ssh -CNg -L ${SINGER_TUNNEL_LOCAL_PORT}:127.0.0.1:${SINGER_TUNNEL_REMOTE_PORT} $SINGER_TUNNEL_HOST"
  fi
}

# ---------------------- start ----------------------

start_db() {
  log "检查本地 MySQL / Redis..."

  # MySQL
  if check_mysql; then
    log "MySQL 已在运行"
  else
    warn "MySQL 未运行，尝试 brew services start mysql..."
    brew services start mysql 2>/dev/null
    sleep 3
    if check_mysql; then
      log "MySQL 已启动"
    else
      err "MySQL 启动失败，请手动检查: brew services info mysql"
      exit 1
    fi
  fi

  # Redis
  if check_redis; then
    log "Redis 已在运行"
  else
    warn "Redis 未运行，尝试 brew services start redis..."
    brew services start redis 2>/dev/null
    sleep 1
    if check_redis; then
      log "Redis 已启动"
    else
      err "Redis 启动失败，请手动检查: brew services info redis"
      exit 1
    fi
  fi
}

start_backend() {
  BACKEND_PORT=$(find_free_port 8000 10001 10003 10005)
  log "启动后端服务 (port $BACKEND_PORT)..."
  cd "$PROJECT_DIR/backend"

  # —— Conda ttsapp 环境 & 依赖同步 ——
  eval "$(conda shell.bash hook)"
  if ! conda env list | grep -q "ttsapp"; then
    warn "conda ttsapp 环境不存在，创建中..."
    conda create -n ttsapp python=3.13 -y -c defaults --override-channels
  fi
  conda activate ttsapp

  local REQ_HASH
  REQ_HASH=$(md5 -q requirements.txt 2>/dev/null || md5sum requirements.txt | awk '{print $1}')
  local MARKER=".deps_hash"
  if [ ! -f "$MARKER" ] || [ "$(cat "$MARKER")" != "$REQ_HASH" ]; then
    log "同步 Python 依赖（requirements.txt 已变更）..."
    pip install -r requirements.txt --index-url "$PIP_INDEX" -q 2>/dev/null \
      || pip install -r requirements.txt -q
    pip install uvloop -q 2>/dev/null || true
    echo "$REQ_HASH" > "$MARKER"
  fi

  if [ ! -f ".env" ]; then
    warn ".env 不存在，从 .env.example 复制..."
    cp .env.example .env 2>/dev/null || warn ".env.example 也不存在，请手动创建 .env"
  fi

  mkdir -p logs uploads
  nohup python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$BACKEND_PORT" \
    --reload \
    > logs/backend.log 2>&1 &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > "$PROJECT_DIR/.backend.pid"
  echo "$BACKEND_PORT" > "$PROJECT_DIR/.backend.port"
  log "后端已启动 PID=$BACKEND_PID  port=$BACKEND_PORT  日志: backend/logs/backend.log"
  log "使用 conda 环境: $(which python)"
}

start_frontend() {
  FRONTEND_PORT=$(find_free_port 3000 10002 10004 10006)
  log "启动前端服务 (port $FRONTEND_PORT)..."
  cd "$PROJECT_DIR/frontend"

  if [ ! -d "node_modules" ]; then
    warn "安装前端依赖..."
    npm install --registry "$NPM_REGISTRY"
  fi

  BACKEND_PORT_VAL=$(cat "$PROJECT_DIR/.backend.port" 2>/dev/null || echo "8000")
  nohup env BACKEND_PORT="$BACKEND_PORT_VAL" FRONTEND_PORT="$FRONTEND_PORT" \
    npm run dev -- --port "$FRONTEND_PORT" \
    > "$PROJECT_DIR/frontend/frontend.log" 2>&1 &
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" > "$PROJECT_DIR/.frontend.pid"
  echo "$FRONTEND_PORT" > "$PROJECT_DIR/.frontend.port"
  log "前端已启动 PID=$FRONTEND_PID  port=$FRONTEND_PORT  日志: frontend/frontend.log"
}

wait_ready() {
  local bp fp
  bp=$(cat "$PROJECT_DIR/.backend.port" 2>/dev/null || echo "8000")
  fp=$(cat "$PROJECT_DIR/.frontend.port" 2>/dev/null || echo "3000")

  log "等待后端就绪..."
  BACKEND_OK=false
  for i in $(seq 1 15); do
    if curl -s "http://localhost:$bp/health" > /dev/null 2>&1; then
      BACKEND_OK=true; break
    fi
    sleep 1
  done

  echo ""
  echo "╔══════════════════════════════════════════╗"
  if $BACKEND_OK; then
    echo -e "║  ${GREEN}✅ 后端就绪${NC}  http://localhost:$bp"
    echo -e "║  ${GREEN}📖 API文档${NC}  http://localhost:$bp/docs"
  else
    echo -e "║  ${YELLOW}⚠️  后端启动中${NC} http://localhost:$bp/health"
  fi
  echo -e "║  ${GREEN}🌐 前端地址${NC}  http://localhost:$fp"
  if port_in_use "$SINGER_TUNNEL_LOCAL_PORT"; then
    echo -e "║  ${GREEN}🎵 Singer隧道${NC} 127.0.0.1:$SINGER_TUNNEL_LOCAL_PORT ✅"
  else
    echo -e "║  ${YELLOW}🎵 Singer隧道${NC} 未建立 ⚠️  (SVS/SVC 不可用)"
  fi
  echo "╚══════════════════════════════════════════╝"
  echo "  停止服务: ./start.sh stop"
  echo "  重启服务: ./start.sh restart"
  echo ""
}

do_start() {
  echo ""
  echo "╔══════════════════════════════════════╗"
  echo "║        TTS 语音平台 启动中            ║"
  echo "╚══════════════════════════════════════╝"
  echo ""

  # 先停止旧进程
  pkill -9 -f "uvicorn app.main" 2>/dev/null
  pkill -9 -f "vite" 2>/dev/null
  kill_port 8000
  kill_port 3000
  log "已停止旧进程"

  start_db
  start_singer_tunnel
  start_backend
  start_frontend
  wait_ready
}

# ---------------------- status ----------------------

do_status() {
  echo ""
  info "===== TTS 语音平台 服务状态 ====="

  local bp fp
  bp=$(cat "$PROJECT_DIR/.backend.port" 2>/dev/null || echo "?")
  fp=$(cat "$PROJECT_DIR/.frontend.port" 2>/dev/null || echo "?")

  if pgrep -f "uvicorn app.main" > /dev/null 2>&1; then
    log "后端:  运行中  port=$bp  PID=$(pgrep -f 'uvicorn app.main' | head -1)"
  else
    err "后端:  未运行"
  fi

  if pgrep -f "vite" > /dev/null 2>&1; then
    log "前端:  运行中  port=$fp  PID=$(pgrep -f 'vite' | head -1)"
  else
    err "前端:  未运行"
  fi

  if check_mysql; then
    log "MySQL: 运行中 (本地)"
  else
    err "MySQL: 未运行"
  fi

  if check_redis; then
    log "Redis: 运行中 (本地)"
  else
    err "Redis: 未运行"
  fi

  if port_in_use "$SINGER_TUNNEL_LOCAL_PORT"; then
    log "Singer 隧道: 运行中 ✅ (127.0.0.1:$SINGER_TUNNEL_LOCAL_PORT → $SINGER_TUNNEL_HOST:$SINGER_TUNNEL_REMOTE_PORT)"
  else
    warn "Singer 隧道: 未建立 ⚠️  (Singer SVS/SVC 不可用)"
  fi
  echo ""
}

# ---------------------- 入口 ----------------------

ACTION="${1:-start}"

case "$ACTION" in
  start)
    do_start
    ;;
  stop)
    do_stop
    ;;
  restart)
    echo ""
    info "===== 重启 TTS 语音平台 ====="
    do_stop
    sleep 1
    do_start
    ;;
  status)
    do_status
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
