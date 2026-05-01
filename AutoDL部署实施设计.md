# Soul 数字人专题 — AutoDL RTX 5090 部署实施设计

> 更新时间：2026 年 4 月 25 日  
> 基于：`soul专题数字人调研.md` + `算力租赁平台研究.md`  
> 决策：**AutoDL + RTX 5090 (32GB) + 按量计费**

---

## 一、部署目标

### 1.1 要部署的模型

| 模型 | 功能 | 常驻显存 (FP16) | 推理峰值 | 优先级 |
|------|------|----------------|---------|--------|
| **SoulX-FlashHead** | 实时数字人（音频驱动口型） | Lite: **6.4 GB** | ~7 GB | **P0 必部署** |
| **SoulX-Podcast** | 播客/TTS 多人语音合成 | **~6 GB**（Qwen3-1.7B 基座） | ~8 GB | **P0 必部署** |
| **SoulX-Singer** | 零样本歌声合成 + 歌声转换 | **~8 GB** | ~10 GB | **P0 必部署** |
| **SoulX-LiveAct** | 小时级长时数字人 | ~30 GB (FP8) | ~32 GB | P1 暂不装（独占整卡） |
| **SoulX-FlashTalk** | 旗舰级 14B 数字人 | 64 GB+ | — | ❌ 超出上限 |

### ⭐ 一张卡够不够？

```
RTX 5090 总显存:                         32 GB
─────────────────────────────────────────────
FlashHead Lite 常驻:          6.4 GB
Podcast 常驻:                 6   GB
Singer 常驻:                  8   GB
─────────────────────────────────────────────
三服务同时加载合计:           ≈ 20.4 GB
推理峰值合计（不会同时推理）:  ≈ 25 GB
剩余显存:                     ≈ 7~12 GB ✅ 富余
```

> **结论：一张 RTX 5090 同时运行三个模型，完全够用。**  
> 三个模型不会同时推理（用户一次只用一个功能），实际峰值不超过 25GB。  
> 全部装进一个镜像，开机一键启动，无需按需切换。

### 1.2 部署目的

```
当前状态：ttsapp 后端 → Gradio Client → HuggingFace Spaces（免费但排队、冷启动慢、不稳定）
目标状态：ttsapp 后端 → Gradio Client → AutoDL 上的自建 Gradio 服务（独占 GPU、无排队、秒级响应）
```

### 1.3 核心收益

| 痛点 | 现状 (HF Spaces) | 目标 (AutoDL 自部署) |
|------|-------------------|---------------------|
| **排队等待** | 高峰期排队 1~5 分钟 | 独占实例，零等待 |
| **冷启动** | Space 休眠后首次 1~2 分钟 | 模型常驻内存，秒级响应 |
| **TLS 超时** | 偶发 SSL handshake timeout | 国内网络，无跨境问题 |
| **生成速度** | ZeroGPU 共享，受限 | RTX 5090 独占，FlashHead Lite 96FPS |
| **稳定性** | Space 可能下线/限流 | 完全自控 |
| **费用** | 免费但不可控 | ≈ ¥3/hr，关机停费 |

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────┐
│  用户本地 / 公司服务器                                  │
│                                                       │
│  ┌─────────────┐    ┌──────────────────────────────┐  │
│  │  前端 Vue3   │───▶│  后端 FastAPI (:8000)         │  │
│  │  :5173       │    │                              │  │
│  └─────────────┘    │  ┌─ flashhead_client.py ─┐   │  │
│                      │  │ GradioSpaceClient     │   │  │
│                      │  │ space_id / server_url │──────────┐
│                      │  └───────────────────────┘   │  │   │
│                      │  ┌─ podcast_client.py ───┐   │  │   │
│                      │  │ GradioSpaceClient     │──────────┤
│                      │  └───────────────────────┘   │  │   │
│                      │  ┌─ singer_client.py ────┐   │  │   │
│                      │  │ GradioSpaceClient     │──────────┤
│                      │  └───────────────────────┘   │  │   │
│                      └──────────────────────────────┘  │   │
│                                                       │   │
│  ┌── docker-compose ──────────────────────────────┐  │   │
│  │ MySQL │ Redis │ ES │ Milvus                     │  │   │
│  └─────────────────────────────────────────────────┘  │   │
└─────────────────────────────────────────────────────┘   │
                                                           │
              ─ ─ ─ ─ ─ ─ ─ 公网 SSH 隧道 / Gradio URL ─ ─│─ ─
                                                           │
