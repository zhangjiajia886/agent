# AutoDL 部署重大问题分析

> 生成时间：2026-04-25 14:05  
> 当前实例：RTX 5090 32GB · Ubuntu 22.04 · CUDA 12.8

---

## 一、当前真实状态快照

| 项目 | 状态 | 详情 |
|------|------|------|
| 系统盘 (overlay /30GB) | ✅ 正常 | 已用 2.8G，剩余 28G |
| 数据盘 (autodl-tmp /50GB) | ✅ 正常 | 模型占 25G，剩余 26G |
| 模型权重 4 个 | ✅ 安全 | 全部在数据盘，重启不丢 |
| conda base 环境 | ✅ 可用 | torch 2.7.0+cu128 已预装 |
| conda soul 环境 | ❌ 不可用 | 只有 6 个包，torch/gradio 等全无 |
| ~/services 代码目录 | ❌ 不存在 | 服务仓库未克隆 |
| GPU | ✅ 就绪 | RTX 5090，32GB 全部空闲 |

---

## 二、重大问题逐一分析

---

### 问题 1：soul 环境不完整（当前阻塞部署的核心问题）

**现象**：  
`conda activate soul && python -c "import torch"` → `ModuleNotFoundError`

**原因**：  
setup_autodl.sh 脚本在 Phase 2（apt install ffmpeg）完成后，Phase 3（pip install torch/flash_attn/gradio）开始前被用户手动终止。soul 环境被创建了，但一个 pip 包都没装进去。

**影响**：  
服务完全无法启动。

**解法**：  
不重新建 soul 环境，直接在 **base 环境** 上补装缺失包（base 已有 torch 2.7.0），节省 3-4GB 磁盘和 30 分钟编译时间。或重新写一个只补装 pip 包的精简脚本。

---

### 问题 2：flash_attn 编译耗时极长（部署效率问题）

**现象**：  
`pip install flash_attn --no-build-isolation` 需要从源码编译，在 CPU 上耗时 **30~60 分钟**，期间 GPU 闲置，计费继续跑。

**原因**：  
flash_attn 没有预编译的 wheel 文件支持 RTX 5090 (sm_100 架构)，必须现场编译。

**影响**：  
每次系统盘重置后重新部署，都需要烧掉 1 小时计费等待编译。

**解法（两条路选一）**：  
- **根治**：部署完成后立刻在 AutoDL 控制台保存镜像快照，下次直接从快照启动，无需任何重装。  
- **临时**：把编译好的 flash_attn wheel 文件存到数据盘，下次 `pip install` 直接本地安装。

---

### 问题 3：模型体积严重低估（已影响部署决策）

**现象**：  
设计文档估算模型合计约 11GB，实际下载后合计 **25.8GB**，差了 2.4 倍。

| 模型 | 设计估算 | 实际大小 | 误差倍数 |
|------|---------|---------|---------|
| FlashHead-1_3B | 2.6 GB | **14 GB** | **5.4×** |
| wav2vec2 | 360 MB | 1.1 GB | 3× |
| Podcast-1.7B | 3.4 GB | 5.4 GB | 1.6× |
| Singer | 4 GB | 5.3 GB | 1.3× |

**原因**：  
设计文档用「参数量 × 2字节 = FP16 大小」公式估算，但 HuggingFace 仓库实际包含：  
- FP32 全精度权重（4字节/参数，是 FP16 的 2 倍）  
- 多个 checkpoint 快照  
- 参考视频/图片素材（FlashHead 仓库含大量 MP4/PNG 演示文件）  
- 训练中间状态文件  

**影响**：  
- 引发了不必要的磁盘恐慌（93% 警告）  
- 数据盘 50GB 实际使用了一半

**解法**：  
已无影响——模型在数据盘，数据盘还剩 26GB 充裕。后续规划以实际大小为准。

---

### 问题 4：系统盘每次重启会丢失 pip 依赖（长期隐患）

**现象**：  
实例关机再开机后，覆盖层文件系统（overlay）恢复到基础镜像状态，所有通过 pip 安装的包、克隆的代码、生成的脚本全部消失。

**已安全的**：  
数据盘 `/root/autodl-tmp` 持久保留（模型权重不受影响）。

