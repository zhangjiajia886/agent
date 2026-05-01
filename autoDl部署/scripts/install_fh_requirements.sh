#!/bin/bash
# 安装 FlashHead requirements（torch 已装，跳过）
# 后台执行：nohup bash ~/install_fh_requirements.sh > ~/logs/install_fh_req.log 2>&1 &

set -e
LOG=~/logs/install_fh_req.log
mkdir -p ~/logs

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

source ~/miniconda3/etc/profile.d/conda.sh
ENV_FH=/root/autodl-tmp/envs/env-flashhead
conda activate "$ENV_FH"

log "========== FlashHead requirements 开始 =========="
log "Python: $(python --version 2>&1)"
log "mirror: https://pypi.tuna.tsinghua.edu.cn/simple"
log "requirements: ~/services/flashhead/requirements.txt"
log "磁盘(数据盘): $(df -h /root/autodl-tmp | awk 'NR==2{print $3"/"$2" "$5}')"

log "过滤冲突包: nvidia-nccl-cu12（torch 已装 2.26.2，排除 requirements.txt 中的版本约束）"
grep -v "nvidia-nccl-cu12" ~/services/flashhead/requirements.txt > /tmp/fh_req_filtered.txt
log "过滤后 requirements 行数: $(wc -l < /tmp/fh_req_filtered.txt)"

pip install -r /tmp/fh_req_filtered.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  --trusted-host pypi.tuna.tsinghua.edu.cn \
  --trusted-host download.pytorch.org \
  --ignore-installed torch torchvision torchaudio \
  --retries 20 \
  --timeout 60 \
  2>&1 | tee -a "$LOG"

RC=${PIPESTATUS[0]}
log "pip 返回码: $RC"

if [ $RC -ne 0 ]; then
  log "❌ FlashHead requirements 安装失败"
  exit $RC
fi

log "验证关键依赖"
python - <<'PY' 2>&1 | tee -a "$LOG"
import torch, gradio, transformers, diffusers
print('torch:', torch.__version__)
print('gradio:', gradio.__version__)
print('transformers:', transformers.__version__)
print('diffusers:', diffusers.__version__)
print('cuda:', torch.cuda.is_available())
PY

log "磁盘(数据盘): $(df -h /root/autodl-tmp | awk 'NR==2{print $3"/"$2" "$5}')"
log "========== FlashHead requirements 完成 =========="
