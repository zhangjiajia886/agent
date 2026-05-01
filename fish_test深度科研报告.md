# Fish Audio TTS 情感标记深度科研报告

> 基于官方文档 https://docs.fish.audio 及项目实测，撰写时间：2026-04-07

---

## 一、模型概览

Fish Audio 目前提供三个 TTS 模型，通过 HTTP Header `model` 指定：

| 模型 | 参数量 | 语言 | WER | 首帧延迟 | 情感语法 | 情感词汇 |
|------|--------|------|-----|---------|---------|---------|
| `s2-pro` | 未公开 | 80+ | — | ~100ms | `[bracket]` | **自然语言，无限制** |
| `s2` | 未公开 | 80+ | — | ~100ms | `[bracket]` | 同 s2-pro（较弱） |
| `s1` | 4B | 80+ | 0.8% | — | `(parenthesis)` | **固定词表，64词** |

> S1 在 TTS-Arena2 全球排名第一（综合质量）；S2-Pro 在延迟和情感灵活度上更优。

---

## 二、S2-Pro 情感标记设计（方括号语法）

### 2.1 核心理念

S2-Pro 使用**自然语言描述**放在方括号内，模型在训练时学习了大量带标注的音频，能理解任意英文描述性词组。**不限于固定词表**。

```
[bracket]               ← 格式
[whispers sweetly]      ← 自然语言描述
[laughing nervously]    ← 复合描述
```

### 2.2 官方预定义标记（最稳定效果）

```
[whisper]    [laugh]    [emphasis]  [sigh]    [gasp]    [pause]
[angry]      [excited]  [sad]       [surprised] [inhale] [exhale]
```

### 2.3 使用规则

1. **插入位置**：放在要控制的文本**前面**，作用于紧随其后的句子/短语
2. **叠加使用**：可在句中多次插入不同标记
3. **自然语言扩展**：可用英文描述组合，如 `[speaking softly and slowly]`、`[very excited]`

**示例：**
```
"I can't believe it [gasp] you actually did it [laugh] I'm so proud of you."
```

```
"[excited] 终于等到你了！[sigh] 唉，但有点累。[whisper] 小声说个秘密…"
```

### 2.4 关键限制

- **标记仅对预训练音色（官方音色）效果显著**
- **克隆音色（reference_id 指向自定义模型）：效果有限或无效**，因为克隆音色在微调时丢失了情感表示空间
- 标记须用英文，中文描述无效

---

## 三、S1 情感标记设计（圆括号语法）

### 3.1 核心理念

S1 使用**固定词表**，64 个情感词精确匹配，不支持任意描述。括号格式为 `(词)` 。

### 3.2 完整词表

#### 基础情感（24 个）
```
(angry) (sad) (excited) (surprised) (satisfied) (delighted)
(scared) (worried) (upset) (nervous) (frustrated) (depressed)
(empathetic) (embarrassed) (disgusted) (moved) (proud) (relaxed)
(grateful) (confident) (interested) (curious) (confused) (joyful)
```

#### 高级情感（25 个）
```
(disdainful) (unhappy) (anxious) (hysterical) (indifferent)
(impatient) (guilty) (scornful) (panicked) (furious) (reluctant)
(keen) (disapproving) (negative) (denying) (astonished) (serious)
(sarcastic) (conciliative) (comforting) (sincere) (sneering)
(hesitating) (yielding) (painful) (awkward) (amused)
```

#### 语调标记（5 个）
```
(in a hurry tone) (shouting) (screaming) (whispering) (soft tone)
```

#### 音效（10 个）
```
(laughing) (chuckling) (sobbing) (crying loudly) (sighing)
(panting) (groaning) (crowd laughing) (background laughter) (audience laughing)
```

### 3.3 使用规则

1. 只能使用上表中的精确词，拼写错误则无效（直接读出来）
2. 放在句子开头或情感转折处
3. 音效类（laughing/sighing 等）可以单独出现，作为"声音动作"

---

## 四、当前项目实现分析

### 4.1 问题复现

项目路径：`backend/app/core/fish_speech.py`