┌─────────────────────────────────────────────────────┐   │
│  AutoDL 实例 — RTX 5090 (32GB)                       │   │
│                                                       │   │
│  ┌─────────────────────────────────────────────────┐  │   │
│  │  Conda 环境: soul                                │  │   │
│  │                                                   │  │   │
│  │  ~/models/                                        │  │   │
│  │    ├── SoulX-FlashHead-1_3B/   (~2.6GB)          │  │   │
│  │    ├── wav2vec2-base-960h/     (~360MB)           │  │   │
│  │    ├── SoulX-Podcast/          (~3.4GB)           │  │   │
│  │    ├── SoulX-Singer/           (~4GB)             │  │   │
│  │    └── chinese-wav2vec2-base/  (~360MB)           │  │   │
│  │                                                   │  │   │
│  │  ~/services/                                      │  │   │
│  │    ├── flashhead_server.py    (:7860) ◀───────────┼──┼───┘
│  │    ├── podcast_server.py      (:7861) ◀───────────┼──┘
│  │    └── singer_server.py       (:7862) ◀───────────┘
│  │                                                   │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 2.2 连接方式选择

| 方案 | 说明 | 优缺点 |
|------|------|--------|
| **方案 A: Gradio Public URL** | AutoDL 上启动 Gradio 时设置 `share=True`，生成公网 URL | ✅ 零配置 / ❌ URL 72h 过期需重启 |
| **方案 B: AutoDL 端口映射** | 使用 AutoDL 自带的「自定义服务」端口映射 | ✅ 稳定长期可用 / ✅ 推荐 |
| **方案 C: SSH 隧道** | `ssh -L 7860:localhost:7860 root@autodl-ip` | ✅ 安全 / ❌ 需保持 SSH 连接 |

> **推荐方案 B** — AutoDL 支持将实例端口映射到公网域名，无需额外操作。

### 2.3 后端代码改造点

当前代码通过 `GradioSpaceClient` 连接 HuggingFace Spaces，**只需改配置即可切换到 AutoDL 实例**：

```python
# 当前 config.py（连接 HuggingFace）
SOUL_FLASHHEAD_SPACE = "Soul-AILab/SoulX-FlashHead"
SOUL_SINGER_SPACE    = "Soul-AILab/SoulX-Singer"
SOUL_PODCAST_SPACE   = "Soul-AILab/SoulX-Podcast-1.7B"

# 改为 AutoDL Gradio 地址（方案 B 端口映射后的地址）
SOUL_FLASHHEAD_SPACE = "http://<autodl-mapped-domain>:7860"
SOUL_SINGER_SPACE    = "http://<autodl-mapped-domain>:7862"
SOUL_PODCAST_SPACE   = "http://<autodl-mapped-domain>:7861"
```

`gradio_client.Client()` 构造函数**原生支持传入 URL**（不仅限于 Space ID），所以现有的 `GradioSpaceClient` 代码**完全不用改**，只需修改 `.env` 配置。

---

## 三、AutoDL 实例配置

### 3.1 选择实例

| 配置项 | 推荐值 |
|--------|--------|
| **GPU** | RTX 5090 (32GB) × 1 |
| **镜像** | PyTorch 2.7 + CUDA 12.8 + Ubuntu 22.04 |
| **系统盘** | 30GB（默认免费） |
| **数据盘** | 50GB（存放模型权重，≈ 11GB 总计 + 余量） |
| **价格** | ≈ ¥2.98 ~ 3.50 / 小时 |

### 3.2 模型存储空间估算