**影响**：  
- 每次重启需要重新跑一遍完整的 pip install 流程（约 1~2 小时）  
- 无法做到「关机省钱、开机即用」

**解法（必须做，否则每次开机都是灾难）**：  
完整部署完成后，在 AutoDL 控制台 → 「我的镜像」→ 「保存镜像」，把当前环境打成快照。  
下次开机选这个快照，30 秒内恢复完整环境，什么都不需要重装。

---

### 问题 5：服务仓库代码未获取（当前阻塞）

**现象**：  
`~/services/` 目录不存在，三个服务的 GitHub 仓库均未克隆。

**原因**：  
setup_autodl.sh 的 Phase 4 没有执行到。

**风险**：  
Soul-AILab 的 GitHub 仓库是否公开、是否存在、requirements.txt 内容是否已知——全部未验证。如果仓库是私有的，则无法直接 `git clone`。

**解法**：  
立刻验证三个仓库是否可访问：
```
https://github.com/Soul-AILab/SoulX-FlashHead
https://github.com/Soul-AILab/SoulX-Podcast
https://github.com/Soul-AILab/SoulX-Singer
```

---

### 问题 6：三个服务依赖版本严重冲突（最关键问题，影响整体架构）

**现象**：  
读取三个仓库的 `requirements.txt` 后发现核心包版本互相矛盾，**无法共用同一个 conda 环境**。

| 依赖包 | FlashHead | Podcast | Singer | 是否冲突 |
|--------|-----------|---------|--------|---------|
| **torch** | 2.7+ | **2.7.1** | **2.2.0** | ❌ 冲突 |
| **torchaudio** | — | 2.7.1 | 2.2.0 | ❌ 冲突 |
| **gradio** | **5.50.0** | 无限制 | **6.3.0** | ❌ 冲突 |
| **transformers** | **4.57.3** | **4.57.1** | **4.41.2** | ❌ 冲突 |
| **numpy** | 无限制 | 无限制 | **<2.0.0** | ❌ 与 base (2.2.6) 冲突 |
| **accelerate** | >=1.8.1 | **1.10.1** | **1.11.0** | ⚠️ 微小冲突 |

**Singer 是最大的异类**：要求 torch==2.2.0（其他两个要 2.7.x），numpy<2.0（base 已是 2.2.6）。  
**这不是能协商的小版本差异——torch 2.2 和 torch 2.7 根本不兼容。**

**额外风险**：  
Singer 要求 `torch==2.2.0`，但 RTX 5090（Blackwell SM_100 架构）**最低需要 PyTorch 2.6+** 才有 CUDA 12.8 官方支持。**Singer 可能根本无法在 RTX 5090 上运行。**

**必须的架构调整**：

```
原设计（错误）：一个 soul 环境运行全部三个服务
↓
正确方案：每个服务独立 conda 环境

env-flashhead  → torch 2.7.1, transformers 4.57.3, gradio 5.50.0
env-podcast    → torch 2.7.1, transformers 4.57.1
env-singer     → torch 2.2.0（⚠️ RTX 5090 兼容性待验证）
```

磁盘影响：3 个环境每个约 4~6GB，合计额外占用 **12~18GB 系统盘**。

---

## 三、换 80GB 卡能解决这些问题吗？

**不能。**

| 问题 | 与 GPU 显存有关？ | 换 80GB 有效？ |
|------|---------------|--------------|
| soul 环境不完整 | ❌ | ❌ |
| flash_attn 编译慢 | ❌ | ❌ |
| 系统盘重启丢失 | ❌ | ❌ |
| 服务代码未克隆 | ❌ | ❌ |
| 模型体积低估 | ❌ | ❌ |
| **依赖版本冲突** | ❌ | ❌ |
| **Singer 不支持 RTX 5090** | ⚠️ 有关 | ✅ 无效（换老卡才有用） |

上述问题全部是**软件/架构问题**，换 80GB 卡只会费用翻倍（A100 80GB ≈ ¥7/h）。  
**Singer 的 RTX 5090 兼容性问题**需要的是换老架构卡（如 A100/V100），不是更大显存的卡。  

