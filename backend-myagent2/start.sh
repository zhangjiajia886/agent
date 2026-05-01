#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}[agent-flow] 后端启动脚本${NC}"

# ── 1. 激活 conda 环境 ──
CONDA_ENV="${CONDA_ENV:-puwang-agent}"

# 初始化 conda（确保 conda activate 可用）
if [ -f "/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh" ]; then
  source /opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
fi

conda activate "$CONDA_ENV" 2>/dev/null
if [ $? -ne 0 ]; then
  echo -e "${YELLOW}无法激活 conda 环境 ${CONDA_ENV}，请先创建: conda create -n ${CONDA_ENV} python=3.11${NC}"
  exit 1
fi

PY_VER=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  Conda env: ${CONDA_ENV}  Python $PY_VER"

# ── 2. 检查依赖 ──
if ! python -c "import fastapi" 2>/dev/null; then
  echo -e "${GREEN}[1/2] 安装依赖...${NC}"
  pip install -r requirements.txt -q
else
  echo -e "${GREEN}[1/2] 依赖已就绪${NC}"
fi

# ── 3. 启动 FastAPI ──
PORT="${PORT:-8000}"

echo -e "${GREEN}[3/3] 启动 FastAPI (port ${PORT})...${NC}"
echo -e "  API docs: http://localhost:${PORT}/docs"
echo -e "  Health:   http://localhost:${PORT}/api/health"
echo ""

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --reload