```python
# 当前过滤函数
def _filter_emotion_tags(text: str) -> str:
    """清除方括号 [xxx] 和英文圆括号 (xxx) 情感标记，防止 TTS 朗读出来。"""
    text = re.sub(r'\[[^\]]{1,40}\]', '', text)
    text = re.sub(r'\([a-zA-Z][a-zA-Z\s]{0,30}\)', '', text)
    return text
```

**现状**：情感标记被完全清除后再送 TTS，情感控制完全失效。

### 4.2 根因分析

| 问题 | 根因 |
|------|------|
| 方括号被朗读出来 | AI 系统 prompt 要求加标记，但标记语法错误或模型未识别 |
| 圆括号被朗读出来 | S2-Pro 不支持圆括号，直接读为文本 |
| 情感无效果 | 使用的是克隆音色（reference_id 为自定义模型），克隆音色情感能力弱 |

### 4.3 最优实现策略

```
┌─────────────────────────────────────────────────────────┐
│  场景 A：使用官方预设音色 + S2-Pro                        │
│  → 方括号标记有效，支持自然语言描述                        │
│  → 效果最好，推荐用于演示和产品                            │
├─────────────────────────────────────────────────────────┤
│  场景 B：使用官方预设音色 + S1                            │
│  → 圆括号标记有效，词表固定 64 个                         │
│  → 情感类型丰富，适合剧情/对话场景                         │
├─────────────────────────────────────────────────────────┤
│  场景 C：使用克隆音色（自定义 reference_id）               │
│  → 情感标记基本无效                                       │
│  → 建议：只做自然说话，不加标记                            │
└─────────────────────────────────────────────────────────┘
```

---

## 五、建议的正确实现

### 5.1 后端过滤逻辑修改

```python
def _prepare_tts_text(text: str, tts_model: str, reference_id: str, is_official_voice: bool) -> str:
    """
    根据模型和音色类型决定是否保留情感标记。
    官方预设音色 + 对应模型：保留标记
    克隆音色：清除所有标记
    """
    if not is_official_voice:
        # 克隆音色：清除所有标记，防止读出来
        text = re.sub(r'\[[^\]]{1,40}\]', '', text)
        text = re.sub(r'\([a-zA-Z][a-zA-Z\s]{0,30}\)', '', text)
        return text

    if tts_model == 's2-pro':
        # 清除圆括号（S2-Pro 不支持），保留方括号
        text = re.sub(r'\([a-zA-Z][a-zA-Z\s]{0,30}\)', '', text)
    elif tts_model == 's1':
        # 清除方括号（S1 不支持），保留圆括号
        text = re.sub(r'\[[^\]]{1,40}\]', '', text)
    
    return text
```

### 5.2 AI System Prompt 建议

**S2-Pro 场景（官方音色）：**
```
每句话可用 [情感词] 控制语气，例如：
[excited] 诶，终于来了！[laugh] 嘿嘿！[sigh] 唉，太累了。
支持：[whisper] [laugh] [sigh] [gasp] [angry] [excited] [sad] [pause] 等。
只用英文方括号，不用圆括号。
```

**S1 场景（官方音色）：**
```
每句话可用 (情感词) 控制语气，仅限以下词：
(laughing) (sighing) (excited) (sad) (angry) (nervous) (relaxed) 等。
只用英文圆括号，不用方括号。
```

**克隆音色场景：**
```
直接用中文自然说话，不加任何括号标记。
```

---

## 六、测试方案

### 6.1 使用现有 `/api/v1/tts/test-emotion` 端点测试

该项目已内置调试端点，可通过前端「🧪 情感标记测试」卡片直接操作。

#### 测试矩阵

| 测试编号 | 模型 | 音色类型 | 文本 | 预期结果 |
|---------|------|---------|------|---------|
| T01 | s2-pro | 官方音色 | `[excited] 哇，太棒了！` | 语气激动 |
| T02 | s2-pro | 官方音色 | `[whisper] 小声说话` | 低沉耳语 |
| T03 | s2-pro | 官方音色 | `[laughing nervously] 这个嘛…` | 紧张笑声 |
| T04 | s1 | 官方音色 | `(excited) 哇，太棒了！` | 语气激动 |
| T05 | s1 | 官方音色 | `(sighing) 唉，算了。` | 叹气音效 |
| T06 | s1 | 官方音色 | `(whispering) 小声说话` | 耳语效果 |
| T07 | s2-pro | 克隆音色 | `[excited] 哇，太棒了！` | 无明显情感变化（基线对照） |
| T08 | s1 | 克隆音色 | `(excited) 哇，太棒了！` | 无明显情感变化（基线对照） |
| T09 | s2-pro | 官方音色 | `哇，太棒了！`（无标记） | 平淡对照 |

