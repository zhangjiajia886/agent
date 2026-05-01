#!/bin/bash
# D03机 环境安装脚本：env-flashhead → env-podcast（串行）
# 后台执行已在 tmux install session 中完成，日志见 ~/logs/

set -e
LOG=~/logs/install_envs_d03.log
mkdir -p ~/logs

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

source ~/miniconda3/etc/profile.d/conda.sh

ENV_FH=/root/autodl-tmp/envs/env-flashhead
ENV_PC=/root/autodl-tmp/envs/env-podcast

log "========== Phase 2: env-flashhead =========="
log "创建 conda 环境 → $ENV_FH"
[ -d "$ENV_FH" ] || conda create --prefix "$ENV_FH" python=3.10 -y
conda activate "$ENV_FH"
log "Python: $(python --version 2>&1)"

log "安装 torch 2.7.1+cu128（清华镜像）"
pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  --trusted-host pypi.tuna.tsinghua.edu.cn \
  --trusted-host download.pytorch.org \
  --retries 20 --timeout 60 \
  2>&1 | tee -a "$LOG"

log "过滤 nvidia-nccl-cu12 冲突后安装 FlashHead requirements"
grep -v "nvidia-nccl-cu12" ~/services/flashhead/requirements.txt > /tmp/fh_req_filtered.txt
pip install -r /tmp/fh_req_filtered.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  --trusted-host pypi.tuna.tsinghua.edu.cn \
  --trusted-host download.pytorch.org \
  --ignore-installed torch torchvision torchaudio \
  --retries 20 --timeout 60 \
  2>&1 | tee -a "$LOG"

log "验证 env-flashhead"
python -c "import torch, gradio; print('torch:', torch.__version__, 'CUDA:', torch.cuda.is_available(), 'gradio:', gradio.__version__)" 2>&1 | tee -a "$LOG"
log "========== Phase 2 完成 =========="

log "========== Phase 3: env-podcast =========="
log "磁盘状态: $(df -h /root/autodl-tmp | awk 'NR==2{print $3"/"$2" "$5}')"
bash ~/install_podcast.sh 2>&1 | tee -a "$LOG"
log "========== Phase 3 完成 =========="

log "========== 创建 FlashHead 软链接 =========="
ln -sf ~/models ~/services/flashhead/models && log "软链接已建: ~/services/flashhead/models → ~/models"

log "========== 全部安装完成，可执行 bash ~/start_all.sh =========="
