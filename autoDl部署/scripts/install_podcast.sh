#!/bin/bash
# 安装 SoulX-Podcast 环境（torch 2.7.1）
# 后台执行：nohup bash ~/install_podcast.sh > ~/logs/install_podcast.log 2>&1 &

set -e
LOG=~/logs/install_podcast.log
mkdir -p ~/logs

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

source ~/miniconda3/etc/profile.d/conda.sh
ENV_PC=/root/autodl-tmp/envs/env-podcast

log "========== Podcast 环境安装开始 =========="
log "磁盘(数据盘): $(df -h /root/autodl-tmp | awk 'NR==2{print $3"/"$2" "$5}')"

[ -d "$ENV_PC" ] || conda create --prefix "$ENV_PC" python=3.10 -y
conda activate "$ENV_PC"
log "Python: $(python --version 2>&1)"

log "安装 torch 2.7.1+cu128（镜像）"
pip install torch==2.7.1 torchaudio==2.7.1 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  --trusted-host pypi.tuna.tsinghua.edu.cn \
  --trusted-host download.pytorch.org \
  --retries 20 \
  --timeout 60 \
  2>&1 | tee -a "$LOG"

log "安装 Podcast requirements"
pip install -r ~/services/podcast/requirements.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  --trusted-host pypi.tuna.tsinghua.edu.cn \
  --trusted-host download.pytorch.org \
  --ignore-installed torch torchaudio \
  --retries 20 \
  --timeout 60 \
  2>&1 | tee -a "$LOG"

RC=${PIPESTATUS[0]}
log "pip 返回码: $RC"
[ $RC -ne 0 ] && log "❌ Podcast requirements 安装失败" && exit $RC

log "验证"
python - <<'PY' 2>&1 | tee -a "$LOG"
import torch, gradio
print('torch:', torch.__version__)
print('gradio:', gradio.__version__)
print('cuda:', torch.cuda.is_available())
PY

log "磁盘(数据盘): $(df -h /root/autodl-tmp | awk 'NR==2{print $3"/"$2" "$5}')"
log "========== Podcast 环境安装完成 =========="