**结论：不换卡。先验证 Singer 在 RTX 5090 上能否运行，不能运行再决策。**

---

## 四、解决路线（按优先级）

```
已完成：
  ✅ Step 1. 验证 3 个 GitHub 仓库全部公开可访问（均返回 200）
  ✅ Step 2. 读取各仓库 requirements.txt，发现版本冲突

立刻执行：
  Step 3. 为每个服务创建独立 conda 环境（env-flashhead, env-podcast, env-singer）
  Step 4. 克隆三个服务仓库到 ~/services/
  Step 5. 在 env-singer 中测试 torch==2.2.0 能否在 RTX 5090 上运行（CUDA 兼容性验证）
  Step 6. 在各自环境中安装依赖，优先跑通 FlashHead（风险最低）

完成部署后立刻执行：
  Step 7. 保存 AutoDL 镜像快照（控制台操作，约 5 分钟）→ 解决重启丢环境问题
  Step 8. 测试 ~/start_all.sh 一键启动所有服务

如果 Singer 无法在 RTX 5090 运行：
  Step 9. 决策：放弃 Singer / 找 RTX 5090 兼容的 torch 版本 / 换 A100 实例
```

---

## 五、当前最快恢复路径（基于真实 requirements）

**已知信息**：三个仓库已验证可访问，requirements.txt 已读取。  
**模型**：全部安全在数据盘。  
**下一步**：用下面的脚本一键克隆代码 + 建三个独立环境：

```bash
# ── 克隆代码 ──
ssh autodl 'mkdir -p ~/services && \
  git clone https://github.com/Soul-AILab/SoulX-FlashHead ~/services/flashhead && \
  git clone https://github.com/Soul-AILab/SoulX-Podcast ~/services/podcast && \
  git clone https://github.com/Soul-AILab/SoulX-Singer ~/services/singer'

# ── 建 FlashHead 环境（torch 2.7.1）──
ssh autodl 'source ~/miniconda3/etc/profile.d/conda.sh && \
  conda create -n env-flashhead python=3.10 -y && conda activate env-flashhead && \
  nohup pip install -r ~/services/flashhead/requirements.txt \
  torch==2.7.1 torchaudio==2.7.1 \
  --index-url https://download.pytorch.org/whl/cu128 \
  > ~/logs/install_flashhead.log 2>&1 & echo PID=$!'

# ── 建 Podcast 环境（torch 2.7.1）──
ssh autodl 'source ~/miniconda3/etc/profile.d/conda.sh && \
  conda create -n env-podcast python=3.10 -y && conda activate env-podcast && \
  nohup pip install -r ~/services/podcast/requirements.txt \
  --index-url https://download.pytorch.org/whl/cu128 \
  > ~/logs/install_podcast.log 2>&1 & echo PID=$!'

# ── 建 Singer 环境（torch 2.2.0，存在 RTX 5090 兼容性风险）──
ssh autodl 'source ~/miniconda3/etc/profile.d/conda.sh && \
  conda create -n env-singer python=3.10 -y && conda activate env-singer && \
  nohup pip install -r ~/services/singer/requirements.txt \
  > ~/logs/install_singer.log 2>&1 & echo PID=$!'
```

预计耗时：git clone 2 分钟，3 个环境各安装约 10~20 分钟。

---

## 六、迁移新实例硬件推荐（2026-04-25 实测数据）

### 实测资源占用

| 资源 | 当前实例 | 实测占用 | 占用率 |
|---|---|---|---|
| 数据盘 | 50 GB | **51 GB（已爆）** | 102% ❌ |
| GPU 显存 | RTX 5090 32 GB | 空闲5GB，推理峰值~24GB | 75% ⚠️ |
| 系统内存 | 754 GB（宿主共享） | ~67 GB | <10% ✅ |

### 实测磁盘明细

| 内容 | 大小 |
|---|---|
| FlashHead 模型 | 14 GB |
| Podcast 模型 | 5.4 GB |
| Singer 模型 | 5.3 GB |
| Singer-Preprocess 模型 | 2.5 GB |
| wav2vec2 模型 | 1.1 GB |
| env-flashhead | 8.6 GB |
| env-podcast | 7.8 GB |
| env-singer | 6.4 GB |
| **合计** | **51.1 GB** |