| 模型 | 大小 | 存储位置 |
|------|------|---------|
| SoulX-FlashHead-1_3B | ~2.6 GB | ~/models/ |
| wav2vec2-base-960h | ~360 MB | ~/models/ |
| SoulX-Podcast (含 dialect) | ~3.4 GB | ~/models/ |
| SoulX-Singer (含 SVC) | ~4 GB | ~/models/ |
| chinese-wav2vec2-base | ~360 MB | ~/models/ |
| Conda 环境 + 依赖 | ~8 GB | 系统盘 |
| **合计** | **~19 GB** | |

> 50GB 数据盘足够，且 AutoDL 关机后数据盘内容**永久保留**。

---

## 四、逐步实施流程

### Phase 0：注册与充值（5 分钟）

```bash
# 1. 注册 AutoDL 账号
#    https://www.autodl.com/register

# 2. 充值 100 元（够用 30+ 小时 RTX 5090）
#    支付宝/微信均可
```

### Phase 1：创建实例与基础环境（15 分钟）

```bash
# ────────────────────────────────────────
# AutoDL 控制台操作
# ────────────────────────────────────────
# 1. 「容器实例」→「创建实例」
# 2. 选择地区（推荐北京/上海/内蒙，延迟低）
# 3. 选择 GPU: RTX 5090 (32GB) × 1
# 4. 选择镜像: PyTorch → 2.7.0 → CUDA 12.8 → Python 3.10
# 5. 数据盘: 50GB
# 6. 创建并等待启动

# ────────────────────────────────────────
# SSH 登录后执行
# ────────────────────────────────────────
# AutoDL 实例默认已装好 conda、PyTorch、CUDA

# 确认 GPU 可用
nvidia-smi

# 创建工作目录
mkdir -p ~/models ~/services ~/logs
```

### Phase 2：下载模型权重（20~30 分钟）

```bash
# AutoDL 到 HuggingFace 下载速度通常 50~100MB/s
# 如果较慢，可用 AutoDL 内置的学术加速（设置 HF 镜像）

# 设置 HuggingFace 镜像加速（AutoDL 内置）
export HF_ENDPOINT=https://hf-mirror.com

# ── FlashHead 模型 ──
huggingface-cli download Soul-AILab/SoulX-FlashHead-1_3B \
  --local-dir ~/models/SoulX-FlashHead-1_3B

huggingface-cli download facebook/wav2vec2-base-960h \
  --local-dir ~/models/wav2vec2-base-960h

# ── Podcast 模型 ──
huggingface-cli download Soul-AILab/SoulX-Podcast-1.7B \
  --local-dir ~/models/SoulX-Podcast

# ── Singer 模型 ──
huggingface-cli download Soul-AILab/SoulX-Singer \
  --local-dir ~/models/SoulX-Singer

# ── LiveAct 可选 ──
# huggingface-cli download Soul-AILab/LiveAct \
#   --local-dir ~/models/LiveAct
# huggingface-cli download TencentGameMate/chinese-wav2vec2-base \
#   --local-dir ~/models/chinese-wav2vec2-base
```

### Phase 3：安装依赖（15~20 分钟）

```bash
# 创建统一 conda 环境
conda create -n soul python=3.10 -y
conda activate soul

# PyTorch（AutoDL 镜像通常已预装，确认版本）
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128

# FlashAttention（数字人推理加速核心）
pip install flash_attn==2.8.0.post2 --no-build-isolation

# SageAttention（可选，进一步加速）
pip install sageattention==2.2.0 --no-build-isolation

# Gradio（用于暴露 API 服务）
pip install gradio>=4.0.0

# ── FlashHead 依赖 ──
cd /tmp && git clone https://github.com/Soul-AILab/SoulX-FlashHead.git
cd SoulX-FlashHead && pip install -r requirements.txt
cp -r /tmp/SoulX-FlashHead ~/services/flashhead

# ── Podcast 依赖 ──
cd /tmp && git clone https://github.com/Soul-AILab/SoulX-Podcast.git
cd SoulX-Podcast && pip install -r requirements.txt
cp -r /tmp/SoulX-Podcast ~/services/podcast

# ── Singer 依赖 ──
cd /tmp && git clone https://github.com/Soul-AILab/SoulX-Singer.git
cd SoulX-Singer && pip install -r requirements.txt
cp -r /tmp/SoulX-Singer ~/services/singer

# 安装 ffmpeg（FlashHead HLS→MP4 转换需要）
apt-get update && apt-get install -y ffmpeg
```

