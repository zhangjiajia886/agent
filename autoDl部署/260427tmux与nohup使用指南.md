# tmux 与 nohup 使用指南

> 适用场景：SSH 远程连接云服务器执行长时间任务（模型下载、服务启动、训练等）

---

## 一、为什么需要会话管理？

**直接执行命令的问题**：

```
本地电脑 ──SSH连接──▶ 云服务器 Shell ──▶ 运行 python xxx.py
                                         ↓
                          笔记本合盖 / 网络断开
                                         ↓
                         SSH 断开 → SIGHUP 信号 → 进程终止
```

SSH 断开时，终端会向所有前台子进程发送 **SIGHUP**（挂断信号），进程默认行为是立即终止。下载到一半的模型、跑到一半的训练——全部丢失。

解决思路：让进程脱离 SSH 终端的生命周期。有两种方案：

| 方案 | 原理 | 适合场景 |
|---|---|---|
| `nohup &` | 忽略 SIGHUP，后台运行 | 一次性任务，不需要交互 |
| `tmux` | 独立服务器端会话，SSH 只是"接入" | 长期服务、多窗口、需要随时查看输出 |

---

## 二、nohup &

### 原理

`nohup`（No Hang Up）命令让进程**忽略 SIGHUP 信号**，配合 `&` 放入后台运行。

```bash
nohup python download.py &
```

进程会继续运行，但你和它"失联"了——输出默认写入 `nohup.out`。

### 常用写法

```bash
# 基础用法，输出写入 nohup.out
nohup python download.py &

# 推荐：将 stdout 和 stderr 都写入指定日志文件
nohup python download.py > ~/logs/download.log 2>&1 &

# 查看进程是否在运行
ps aux | grep download.py

# 查看日志（实时滚动）
tail -f ~/logs/download.log

# 终止进程
kill <PID>
# 或一行找到并终止
kill $(pgrep -f download.py)
```

### 优缺点

| ✅ 优点 | ❌ 缺点 |
|---|---|
| 简单，一行命令 | 断线后只能看日志，无法重新"接入" |
| 无需提前安装 | 多个任务时难以管理 |
| 进程真正独立运行 | 无交互能力（无法输入命令）|

---

## 三、tmux（推荐）

### 什么是 tmux？

tmux 是服务器端的**会话管理器**。它在服务器上维护独立的终端会话，SSH 连接只是"接入"这个会话查看。SSH 断开后，会话继续在服务器运行，重新 SSH 后可以 `attach` 恢复查看。

```
服务器端（持久存在）：
┌─────────────────────────────────────────┐
│  tmux server                            │
│  ├── session: download                  │
│  │     └── window 0: python download.py │ ← 进程一直在跑
│  └── session: services                  │
│        ├── window 0: FlashHead          │
│        └── window 1: Podcast            │
└─────────────────────────────────────────┘
              ▲
          SSH attach（可随时连接/断开）
```

### 核心概念

- **Session（会话）**：一个独立的工作空间，可以包含多个窗口
- **Window（窗口）**：类似浏览器标签，每个窗口有一个终端
- **Pane（面板）**：窗口内的分屏区域

### 快捷键前缀

tmux 所有快捷键都以 `Ctrl+b` 开头（先按 `Ctrl+b`，松开，再按后续键）。

---

### 常用命令速查

#### 会话管理（在普通 Shell 里执行）

```bash
# 创建新会话（前台，交互式）
tmux new-session -s download

# 创建新会话（后台，适合脚本）
tmux new-session -d -s download

# 查看所有会话
tmux list-sessions        # 或 tmux ls

# 接入会话（恢复查看）
tmux attach -t download   # 或 tmux a -t download

# 删除会话
tmux kill-session -t download

# 删除所有会话
tmux kill-server
```

#### 在 tmux 会话内的快捷键

| 快捷键 | 功能 |
|---|---|
| `Ctrl+b d` | **Detach（脱离会话）**，会话继续运行，返回普通 Shell |
| `Ctrl+b c` | 新建窗口 |
| `Ctrl+b n` | 切换到下一个窗口 |
| `Ctrl+b p` | 切换到上一个窗口 |
| `Ctrl+b 0~9` | 切换到第 N 个窗口 |
| `Ctrl+b ,` | 重命名当前窗口 |
| `Ctrl+b %` | 左右分屏 |
| `Ctrl+b "` | 上下分屏 |
| `Ctrl+b 方向键` | 切换面板 |
| `Ctrl+b [` | 进入滚动模式（可上下翻看历史输出，`q` 退出）|
| `Ctrl+b &` | 关闭当前窗口 |

#### 在脚本中控制 tmux（非交互场景）

```bash
# 在已有会话中执行命令（C-m 相当于 Enter）
tmux send-keys -t download "python download.py" C-m

# 在新窗口执行命令
tmux new-window -t services -n flashhead
tmux send-keys -t services:flashhead "conda activate env-flashhead && python app.py" C-m
```

---

### 完整部署示例

```bash
# ── 步骤 1：创建一个管理所有服务的会话 ──
tmux new-session -d -s main

# ── 步骤 2：在会话里创建各窗口 ──
tmux new-window -t main -n download    # 窗口：模型下载
tmux new-window -t main -n flashhead  # 窗口：FlashHead 服务
tmux new-window -t main -n podcast    # 窗口：Podcast 服务

# ── 步骤 3：在各窗口执行命令 ──
tmux send-keys -t main:download \
  "HF_ENDPOINT=https://hf-mirror.com huggingface-cli download SoulAI/FlashHead --local-dir ~/autodl-tmp/models/FlashHead 2>&1 | tee ~/logs/dl.log" C-m

tmux send-keys -t main:flashhead \
  "conda activate /root/autodl-tmp/envs/env-flashhead && GRADIO_SERVER_PORT=6006 python gradio_app.py 2>&1 | tee ~/logs/flashhead.log" C-m

# ── 步骤 4：接入会话查看 ──
tmux attach -t main
# 按 Ctrl+b n 切换窗口
# 按 Ctrl+b d 脱离，SSH 可以断开了

# ── 步骤 5：下次 SSH 重连后恢复 ──
tmux attach -t main
```

---

### tmux 中 conda 激活失败的解决

新建 tmux 窗口/会话后，有时 `conda activate xxx` 报错，因为 tmux 没有加载 `.bashrc`。

```bash
# 方法 1：在每条命令前 source conda 初始化
source /root/miniconda3/etc/profile.d/conda.sh && conda activate env-flashhead

# 方法 2：在 tmux 配置里加入（~/.tmux.conf）
set-option -g default-command "bash --login"

# 方法 3：直接用绝对路径调用 python
/root/autodl-tmp/envs/env-flashhead/bin/python gradio_app.py
```

---

## 四、选择建议

```
需要随时重新接入查看输出？  → tmux ✅
一次性后台任务（下载/训练）？ → nohup 或 tmux 均可
多个服务同时管理？           → tmux（多窗口）✅
脚本自动化，无人值守？       → nohup（简单）或 tmux（可监控）
```

**实际部署推荐：全程用 tmux**，一个 session 管理所有服务，可以随时 attach 查看任意窗口的实时日志，远比 `tail -f` 多个日志文件方便。