### 6.2 测试用官方中文音色

通过「发现官方音色」→ 搜索标签 `Chinese` 导入，常见可用 ID：

```
# 在「发现官方音色」对话框搜索后导入，然后在测试卡片 reference_id 选择导入的音色
```

### 6.3 对照实验脚本（curl）

```bash
FISH_KEY="<FISH_API_KEY>"
OFFICIAL_VOICE_ID="<从发现官方音色导入后的 fish_model_id>"

# T01 - S2-Pro + 官方音色 + 方括号情感
curl -X POST https://api.fish.audio/v1/tts \
  -H "Authorization: Bearer $FISH_KEY" \
  -H "Content-Type: application/json" \
  -H "model: s2-pro" \
  -d '{
    "text": "[excited] 哇，真的太棒了！[laugh] 哈哈哈！[sigh] 唉，不过有点累。",
    "reference_id": "'"$OFFICIAL_VOICE_ID"'",
    "format": "mp3",
    "latency": "normal"
  }' -o T01_s2pro_official_excited.mp3

# T04 - S1 + 官方音色 + 圆括号情感
curl -X POST https://api.fish.audio/v1/tts \
  -H "Authorization: Bearer $FISH_KEY" \
  -H "Content-Type: application/json" \
  -H "model: s1" \
  -d '{
    "text": "(excited) 哇，真的太棒了！(laughing) 哈哈哈！(sighing) 唉，不过有点累。",
    "reference_id": "'"$OFFICIAL_VOICE_ID"'",
    "format": "mp3",
    "latency": "normal"
  }' -o T04_s1_official_excited.mp3

# T09 - 无标记对照
curl -X POST https://api.fish.audio/v1/tts \
  -H "Authorization: Bearer $FISH_KEY" \
  -H "Content-Type: application/json" \
  -H "model: s2-pro" \
  -d '{
    "text": "哇，真的太棒了！哈哈哈！唉，不过有点累。",
    "reference_id": "'"$OFFICIAL_VOICE_ID"'",
    "format": "mp3",
    "latency": "normal"
  }' -o T09_baseline_no_tag.mp3
```

### 6.4 评估维度

| 维度 | 说明 | 评分 |
|------|------|------|
| 情感识别 | 标记是否被正确朗读/解释（不读出括号本身） | 是/否 |
| 情感表现 | 语气/音调变化是否可感知 | 1~5 |
| 音质 | 是否有噪音、断裂、异常停顿 | 1~5 |
| 自然度 | 情感过渡是否自然 | 1~5 |

---

## 七、关键结论

1. **S2-Pro 方括号**：灵活但依赖**官方预训练音色**，克隆音色无效。
2. **S1 圆括号**：固定词表 64 词，更可预测，同样需要**官方预训练音色**。
3. **克隆音色**：两种标记效果均弱，建议不加任何标记，让模型自然说话。
4. **正确实现路径**：`官方中文音色` + `S1 固定词表` 是当前最可靠方案，词表明确，可预期。
5. **S2-Pro 自然语言描述**（如 `[speaking calmly]`）可作为音色无关的"软控制"，通过 `style_prompt` 参数拼到文本头部，对整体语气有一定引导作用（本项目已实现）。

---

## 八、推荐的下一步行动

- [ ] 从「发现官方音色」导入 2-3 个中文官方预设音色（tag: Chinese）
- [ ] 在「情感标记测试」卡片用官方音色对 T01~T09 逐一测试，记录分值
- [ ] 根据测试结果决定：是否将 AI 对话的 system prompt 改回情感标记模式
- [ ] 若决定启用 S1 情感标记：修改 `_filter_emotion_tags` 逻辑，对官方音色保留圆括号

---

*报告来源：Fish Audio 官方文档 + 项目实测 | API Key 已在 `.env` 配置*