### Phase 4：启动 Gradio 服务（10 分钟）

三个模型分别以 Gradio 服务形式运行，占用不同端口：

```bash
# ── 终端 1: FlashHead (:7860) ──
conda activate soul
cd ~/services/flashhead
python gradio_app_streaming.py \
  --ckpt_dir ~/models/SoulX-FlashHead-1_3B \
  --wav2vec_dir ~/models/wav2vec2-base-960h \
  --server_port 7860 \
  --server_name 0.0.0.0
# 常驻显存: Lite ~6.4GB

# ── 终端 2: Podcast (:7861) ──
conda activate soul
cd ~/services/podcast
python gradio_app.py \
  --model_dir ~/models/SoulX-Podcast \
  --server_port 7861 \
  --server_name 0.0.0.0
# 常驻显存: ~6GB

# ── 终端 3: Singer (:7862) ──
conda activate soul
cd ~/services/singer
python gradio_app.py \
  --model_dir ~/models/SoulX-Singer \
  --server_port 7862 \
  --server_name 0.0.0.0
# 常驻显存: ~8GB
```

> **显存分配**：三个服务同时常驻约 20.4GB，推理峰值约 25GB，RTX 5090 (32GB) 余量充足。  
> 全部一键启动，无需手动切换。

#### 使用 tmux 管理多服务（推荐）

```bash
# 安装 tmux
apt-get install -y tmux

# 创建启动脚本
cat > ~/start_all.sh << 'EOF'
#!/bin/bash
# Soul 数字人服务一键启动脚本

SESSION="soul"
tmux new-session -d -s $SESSION

# FlashHead
tmux rename-window -t $SESSION:0 'flashhead'
tmux send-keys -t $SESSION:0 'conda activate soul && cd ~/services/flashhead && python gradio_app_streaming.py --ckpt_dir ~/models/SoulX-FlashHead-1_3B --wav2vec_dir ~/models/wav2vec2-base-960h --server_port 7860 --server_name 0.0.0.0 2>&1 | tee ~/logs/flashhead.log' C-m

# Podcast
tmux new-window -t $SESSION -n 'podcast'
tmux send-keys -t $SESSION:1 'conda activate soul && cd ~/services/podcast && python gradio_app.py --model_dir ~/models/SoulX-Podcast --server_port 7861 --server_name 0.0.0.0 2>&1 | tee ~/logs/podcast.log' C-m

# Singer
tmux new-window -t $SESSION -n 'singer'
tmux send-keys -t $SESSION:2 'conda activate soul && cd ~/services/singer && python gradio_app.py --model_dir ~/models/SoulX-Singer --server_port 7862 --server_name 0.0.0.0 2>&1 | tee ~/logs/singer.log' C-m

echo "所有服务已启动，使用 tmux attach -t soul 查看"
EOF
chmod +x ~/start_all.sh
```

### Phase 5：配置 AutoDL 端口映射

```
AutoDL 控制台 → 实例详情 → 「自定义服务」

添加以下端口映射：
  端口 7860 → FlashHead Gradio
  端口 7861 → Podcast Gradio
  端口 7862 → Singer Gradio

映射后会生成公网访问地址，格式类似：
  https://u-xxxxx-7860.westb.seetacloud.com
  https://u-xxxxx-7861.westb.seetacloud.com
  https://u-xxxxx-7862.westb.seetacloud.com
```

### Phase 6：修改 ttsapp 后端配置

```bash
# 编辑 ttsapp/backend/.env
# 将 HuggingFace Space ID 替换为 AutoDL Gradio URL

# ── 之前 ──
SOUL_FLASHHEAD_SPACE=Soul-AILab/SoulX-FlashHead
SOUL_SINGER_SPACE=Soul-AILab/SoulX-Singer
SOUL_PODCAST_SPACE=Soul-AILab/SoulX-Podcast-1.7B

# ── 改为 ──
SOUL_FLASHHEAD_SPACE=https://u-xxxxx-7860.westb.seetacloud.com
SOUL_SINGER_SPACE=https://u-xxxxx-7862.westb.seetacloud.com
SOUL_PODCAST_SPACE=https://u-xxxxx-7861.westb.seetacloud.com

# HF_TOKEN 不再需要（本地推理无需鉴权）
SOUL_HF_TOKEN=
```

