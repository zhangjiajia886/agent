#!/bin/bash
# D03机 三模型并行下载脚本
# 执行：bash ~/download_models_d03.sh
# 查看：tmux attach -t download

mkdir -p ~/logs /root/autodl-tmp/models /root/autodl-tmp/envs

source ~/miniconda3/etc/profile.d/conda.sh
conda activate base

SESSION="download"
tmux kill-session -t $SESSION 2>/dev/null || true
sleep 1
tmux new-session -d -s $SESSION -x 220 -y 50

# ── Window 0: FlashHead-1_3B (~14GB)
tmux rename-window -t $SESSION:0 'flashhead'
tmux send-keys -t $SESSION:0 \
  "export HF_ENDPOINT=https://hf-mirror.com && \
   source ~/miniconda3/etc/profile.d/conda.sh && conda activate base && \
   echo '[FH] 开始下载 SoulX-FlashHead-1_3B...' && \
   hf download Soul-AILab/SoulX-FlashHead-1_3B --local-dir ~/models/SoulX-FlashHead-1_3B 2>&1 | tee ~/logs/dl_flashhead.log && \
   echo '[FH] ✅ 下载完成'" C-m

# ── Window 1: wav2vec2-base-960h (~1.1GB)
tmux new-window -t $SESSION -n 'wav2vec'
tmux send-keys -t $SESSION:1 \
  "export HF_ENDPOINT=https://hf-mirror.com && \
   source ~/miniconda3/etc/profile.d/conda.sh && conda activate base && \
   echo '[W2V] 开始下载 wav2vec2-base-960h...' && \
   hf download facebook/wav2vec2-base-960h --local-dir ~/models/wav2vec2-base-960h 2>&1 | tee ~/logs/dl_wav2vec.log && \
   echo '[W2V] ✅ 下载完成'" C-m

# ── Window 2: SoulX-Podcast-1.7B (~5.4GB)
tmux new-window -t $SESSION -n 'podcast'
tmux send-keys -t $SESSION:2 \
  "export HF_ENDPOINT=https://hf-mirror.com && \
   source ~/miniconda3/etc/profile.d/conda.sh && conda activate base && \
   echo '[PC] 开始下载 SoulX-Podcast-1.7B...' && \
   hf download Soul-AILab/SoulX-Podcast-1.7B --local-dir ~/models/SoulX-Podcast 2>&1 | tee ~/logs/dl_podcast.log && \
   echo '[PC] ✅ 下载完成'" C-m

echo ""
echo "=== 三个模型正在并行下载 ==="
echo "查看进度 : tmux attach -t download"
echo ""
echo "查看各模型日志:"
echo "  tail -f ~/logs/dl_flashhead.log"
echo "  tail -f ~/logs/dl_wav2vec.log"
echo "  tail -f ~/logs/dl_podcast.log"
echo ""
echo "查看已下载大小:"
echo "  du -sh ~/models/*/"
