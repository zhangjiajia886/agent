#!/bin/bash
# D03机 / RTX 5090 启动脚本
# 服务：FlashHead（6006）+ Podcast（6008）
# Singer 在单独 V100 实例，此脚本不包含
# 执行：bash ~/start_all.sh
# 查看：tmux attach -t soul

source ~/miniconda3/etc/profile.d/conda.sh

ENV_FH=/root/autodl-tmp/envs/env-flashhead
ENV_PC=/root/autodl-tmp/envs/env-podcast

SESSION="soul"
mkdir -p ~/logs

echo "停止旧 tmux session（如有）..."
tmux kill-session -t $SESSION 2>/dev/null || true
sleep 1

echo "启动 tmux session: $SESSION"
tmux new-session -d -s $SESSION -x 220 -y 50

# ── FlashHead（端口 6006）
tmux rename-window -t $SESSION:0 'flashhead'
tmux send-keys -t $SESSION:0 "source ~/miniconda3/etc/profile.d/conda.sh && conda activate $ENV_FH && cd ~/services/flashhead && echo '[FH] 启动 FlashHead on 6006...' && GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=6006 python gradio_app.py 2>&1 | tee ~/logs/flashhead.log" C-m
sleep 2

# ── Podcast（端口 6008）
tmux new-window -t $SESSION -n 'podcast'
tmux send-keys -t $SESSION:1 "source ~/miniconda3/etc/profile.d/conda.sh && conda activate $ENV_PC && cd ~/services/podcast && echo '[PC] 启动 Podcast on 6008...' && python run_api.py --model ~/models/SoulX-Podcast --port 6008 --host 0.0.0.0 2>&1 | tee ~/logs/podcast.log" C-m

echo ""
echo "=== 服务已启动 ==="
echo "查看面板  : tmux attach -t soul"
echo "FlashHead : https://u982127-9c41-df2246bb.westd.seetacloud.com:8443"
echo "Podcast   : https://uu982127-9c41-df2246bb.westd.seetacloud.com:8443"
echo ""
echo "查看日志  :"
echo "  tail -f ~/logs/flashhead.log"
echo "  tail -f ~/logs/podcast.log"