### RTX 5090 已知问题（选新机型的关键依据）

| 问题 | 影响 |
|---|---|
| Singer torch 2.2.0 不支持 sm_120 | ❌ Singer 完全无法运行 |
| flash_attn 不支持 sm_120 | FlashHead 慢 5-10 倍 |
| 50GB 数据盘已爆满 | 无法存生成文件 |

---

### 推荐机型：A100 SXM4 40GB

> **核心原因**：A100 (sm_80) 完整支持 torch 2.2.0，Singer 可正常运行；flash_attn 有预编译 wheel，FlashHead 全速运行。

#### 资源规划（≤70% 目标）

| 资源 | 需求量 | 推荐配置 | 预期占用率 |
|---|---|---|---|
| **GPU 显存** | 峰值 ~24 GB | **A100 40 GB** | ~60% ✅ |
| **数据盘** | 当前 51 GB + 生成文件 | **100 GB** | ~51% ✅ |
| **系统内存** | 三服务合计 ~30 GB | **80 GB**（A100标配） | ~38% ✅ |

#### 显存占用预估

| 服务 | 空闲显存 | 推理峰值 |
|---|---|---|
| FlashHead | 4 GB | ~11 GB |
| Podcast | 5.3 GB | ~7 GB |
| Singer | — | ~4-6 GB |
| **三服务峰值合计** | — | **~24 GB** |
| A100 40GB 占用率 | — | **60%** ✅ |

#### 其他可选机型对比

| 机型 | 显存 | Singer兼容 | flash_attn | 参考价 | 推荐度 |
|---|---|---|---|---|---|
| **A100 SXM4 40GB** | 40 GB | ✅ | ✅ 有预编译wheel | ~¥4/h | ⭐⭐⭐⭐⭐ |
| A100 SXM4 80GB | 80 GB | ✅ | ✅ | ~¥7/h | ⭐⭐⭐⭐（贵） |
| RTX 4090 24GB | 24 GB | ⚠️ 存疑 | ⚠️ 存疑 | ~¥3/h | ⭐⭐⭐ |
| RTX 5090 32GB（当前） | 32 GB | ❌ Singer不可用 | ❌ 编译失败 | ~¥5/h | ⭐⭐ |
| V100 32GB | 32 GB | ✅ | ✅ | ~¥2.5/h | ⭐⭐⭐（旧卡，慢） |

### 新实例开通步骤

```
1. AutoDL 控制台 → 当前实例 → 「更多」→ 「保存镜像」（5分钟）
   ⚠️ 重要：镜像保存 envs + 代码，下次无需重装
   ⚠️ 注意：模型在数据盘，镜像不包含，新实例需重新挂载或迁移

2. 开新实例
   - GPU：A100 SXM4 40GB
   - 数据盘：100 GB
   - 镜像：选刚保存的快照（如可用）或重新部署

3. 数据盘迁移（两种方式选一）
   方式A：新实例 rsync 从旧实例拉模型（实例同区域，走内网快）
   方式B：旧实例关机，拍数据盘快照，新实例挂载快照

4. 如果重新部署（从零开始）：
   参考「真实记录执行的所有命令.md」逐节执行即可
   核心命令顺序：克隆代码 → 安装环境 → 下载模型 → start_all.sh
```

### 新实例部署注意事项（避免重踏旧坑）

```bash
# 1. Singer 路径软链（必做，否则报 FileNotFoundError）
ln -sf ~/models ~/services/singer/pretrained_models/SoulX-Singer
ln -sf ~/models ~/services/singer/pretrained_models/SoulX-Singer-Preprocess

# 2. FlashHead 路径软链（必做）
ln -sf ~/models ~/services/flashhead/models

# 3. 端口：只有 6006 和 6008 可以通过 AutoDL 公网访问
#    FlashHead → 6006, Podcast → 6008, Singer → 7862（SSH tunnel）

# 4. flash_attn 在 A100 有预编译 wheel，直接 pip install 即可（无需编译）
pip install flash_attn -i https://pypi.tuna.tsinghua.edu.cn/simple
```
