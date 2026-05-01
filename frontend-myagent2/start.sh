#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── 颜色 ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}[agent-flow] 前端启动脚本${NC}"

# ── 1. 检查 node ──
if ! command -v node &>/dev/null; then
  echo -e "${YELLOW}未检测到 node，请先安装 Node.js >= 18${NC}"
  exit 1
fi

NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VER" -lt 18 ]; then
  echo -e "${YELLOW}Node.js 版本过低 ($(node -v))，需要 >= 18${NC}"
  exit 1
fi

echo -e "  Node $(node -v)  npm $(npm -v)"

# ── 2. 安装依赖 ──
if [ ! -d "node_modules" ] || [ ! -d "node_modules/.vite" -a ! -d "node_modules/vite" ]; then
  echo -e "${GREEN}[1/2] 安装依赖...${NC}"
  npm install
else
  echo -e "${GREEN}[1/2] 依赖已就绪，跳过 npm install${NC}"
fi

# ── 3. 启动开发服务器 ──
BACKEND_PORT="${BACKEND_PORT:-8000}"
PORT="${PORT:-5173}"

echo -e "${GREEN}[2/2] 启动 Vite 开发服务器 (port ${PORT})...${NC}"
echo -e "  后端代理: /api -> http://localhost:${BACKEND_PORT}"
echo -e "  WebSocket: /ws  -> ws://localhost:${BACKEND_PORT}"
echo ""

VITE_BACKEND_PORT="${BACKEND_PORT}" npx vite --host --port "${PORT}"