> **关键：现有代码 `GradioSpaceClient` 的 `Client()` 构造函数原生支持传入 URL，无需改任何 Python 代码。**

### Phase 7：验证联通性

```bash
# 在本地测试 Gradio 服务是否可达
python -c "
from gradio_client import Client
c = Client('https://u-xxxxx-7860.westb.seetacloud.com')
print(c.view_api())  # 能看到 API 列表即成功
"

# 启动 ttsapp 后端，测试数字人生成
cd ~/home/learn26/ttsapp && bash start.sh
```

### Phase 8：保存镜像（关键！）

```
AutoDL 控制台 → 实例详情 → 「保存镜像」

镜像命名建议：soul-digital-human-v1
包含内容（全量打包，一个不落）：
  ✅ conda 环境 (soul) + 全部 pip 依赖
  ✅ FlashHead 模型权重 + 服务代码
  ✅ Podcast 模型权重 + 服务代码
  ✅ Singer 模型权重 + 服务代码
  ✅ wav2vec2 辅助模型
  ✅ 一键启动脚本 ~/start_all.sh
  ✅ ffmpeg 等系统工具

保存后的体验：
  1. AutoDL 控制台点「开机」（30 秒）
  2. SSH 登录，执行 ~/start_all.sh
  3. 三个服务 60 秒内全部就绪
  4. 无需下载任何东西，环境完整可用

存储说明：
  - 模型权重 ~11GB + 环境 ~8GB + 代码 ~1GB ≈ 20GB
  - AutoDL 镜像 30GB 以下免费存储 ✅
```

---

## 五、显存分配策略

### 5.1 默认模式：三服务常驻（一键启动）

```
RTX 5090 32GB 显存分配（三服务全部常驻）：
┌──────────────────────────────────────────────────────────────┐
│  FlashHead Lite   │   Podcast      │   Singer      │ 空闲   │
│  6.4 GB           │   6 GB         │   8 GB        │ ~12 GB │
└──────────────────────────────────────────────────────────────┘
常驻总计: ≈ 20.4 GB    剩余: ≈ 11.6 GB
推理峰值: ≈ 25 GB      剩余: ≈ 7 GB     ← 用户一次只调一个模型
```

> **三个服务始终全部运行，无需手动切换。**  
> 用户通过前端选择不同功能时，对应模型执行推理，其他模型保持空闲但常驻显存。

### 5.2 FlashHead Pro 模式（特殊场景）

| 模式 | 帧率 @5090 | 显存 | 画质 | 能否共存 |
|------|-----------|------|------|----------|
| **Lite** | ~96+ FPS | 6.4 GB | 较好 | ✅ 三服务同时运行 |
| **Pro** | ~16.8 FPS | ~20 GB | 最佳 | ⚠️ 需停 Singer（20+6+8=34>32） |

> 日常用 Lite 即可。如需 Pro 高画质，运行 `~/switch_to_pro.sh` 自动停 Singer 并切换。

---

## 六、日常使用流程

### 6.1 开机流程（每次实验前，约 2 分钟，全自动）

```
1. AutoDL 控制台 → 选择实例 → 「开机」（约 30 秒）
2. SSH 登录（或用 JupyterLab 终端）
3. 执行一条命令：~/start_all.sh
4. 三个服务自动启动、模型自动加载到 GPU（约 60 秒）
5. 开始使用 — FlashHead / Podcast / Singer 全部可用

无需手动选择启动哪个模型，全部常驻，随用随调。
```

### 6.2 关机流程（实验结束后）

```
1. tmux attach -t soul → 确认没有正在运行的任务
2. AutoDL 控制台 → 「关机」
3. ✅ 关机后立即停止计费
4. ✅ 数据盘内容保留（模型、代码、环境全在）
5. ✅ 保存的镜像永久有效
```

