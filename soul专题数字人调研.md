# Soul AI Lab 数字人模型专题深度调研

> 更新时间：2026 年 4 月 23 日  
> 覆盖 SoulX-FlashTalk / SoulX-FlashHead / SoulX-LiveAct 三大模型全方位对比

---

## 一、背景：Soul AI Lab 是谁？

**Soul App**（张璐团队）旗下 AI 研究部门，聚焦**实时数字人**技术。2025 年底至 2026 年 4 月，连续开源 3 款实时数字人模型，形成了从"高性能集群" → "消费级显卡"的完整技术路线图。

此外团队还开源了语音生态模型，并发布了闭源的全双工通话大模型，构建完整的"实时交互"多模态技术生态（详见下方）。

### Soul AI Lab 语音生态模型详解

#### 1. SoulX-Podcast — 播客级多人语音合成

- **仓库**: [Soul-AILab/SoulX-Podcast](https://github.com/Soul-AILab/SoulX-Podcast) | **3.3k Stars** | **Apache 2.0**
- **发布**: 2025.10.28（次日登顶 HuggingFace TTS 趋势榜）
- **论文**: [arXiv 2510.23541](https://arxiv.org/pdf/2510.23541)
- **架构**: LLM (Qwen3-1.7B 基座) + FlowMatching 语音生成范式
- **核心能力**:
  - **多人多轮对话语音生成**: 播客风格长篇对话，也支持单人独白 TTS
  - **零样本跨方言声音克隆**: 用普通话参考音频即可生成四川话、河南话、粤语等方言
  - **副语言控制**: 支持 `<|laughter|>` 笑声、`<|sigh|>` 叹气、`<|breathing|>` 呼吸、`<|coughing|>` 咳嗽、`<|throat_clearing|>` 清嗓等拟声标签
  - **语言**: 中文（普通话 + 多方言）+ 英文
  - 可稳定输出超过 **60 分钟**自然流畅语音
- **部署**: 支持 vLLM + Docker、WebUI、HuggingFace 在线 Demo
- **开源内容**: 推理代码 + 模型权重（HuggingFace）
- **是否收费**: ✅ **完全免费，Apache 2.0 可商用**

#### 2. SoulX-Singer — 零样本歌声合成

- **仓库**: [Soul-AILab/SoulX-Singer](https://github.com/Soul-AILab/SoulX-Singer) | **573 Stars** | **Apache 2.0**
- **发布**: 2026.02.06
- **论文**: [arXiv 2602.07803](https://arxiv.org/abs/2602.07803)
- **训练数据**: 42,000+ 小时对齐的人声、歌词、音符数据
- **核心能力**:
  - **零样本歌声合成 (SVS)**: 无需微调即可模仿未见过的歌手声音
  - **双控制模式**: 旋律控制 (F0 contour) + 乐谱控制 (MIDI notes)
  - **歌声转换 (SVC)**: SoulX-Singer-SVC 模型，直接从原始歌声音频转换，无需歌词/MIDI 转写
  - **语言**: 中文、英文、粤语三语
  - **歌词编辑**: 修改歌词同时保持自然韵律
  - **跨语言合成**: 解耦音色与内容，实现跨语言高保真合成
- **部署**: WebUI + HuggingFace 在线 Demo + MIDI 在线编辑器
- **开源内容**: 推理代码 + 模型权重 + SVC 模型 + 评测数据集 (SoulX-Singer-Eval)
- **是否收费**: ✅ **完全免费，Apache 2.0 可商用**

#### 3. SoulX-Duplug — 全双工语音对话控制模块

- **仓库**: [Soul-AILab/SoulX-Duplug](https://github.com/Soul-AILab/SoulX-Duplug) | **195 Stars** | **Apache 2.0**
- **发布**: 2026.03.16（联合上海交通大学 X-LANCE Lab + 西北工业大学 ASLP@NPU）
- **论文**: [arXiv 2603.14877](https://arxiv.org/abs/2603.14877)
- **核心能力**:
  - **即插即用**流式语义 VAD 模型，赋予半双工语音系统全双工能力
  - 通过文本引导的流式状态预测，实现低延迟、语义感知的对话管理
  - 将 VAD（话音检测）、ASR（语音识别）、Turn Detection（轮次判断）**统一建模**
  - 无需修改原有模型架构即可接入
  - 配套开源完整的对话系统 Demo
- **部署**: 提供在线交互 Demo + 评测数据集 (SoulX-Duplug-Eval)
- **开源内容**: 推理代码 + 模型权重 + 对话系统 + 评测集
- **是否收费**: ✅ **完全免费，Apache 2.0 可商用**

#### 4. SoulX-DuoVoice — 端到端全双工语音通话大模型（闭源）

- **状态**: ❌ **未开源**，仅 Soul App 内部使用（已在站内开启内测）
- **核心能力**:
  - 双 LLM 架构: Dialogue Model（对话理解与生成）+ Speech Model（语音生成）
  - 摒弃传统 VAD 机制，AI 自主决策对话节奏
  - 支持主动打断、适时打断用户、边听边说、时间语义感知、并行发言
  - 实现"类真人"的自然对话体验
- **是否收费**: N/A（未开源，暂不可用）

---

## 二、收费与许可证

### 数字人模型

| 模型 | 许可证 | 代码开源 | 模型权重开源 | 训练代码 | 商用是否免费 |
|------|--------|---------|-------------|---------|-------------|
| **SoulX-FlashTalk** | **Apache 2.0** | ✅ 已开源 | ✅ HuggingFace | ❌ 未开源 | ✅ **免费商用** |
| **SoulX-FlashHead** | **Apache 2.0** | ✅ 已开源 | ✅ HuggingFace (Lite+Pro) | ❌ 未开源 (Pretrained 即将发布) | ✅ **免费商用** |
| **SoulX-LiveAct** | **未明确标注** | ✅ 已开源 | ✅ HuggingFace + ModelScope | 🔜 计划开源 | ⚠️ 需关注后续许可声明 |

### 语音生态模型

| 模型 | 许可证 | 代码开源 | 模型权重开源 | Stars | 商用是否免费 |
|------|--------|---------|-------------|-------|-------------|
| **SoulX-Podcast** | **Apache 2.0** | ✅ 已开源 | ✅ HuggingFace | 3.3k | ✅ **免费商用** |
| **SoulX-Singer** | **Apache 2.0** | ✅ 已开源 | ✅ HuggingFace | 573 | ✅ **免费商用** |
| **SoulX-Duplug** | **Apache 2.0** | ✅ 已开源 | ✅ HuggingFace | 195 | ✅ **免费商用** |
| **SoulX-DuoVoice** | — | ❌ 未开源 | ❌ 未开源 | — | ❌ 不可用（闭源） |

### 结论：收费吗？

> **除 DuoVoice 外，Soul AI Lab 所有已开源模型（6 款）全部采用 Apache 2.0 许可证，完全免费，允许商用、修改、再分发。**
>
> **不存在任何收费项**：无 API 调用费、无模型下载费、无使用次数限制。

---

## 二-A、在线 Demo 使用指南（无需安装，浏览器直接体验）

以下所有在线 Demo **完全免费**，无需注册账号，打开浏览器即可使用。

### 1. SoulX-FlashHead — 实时数字人（流式生成）

| | |
|---|---|
| **入口** | https://huggingface.co/spaces/Soul-AILab/SoulX-FlashHead |
| **运行环境** | HuggingFace ZeroGPU（免费，排队制） |
| **支持模式** | 普通生成 + **流式实时生成** |

**使用步骤**:
1. 打开上述链接，等待 Space 加载（首次可能需 1-2 分钟）
2. **上传参考图片**: 一张正面人脸照片（512×512 最佳）
3. **上传音频文件**: 一段语音音频（wav/mp3）
4. 点击 **Generate** 生成口型同步的数字人视频
5. 流式模式下可实时预览生成过程

> 💡 高峰期可能需要排队。如需无排队体验，可本地部署 Lite 版（单卡 4090 即可）。

---

### 2. SoulX-Singer — AI 歌声合成 + 歌声转换

| | |
|---|---|
| **歌声合成入口** | https://huggingface.co/spaces/Soul-AILab/SoulX-Singer |
| **MIDI 编辑器** | https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor |
| **运行环境** | HuggingFace ZeroGPU（免费） |

**歌声合成 (SVS) 使用步骤**:
1. 打开 SoulX-Singer Space
2. **上传参考音频**: 提供一段目标歌手的声音样本（用于零样本音色克隆）
3. **输入歌词**: 填入想要演唱的歌词文本
4. **选择控制模式**:
   - **Melody 模式**: 上传 F0 旋律文件，模型按旋律演唱
   - **Score 模式**: 上传 MIDI 乐谱，模型按乐谱演唱
5. 点击生成，等待合成完成后下载音频

**歌声转换 (SVC) 使用步骤**:
1. 同一 Space 中切换到 SVC 标签页
2. **上传目标歌手参考音频**: 提供想要转换到的音色样本
3. **上传源歌曲音频**: 待转换的原始歌声录音
4. 点击转换，模型将保留原曲旋律和歌词，仅替换音色

**MIDI 编辑器**:
- 在线可视化编辑 MIDI 音符，无需安装专业音乐软件
- 编辑完成后可直接导入 SoulX-Singer 进行合成

---

### 3. SoulX-Podcast — 播客语音生成

| | |
|---|---|
| **入口** | https://huggingface.co/spaces/Soul-AILab/SoulX-Podcast-1.7B |
| **运行环境** | HuggingFace ZeroGPU（免费） |

**使用步骤**:
1. 打开上述链接
2. **上传参考音频**: 提供说话人声音样本（用于零样本声音克隆）
3. **输入文本**: 填入需要合成的对话/独白文本
   - 多人对话: 用角色标记区分不同说话人
   - 可插入副语言标签: `<|laughter|>` `<|sigh|>` `<|breathing|>` 等
4. **选择方言**（可选）: 普通话 / 四川话 / 河南话 / 粤语 / 英语
5. 点击生成，等待合成完成后播放或下载

> 💡 方言模型需使用 `SoulX-Podcast-1.7B-dialect` 权重，在线 Demo 已集成。

---

### 4. SoulX-Duplug — 全双工语音对话

| | |
|---|---|
| **入口** | https://soulx-duplug.sjtuxlance.com/ |
| **运行环境** | 上海交通大学服务器 |

**使用步骤**:
1. 打开上述链接（Chrome 浏览器推荐）
2. **允许麦克风权限**
3. 直接对着麦克风说话，体验全双工语音交互
4. AI 可以主动打断、边听边说，体验类似真人对话

> ⚠️ 该 Demo 依赖服务器可用性，如无法访问可能是服务器维护中。

---

### 5. SoulX-FlashTalk — 旗舰级数字人

| | |
|---|---|
| **在线 Demo** | 即将上线（Coming Soon） |
| **替代方案** | 本地部署（需 64G+ VRAM 单卡 或 8×H800） |

> FlashTalk 暂无公开在线 Demo。如需体验，推荐先使用 FlashHead 的在线版本（效果类似，帧率更高）。

---

### 6. SoulX-LiveAct — 小时级数字人

| | |
|---|---|
| **在线 Demo** | 暂未提供 |
| **替代方案** | 本地部署 GUI Demo（需 2×H100 或单卡 4090/5090） |

---

### 在线 Demo 汇总速查表

| 模型 | 在线 Demo | 免费 | 需注册 | 需 GPU |
|------|----------|------|--------|--------|
| **FlashHead** | [HF Spaces](https://huggingface.co/spaces/Soul-AILab/SoulX-FlashHead) | ✅ | ❌ | ❌ 云端提供 |
| **Singer** | [HF Spaces](https://huggingface.co/spaces/Soul-AILab/SoulX-Singer) | ✅ | ❌ | ❌ 云端提供 |
| **Singer MIDI 编辑器** | [HF Spaces](https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor) | ✅ | ❌ | ❌ |
| **Podcast** | [HF Spaces](https://huggingface.co/spaces/Soul-AILab/SoulX-Podcast-1.7B) | ✅ | ❌ | ❌ 云端提供 |
| **Duplug** | [在线体验](https://soulx-duplug.sjtuxlance.com/) | ✅ | ❌ | ❌ 云端提供 |
| **FlashTalk** | 即将上线 | — | — | — |
| **LiveAct** | 暂无 | — | — | — |

> **所有在线 Demo 均免费、无需注册账号、无需本地 GPU**，直接在浏览器中使用。高峰期可能排队。

---

## 三、三大模型全景对比

| 维度 | SoulX-FlashTalk | SoulX-FlashHead | SoulX-LiveAct |
|------|----------------|-----------------|---------------|
| **发布时间** | 2026.01.08 | 2026.02.12 | 2026.03.16 |
| **定位** | 旗舰级高保真实时数字人 | 轻量级消费显卡实时数字人 | 小时级长时稳定实时数字人 |
| **参数量** | **14B** | **1.3B** | **18B** (14B Wan2.1 + 4B Audio) |
| **基座模型** | WAN2.1-I2V-14B + InfiniteTalk | 自研架构 | WAN2.1 |
| **核心技术** | Self-Correcting Bidirectional Distillation | Oracle-Guided Bidirectional Distillation + TACC | Neighbor Forcing + ConvKV Memory |
| **实时帧率** | 32 FPS | Lite: **96 FPS** / Pro: 25+ FPS | **20 FPS** |
| **启动延迟** | **0.87s** (亚秒级) | 即时 | ~0.94s |
| **最低硬件** | 8×H800 (实时) / 单卡 64G VRAM (离线) | **单卡 RTX 4090** (Lite, 6.4G 显存) | 2×H100/H200 (实时) / 单卡 RTX 5090 (6FPS) |
| **最大并发** | — | 单卡 4090 最高 **3 路并发** | — |
| **分辨率** | 720×416 | 512×512 | 720×416 / 512×512 / 480×832 |
| **长视频稳定性** | 1000s+ 无漂移 | 无限长度无身份漂移 | **小时级** 无漂移（核心卖点） |
| **输入** | 参考图 + 音频 + 文本 | 参考图 + 音频 | 参考图 + 音频 + 动作/表情编辑 |
| **语言支持** | 中文为主 | **15 种语言** | 中文为主 |
| **数据集** | 内部训练集 | 自研 VividHead (782h, 已开源) | 内部训练集 |
| **GitHub Stars** | 1.2k | 697 | 1.2k |
| **论文** | [arXiv 2512.23379](https://arxiv.org/pdf/2512.23379) | [arXiv 2602.07449](https://arxiv.org/pdf/2602.07449) | [arXiv 2603.11746](https://arxiv.org/abs/2603.11746) |

---

## 四、技术深度解析

### 4.1 SoulX-FlashTalk：14B 旗舰级实时数字人

#### 架构
- **基座**: WAN2.1-I2V-14B DiT + InfiniteTalk
- **四大组件**:
  - **3D VAE**: 时空下采样 4×8×8，压缩视频到 latent 空间
  - **DiT Generator**: 3D Attention + Cross-Attention（参考图/文本）+ Audio Cross-Attention
  - **Conditioning Encoders**: chinese-wav2vec2-base（音频）+ CLIP（参考图）+ umT5（双语字幕）
  - **Latent Input Formulation**: motion frames + noisy latents + reference guidance

#### 训练策略（两阶段）

**Stage 1: Latency-Aware Spatiotemporal Adaptation**
- 将预训练模型适配到更低分辨率和更短帧序列
- 动态宽高比分桶策略，减少填充/裁切损失
- 使 14B 模型在低分辨率下恢复细节和身份一致性

**Stage 2: Self-Correcting Bidirectional Distillation**
- 基于 DMD 框架压缩采样步数，消除 CFG 依赖
- **创新点**: 多步回顾自校正机制 — 生成器自回归生成 K 个连续 chunk，每个 chunk 基于上一个生成结果（而非 GT）
- **Stochastic Truncation Strategy**: 随机截断反向传播，节省显存，训练成本仅需 200 步蒸馏（LiveAvatar 需 27,500 步，效率提升 **~23×**）

#### 推理加速
- **xDiT 混合序列并行**: Ulysses + Ring Attention → DiT 推理 **5× 加速**
- **3D VAE 并行**: LightX2V slicing 策略 → VAE 解码 **5× 加速**
- **FlashAttention3**: 针对 Hopper 架构优化 → 注意力延迟再降 **20%**
- **torch.compile**: 全图优化，最大化硬件利用率

#### 端到端延迟分解（8×H800）
| 组件 | 延迟 |
|------|------|
| 音频处理 | 33ms |
| DiT 4步去噪 | 616ms |
| VAE 解码 | 187ms |
| Motion 编码 | 14ms |
| 其他开销 | ~26ms |
| **总计** | **876ms** |

#### Benchmark 成绩
| 指标 | FlashTalk | EchoMimicV3 | LiveAvatar | InfiniteTalk |
|------|-----------|-------------|------------|-------------|
| ASE (外观) ↑ | **3.51** | 3.45 | - | - |
| IQA (图像质量) ↑ | **4.79** | 4.70 | - | - |
| Sync-C (唇形) ↑ | **1.47** | - | - | - |
| FPS ↑ | **32** | - | 20.88 | - |
| 长视频 Sync-C ↑ | **1.61** | - | - | - |

---

### 4.2 SoulX-FlashHead：1.3B 消费级实时数字人

#### 核心创新

**① Oracle-Guided Bidirectional Distillation（双向蒸馏）**
- 教师模型使用 Ground Truth motion frames 作为"先知"锚点
- 学生模型自回归基于自身预测生成
- 强约束人物特征，解决长视频身份漂移问题

**② Temporal Audio Context Cache (TACC，8秒记忆)**
- 强制缓存 8 秒历史音频特征
- 补偿流式生成中短音频切片的上下文缺失
- 解决口型抖动和同步偏差问题

**③ Streaming-Aware Spatiotemporal Pre-training**
- 针对流式推理场景的时空预训练
- 确保从短音频片段中稳定提取特征

#### 双版本对比

| 版本 | 定位 | 帧率@4090 | 帧率@5090 | 显存占用 | 并发数 |
|------|------|-----------|-----------|---------|--------|
| **Lite** | 高速率 | **96 FPS** | — | **6.4G** | 最高 3 路 |
| **Pro** | 高画质 | 10.8 FPS | 16.8 FPS (单卡) / 25+ FPS (双卡) | — | — |

#### Benchmark 成绩（HDTF + VFHQ）
| 指标 | FlashHead-Pro | 对比 |
|------|--------------|------|
| FID ↓ | **8.31** | SOTA |
| FVD ↓ | **103.14** | SOTA |
| Sync-C ↑ | **5.60** | 大幅领先 |

#### 与竞品帧率对比（60s 长视频@单卡 4090）
| 模型 | FPS |
|------|-----|
| **FlashHead-Lite** | **96.00** |
| Ditto | 45.04 |
| FlashHead-Pro | 10.81 |
| SadTalker | 2.17 |
| EchoMimic_V3 | 0.81 |
| Hallo3 | 0.16 |

> Lite 版推理效率是实时基准 (25FPS) 的 **~4 倍**，是行业同类模型的 **100 倍以上**。

#### VividHead 数据集（已开源）
- 从 10,000+ 小时素材中精炼 **782 小时**高质量音画数据
- 330,000 个短视频片段 (3s-60s)
- 512×512 分辨率，严格时间对齐语音
- 元数据：语言、种族、年龄
- 限制为单人可见说话者
- 下载: [HuggingFace datasets/Soul-AILab/VividHead](https://huggingface.co/datasets/Soul-AILab/VividHead)

---

### 4.3 SoulX-LiveAct：小时级稳定实时数字人

#### 核心创新

**① Neighbor Forcing（邻近强制）**
- 在同一扩散步内，将相邻帧的 latent 信息进行传播
- 模型在统一噪声语义空间中做预测
- 有效减少训练-推理分布不一致导致的不稳定性
- 理论支撑：识别出"扩散步对齐的邻近 latent"是 AR Diffusion 的关键归纳偏置

**② ConvKV Memory（卷积 KV 记忆压缩）**
- 将线性增长的 KV cache 转化为"短期精确 + 长期压缩"格式
- 近期信息保持高精度（局部细节），远期信息通过轻量卷积压缩
- **恒定显存开销**：运行时间从分钟到小时，显存不增长
- 配合 RoPE Reset 对齐位置编码，消除长序列位置漂移

**③ 多模态控制**
- 不仅支持音频驱动，还支持**动作编辑**和**表情编辑**
- 可通过 JSON 配置自定义人物动作和表情

#### 性能数据

| 配置 | 分辨率 | FPS | 延迟 | 计算成本 |
|------|--------|-----|------|---------|
| 2×H100/H200 | 720×416 | **20 FPS** | 0.94s | 27.2 TFLOPs/帧 |
| 2×H100/H200 | 512×512 | 24 FPS | — | — |
| 单卡 RTX 5090 | 416×720 | 6 FPS | — | FP8 KV cache |
| 单卡 RTX 4090 | 416×720 | ~4 FPS | — | FP8 KV + offload |

#### Benchmark 成绩

**HDTF 数据集:**
| 指标 | LiveAct |
|------|---------|
| Sync-C ↑ | **9.40** |
| Sync-D ↓ | **6.76** |
| FID ↓ | 10.05 |
| FVD ↓ | 69.43 |
| VBench Temporal Quality | 97.6 |
| VBench Image Quality | 63.0 |
| VBench-2.0 Human Fidelity | **99.9** |

**EMTD 数据集:**
| 指标 | LiveAct |
|------|---------|
| Sync-C ↑ | 8.61 |
| Sync-D ↓ | 7.29 |
| VBench Temporal Quality | 97.3 |
| VBench Image Quality | 65.7 |
| Human Fidelity | 98.9 |

---

## 五、部署指南速查

### 5.1 FlashTalk 部署

```bash
# 环境
conda create -n flashtalk python=3.10
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
pip install flash_attn==2.8.0.post2 --no-build-isolation

# 模型下载
huggingface-cli download Soul-AILab/SoulX-FlashTalk-14B --local-dir ./models/SoulX-FlashTalk-14B
huggingface-cli download TencentGameMate/chinese-wav2vec2-base --local-dir ./models/chinese-wav2vec2-base

# 推理（单卡 64G+ VRAM，可 --cpu_offload 降至 40G）
bash inference_script_single_gpu.sh

# 实时推理（需 8×H800 或更高）
bash inference_script_multi_gpu.sh
```

### 5.2 FlashHead 部署

```bash
# 环境
conda create -n flashhead python=3.10
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
pip install flash_attn==2.8.0.post2 --no-build-isolation
pip install sageattention==2.2.0 --no-build-isolation  # 可选，加速

# 模型下载
huggingface-cli download Soul-AILab/SoulX-FlashHead-1_3B --local-dir ./models/SoulX-FlashHead-1_3B
huggingface-cli download facebook/wav2vec2-base-960h --local-dir ./models/wav2vec2-base-960h

# Lite 推理（单卡 4090，96FPS）
bash inference_script_single_gpu_lite.sh

# Pro 推理（单卡/多卡）
bash inference_script_single_gpu_pro.sh

# Gradio Web Demo
python gradio_app.py              # 普通模式
python gradio_app_streaming.py    # 流式模式
```

### 5.3 LiveAct 部署

```bash
# 环境
conda create -n liveact python=3.10
pip install -r requirements.txt
conda install conda-forge::sox -y
pip install vllm==0.11.0

# SageAttention（FP8 加速）
git clone https://github.com/thu-ml/SageAttention.git && cd SageAttention && git checkout v2.2.0 && python setup.py install

# LightVAE
git clone https://github.com/ModelTC/LightX2V && cd LightX2V && python setup_vae.py install

# 模型下载
huggingface-cli download Soul-AILab/LiveAct --local-dir ./models/LiveAct

# 2×H100 实时推理 (20FPS)
USE_CHANNELS_LAST_3D=1 CUDA_VISIBLE_DEVICES=0,1 \
torchrun --nproc_per_node=2 generate.py \
  --size 416*720 --ckpt_dir MODEL_PATH --wav2vec_dir chinese-wav2vec2-base \
  --fps 20 --steam_audio

# RTX 4090/5090 消费级推理
USE_CHANNELS_LAST_3D=1 CUDA_VISIBLE_DEVICES=0 \
python generate.py \
  --size 416*720 --ckpt_dir MODEL_PATH --wav2vec_dir chinese-wav2vec2-base \
  --fps 24 --fp8_kv_cache --block_offload --t5_cpu
```

---

## 六、技术路线演进图

```
2025.12  SoulX-FlashTalk (14B)
         │  定位：旗舰级、最高画质
         │  硬件：8×H800 集群
         │  成就：首个 14B 亚秒级实时数字人
         │
2026.02  SoulX-FlashHead (1.3B)
         │  定位：消费级、算力自由
         │  硬件：单卡 RTX 4090
         │  成就：96FPS、6.4G 显存、3 路并发
         │
2026.03  SoulX-LiveAct (18B)
         │  定位：小时级长时稳定
         │  硬件：2×H100/H200
         │  成就：恒定显存、小时级不漂移
         │
2026.04  OpenAvatarChat v0.6.0 集成 FlashHead
         │  → 从模型走向完整对话系统
         ▼
 Future  FlashTalk 4-GPU 版本（即将发布）
         LiveAct 训练代码开源
         FP4 精度支持（RTX 5090/B200）
```

---

## 七、选型决策树

```
需要数字人实时对话？
├─ 有 H100/H800 集群？
│  ├─ 需要小时级不间断直播 → SoulX-LiveAct
│  └─ 追求最高画质短视频 → SoulX-FlashTalk
├─ 只有 RTX 4090/5090？
│  ├─ 需要实时互动 (25+ FPS) → SoulX-FlashHead Lite
│  ├─ 追求画质 (可接受 10-16 FPS) → SoulX-FlashHead Pro
│  └─ 需要完整对话系统 → OpenAvatarChat + FlashHead
└─ 没有 GPU？
   └─ 暂不适用 Soul 系列（考虑 DUIX.ai 移动端方案）
```

---

## 八、应用场景全景

| 场景 | 推荐模型 | 理由 |
|------|---------|------|
| **7×24h 电商直播** | FlashHead Lite | 单卡 4090 即可，96FPS 流畅无压力 |
| **高端品牌宣传片** | FlashTalk | 14B 旗舰画质，超越闭源模型 |
| **AI 一对一外教** | FlashHead (15种语言) | 低延迟实时互动 + 多语言 |
| **游戏 NPC** | FlashHead Lite | 1.3B 轻量，不抢渲染资源 |
| **视频播客** | LiveAct | 小时级稳定，表情动作可编辑 |
| **虚拟客服** | FlashHead + OpenAvatarChat | 完整对话系统，模块化集成 |
| **数字人矩阵直播** | FlashHead Lite (3路并发) | 单卡跑 3 路实时流 |

---

## 九、与行业竞品对比

| 维度 | SoulX 系列 | HeyGem.ai | MuseTalk | EchoMimic | LatentSync |
|------|-----------|-----------|----------|-----------|------------|
| **实时性** | ✅ 32~96 FPS | ❌ 离线 | ✅ 实时 | ❌ 离线 | ❌ 离线 |
| **画质上限** | 🏆 SOTA | 🥈 4K 高清 | 🥉 中等 | 🥈 较好 | 🥈 较好 |
| **长视频稳定性** | 🏆 小时级 | 中等 | 中等 | 差 | 差 |
| **消费级显卡** | ✅ 4090 (FlashHead) | ✅ 1080Ti | ✅ 3060 | ✅ 3060 | ✅ 消费级 |
| **移动端** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **许可证** | Apache 2.0 | Apache 2.0 | 开源 | Apache 2.0 | 开源 |
| **训练数据开源** | ✅ VividHead 782h | ❌ | ❌ | ❌ | ❌ |
| **论文** | 3 篇技术报告 | 无 | 有 | 有 | 有 |

---

## 十、总结

Soul AI Lab 在 4 个月内连续开源 3 款实时数字人模型，形成了**业界最完整的实时数字人开源技术栈**：

1. **完全免费** — Apache 2.0 许可，代码+权重全面开放，无任何收费
2. **覆盖全场景** — 从 H800 集群到单卡 4090，从分钟级到小时级
3. **技术领先** — FlashTalk 在 TalkBench 上全面超越同期 SOTA；FlashHead 帧率是竞品 100 倍以上
4. **数据开源** — VividHead 782h 高质量数据集已开放（行业罕见）
5. **生态联动** — 已被 OpenAvatarChat 集成，配合 SoulX-Podcast / DuoVoice 可构建完整实时交互系统

**如果当前项目需要接入实时数字人能力，FlashHead Lite 是性价比最高的选择（单卡 4090、6.4G 显存、96FPS、Apache 2.0 免费商用）。**

---

## 附：资源链接汇总

| 资源 | FlashTalk | FlashHead | LiveAct |
|------|-----------|-----------|---------|
| **GitHub** | [Soul-AILab/SoulX-FlashTalk](https://github.com/Soul-AILab/SoulX-FlashTalk) | [Soul-AILab/SoulX-FlashHead](https://github.com/Soul-AILab/SoulX-FlashHead) | [Soul-AILab/SoulX-LiveAct](https://github.com/Soul-AILab/SoulX-LiveAct) |
| **论文** | [arXiv 2512.23379](https://arxiv.org/pdf/2512.23379) | [arXiv 2602.07449](https://arxiv.org/pdf/2602.07449) | [arXiv 2603.11746](https://arxiv.org/abs/2603.11746) |
| **模型权重** | [HF: SoulX-FlashTalk-14B](https://huggingface.co/Soul-AILab/SoulX-FlashTalk-14B) | [HF: SoulX-FlashHead-1_3B](https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B) | [HF: LiveAct](https://huggingface.co/Soul-AILab/LiveAct) |
| **在线 Demo** | 即将上线 | [HF Spaces](https://huggingface.co/spaces/Soul-AILab/SoulX-FlashHead) | — |
| **数据集** | — | [VividHead (782h)](https://huggingface.co/datasets/Soul-AILab/VividHead) | — |
| **ComfyUI** | — | [ComfyUI_RH_FlashHead](https://github.com/HM-RunningHub/ComfyUI_RH_FlashHead) | — |
| **项目主页** | [soul-ailab.github.io/soulx-flashtalk](https://soul-ailab.github.io/soulx-flashtalk/) | [soul-ailab.github.io/soulx-flashhead](https://soul-ailab.github.io/soulx-flashhead/) | — |

### 语音生态模型资源链接

| 资源 | SoulX-Podcast | SoulX-Singer | SoulX-Duplug |
|------|--------------|--------------|-------------|
| **GitHub** | [Soul-AILab/SoulX-Podcast](https://github.com/Soul-AILab/SoulX-Podcast) | [Soul-AILab/SoulX-Singer](https://github.com/Soul-AILab/SoulX-Singer) | [Soul-AILab/SoulX-Duplug](https://github.com/Soul-AILab/SoulX-Duplug) |
| **论文** | [arXiv 2510.23541](https://arxiv.org/pdf/2510.23541) | [arXiv 2602.07803](https://arxiv.org/abs/2602.07803) | [arXiv 2603.14877](https://arxiv.org/abs/2603.14877) |
| **模型权重** | [HF: SoulX-Podcast](https://huggingface.co/collections/Soul-AILab/soulx-podcast) | [HF: SoulX-Singer](https://huggingface.co/Soul-AILab/SoulX-Singer) | [HF: SoulX-Duplug](https://huggingface.co/collections/Soul-AILab/soulx-duplug) |
| **在线 Demo** | [HF Spaces](https://huggingface.co/Soul-AILab/spaces) | [HF Spaces](https://huggingface.co/spaces/Soul-AILab/SoulX-Singer) | [在线体验](https://soulx-duplug.sjtuxlance.com/) |
| **评测数据集** | — | [SoulX-Singer-Eval](https://huggingface.co/datasets/Soul-AILab/SoulX-Singer-Eval-Dataset) | [SoulX-Duplug-Eval](https://huggingface.co/datasets/Soul-AILab/SoulX-Duplug-Eval) |
| **项目主页** | [soul-ailab.github.io/soulx-podcast](https://soul-ailab.github.io/soulx-podcast/) | [soul-ailab.github.io/soulx-singer](https://soul-ailab.github.io/soulx-singer/) | — |
| **附加工具** | Docker + vLLM 支持 | [MIDI 在线编辑器](https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor) | 配套对话系统 Demo |

---

*本文档基于 GitHub 仓库、arXiv 论文、新浪财经、中华网等公开资料整理。*