### 6.3 HuggingFace 回退方案

如果 AutoDL 实例关机或不可用，可随时切回 HuggingFace Spaces：

```bash
# backend/.env 改回 HF Space ID
SOUL_FLASHHEAD_SPACE=Soul-AILab/SoulX-FlashHead
SOUL_SINGER_SPACE=Soul-AILab/SoulX-Singer
SOUL_PODCAST_SPACE=Soul-AILab/SoulX-Podcast-1.7B
SOUL_HF_TOKEN=hf_xxxxx

# 重启后端即可切回（无需改代码）
```

---

## 七、费用预估

### 7.1 月度费用

| 场景 | 每次时长 | 每周次数 | 月费 | 说明 |
|------|---------|---------|------|------|
| **轻度实验** | 2 小时 | 3 次 | **≈ ¥72~84** | 每次试一两个模型 |
| **中度开发** | 3 小时 | 5 次 | **≈ ¥180~210** | 调试 + 集成测试 |
| **重度使用** | 5 小时 | 10 次 | **≈ ¥600~700** | 密集开发 + Demo |

### 7.2 首次部署费用

| 项目 | 时长 | 费用 |
|------|------|------|
| 环境搭建 (Phase 1-3) | ~1 小时 | ≈ ¥3~3.5 |
| 模型下载 (Phase 2) | ~0.5 小时 | 含在上面 |
| 服务启动与验证 (Phase 4-7) | ~0.5 小时 | ≈ ¥1.5~1.75 |
| **首次总计** | **~1.5 小时** | **≈ ¥5** |

> 首次部署完成后保存镜像，后续每次开机直接 `start_all.sh`，2 分钟内可用。

---

## 八、ttsapp 后端代码适配清单

### 8.1 需要修改的文件

| 文件 | 修改内容 | 改动量 |
|------|---------|--------|
| `backend/.env` | 三个 Space ID 改为 AutoDL URL | 3 行 |
| `backend/app/config.py` | **无需修改**（配置项名不变） | 0 行 |
| `backend/app/core/gradio_client.py` | **无需修改**（Client 原生支持 URL） | 0 行 |
| `backend/app/core/flashhead_client.py` | **无需修改**（API 接口不变） | 0 行 |
| `backend/app/core/singer_client.py` | **无需修改** | 0 行 |
| `backend/app/core/podcast_client.py` | **无需修改** | 0 行 |

> **总计改动：仅 `.env` 中 3 行配置**。现有架构的 `GradioSpaceClient` 抽象层设计得很好，切换后端完全透明。

### 8.2 可选优化：超时时间调整

AutoDL 自部署响应更快，可适当缩短超时：

```python
# backend/.env
SOUL_API_TIMEOUT=120  # 从 300 秒缩短到 120 秒（自部署无排队）
```

### 8.3 可选优化：移除 HLS 转换逻辑

如果 AutoDL 上的 FlashHead 直接返回 MP4（本地推理通常直出 MP4，无 HLS 流），可简化 `flashhead_client.py` 中的 `_convert_hls_to_mp4_bytes` 逻辑。但**建议保留**，做兼容性兜底。

---

## 九、风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| RTX 5090 无卡可租 | 中 | 无法开机 | 选择多个区域备选；或临时切回 HF Spaces |
| 三模型同时运行 OOM | 低 | 服务崩溃 | 按需切换模式；或降为 Lite 模式 |
| AutoDL 端口映射不稳定 | 低 | 连接中断 | 备选 SSH 隧道方案 |
| 模型版本更新 | 中 | 需重新部署 | 保存镜像分版本；git pull 更新 |
| Gradio API 接口变更 | 低 | 调用失败 | 锁定 Gradio 版本；AutoDL 上用固定 commit |
| 关机忘了导致持续计费 | 中 | 浪费钱 | AutoDL 支持设置「定时关机」和「余额不足自动关机」 |

---

## 十、后续演进路线

### 10.1 短期（1~2 周）

- [x] 确定方案：AutoDL + RTX 5090
- [ ] Phase 0-3：注册、创建实例、下载模型
- [ ] Phase 4-7：启动服务、配置映射、联调验证
- [ ] Phase 8：保存镜像
- [ ] 本地 ttsapp 改 `.env` 完成切换

### 10.2 中期（1~2 月）

- [ ] 评估 LiveAct 在 RTX 5090 上的实际效果（6FPS 是否可接受）
- [ ] 考虑将 ttsapp 后端也部署到 AutoDL（消除跨网延迟）
- [ ] 编写自动化脚本：开机 → 启动服务 → 健康检查 → 通知

### 10.3 长期

- [ ] 等待 FlashHead Pro FP4 支持（RTX 5090 原生 FP4，显存减半）
- [ ] 评估 FlashTalk 4-GPU 版本（如果发布 4090/5090 多卡方案）
- [ ] 考虑包月方案（如使用频率超过每天 3 小时）

---

## 附录 A：Gradio 启动参数参考

### FlashHead

```bash
# Lite 模式（96FPS，推荐默认）
python gradio_app_streaming.py \
  --ckpt_dir ~/models/SoulX-FlashHead-1_3B \
  --wav2vec_dir ~/models/wav2vec2-base-960h \
  --model_type lite \
  --server_port 7860 \
  --server_name 0.0.0.0

# Pro 模式（16.8FPS，高画质）
python gradio_app_streaming.py \
  --ckpt_dir ~/models/SoulX-FlashHead-1_3B \
  --wav2vec_dir ~/models/wav2vec2-base-960h \
  --model_type pro \
  --server_port 7860 \
  --server_name 0.0.0.0
```

### Podcast

```bash
python gradio_app.py \
  --model_dir ~/models/SoulX-Podcast \
  --server_port 7861 \
  --server_name 0.0.0.0
```

### Singer

```bash
python gradio_app.py \
  --model_dir ~/models/SoulX-Singer \
  --server_port 7862 \
  --server_name 0.0.0.0
```

---

## 附录 B：快速命令速查

```bash
# ── 开机后一键启动 ──
~/start_all.sh

# ── 查看服务状态 ──
tmux attach -t soul           # 进入 tmux 会话
# Ctrl+B → 0/1/2 切换窗口     # 查看各服务日志

# ── 查看 GPU 状态 ──
nvidia-smi                     # 显存占用
watch -n 2 nvidia-smi          # 实时监控

# ── 查看服务日志 ──
tail -f ~/logs/flashhead.log
tail -f ~/logs/podcast.log
tail -f ~/logs/singer.log

# ── 停止单个服务 ──
tmux send-keys -t soul:0 C-c   # 停止 FlashHead
tmux send-keys -t soul:1 C-c   # 停止 Podcast
tmux send-keys -t soul:2 C-c   # 停止 Singer

# ── 测试 Gradio 连通性 ──
curl http://localhost:7860/api/predict  # FlashHead
curl http://localhost:7861/api/predict  # Podcast
curl http://localhost:7862/api/predict  # Singer
```

---

## 附录 C：目录结构总览

```
AutoDL 实例 ~/
├── models/                          # 模型权重（数据盘）
│   ├── SoulX-FlashHead-1_3B/       # ~2.6 GB
│   ├── wav2vec2-base-960h/          # ~360 MB
│   ├── SoulX-Podcast/               # ~3.4 GB
│   ├── SoulX-Singer/                # ~4 GB
│   └── chinese-wav2vec2-base/       # ~360 MB (LiveAct 用)
├── services/                        # 服务代码
│   ├── flashhead/                   # FlashHead Gradio 服务
│   │   ├── gradio_app_streaming.py
│   │   └── ...
│   ├── podcast/                     # Podcast Gradio 服务
│   │   ├── gradio_app.py
│   │   └── ...
│   └── singer/                      # Singer Gradio 服务
│       ├── gradio_app.py
│       └── ...
├── logs/                            # 日志
│   ├── flashhead.log
│   ├── podcast.log
│   └── singer.log
├── start_all.sh                     # 一键启动脚本
└── .bashrc                          # conda activate soul
```

---

*本文档基于 `soul专题数字人调研.md` 和 `算力租赁平台研究.md` 的调研结论，结合 ttsapp 现有代码架构设计。*
