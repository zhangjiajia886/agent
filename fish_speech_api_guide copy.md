# Fish Speech API 完整使用指南

> 🐟 Fish Speech 是一个云端 AI 语音服务，提供 **文字转语音（TTS）**、**语音识别（ASR）**、**声音克隆** 等能力。
>
> **Base URL**: `https://api.fish.audio`  
> **鉴权方式**: 每个请求头加 `Authorization: Bearer <你的API Key>`  
> **API Key 获取**: https://fish.audio/app/api-keys/

---

## 一、全部 API 一览（共 10 个）

下面这张图展示了所有 API 的分类：

```
Fish Audio API
│
├── 💰 Wallet（账户）
│   ├── GET  /wallet/self/api-credit     → 查询剩余积分
│   └── GET  /wallet/self/package        → 查询当前套餐
│
├── 🎙️ Voice Models（声音模型/声音克隆）
│   ├── GET    /model                    → 搜索/列出声音模型
│   ├── POST   /model                    → 上传音频，创建克隆声音
│   ├── GET    /model/{model_id}         → 获取某个模型详情
│   ├── PATCH  /model/{model_id}         → 修改模型名称/描述
│   └── DELETE /model/{model_id}         → 删除模型
│
└── 🔊 TTS & ASR（语音合成与识别）
    ├── POST /v1/tts                     → 文字 → 语音（支持流式）
    ├── POST /v1/asr                     → 语音 → 文字
    └── WSS  /v1/tts/live               → WebSocket 实时流式合成
```

---

## 二、最常用：TTS 文字转语音

### 🤔 它能做什么？

```
你输入文字  →  Fish Speech  →  输出语音文件（mp3/wav/pcm/opus）
"你好！"         云端合成          🔊 播放给用户
```

### 📮 接口信息

```
POST https://api.fish.audio/v1/tts
```

### 🎛️ 关键参数说明

```
必填：
  text          → 要合成的文字内容

推荐填写：
  reference_id  → 指定声音模型ID（谁来说话）
                  不填会用默认声音

可选调节：
  format        → 音频格式   mp3（默认）/ wav / pcm / opus
  latency       → 速度/质量  normal（最好）/ balanced（均衡）/ low（最快）
  mp3_bitrate   → MP3音质    64 / 128（默认）/ 192 kbps
  sample_rate   → 采样率     默认 44100 Hz
  normalize     → 文字规范化  true（推荐，数字/英文更稳定）
  streaming     → 流式返回   true（边合成边收，降低首音延迟）
  chunk_length  → 分块长度   100~300，值越小首音越快但质量略降
```

### 💡 三种使用方式对比

```
方式1: 普通模式（等全部合成完才返回）
  你发请求 ──等待3~5秒──► 收到完整音频文件
  适合：离线生成、对延迟不敏感的场景

方式2: HTTP 流式（边合成边收到音频块）
  你发请求 ──1~2秒──► 收到第1块 ──► 收到第2块 ──► ... ──► 完成
  适合：实时对话、网页播放器（边下载边播放）

方式3: WebSocket 流式（最低延迟，< 1秒首音）
  你建立WS连接 ──发文本──► 立刻收到音频流 ──► 持续推送
  适合：数字人实时对话、直播场景
```

### 📝 代码示例

**方式1：普通模式**
```python
import requests

resp = requests.post(
    "https://api.fish.audio/v1/tts",
    json={
        "text": "你好，我是AI陪练数字人，很高兴为您服务。",
        "reference_id": "8a4a6717a4984a70b1413f0d7d60c434",  # 声音模型ID
        "format": "mp3",
        "mp3_bitrate": 128,
        "latency": "normal",
        "normalize": True,
    },
    headers={"Authorization": "Bearer 你的API_KEY"},
    timeout=30,
)
# 保存为文件
with open("output.mp3", "wb") as f:
    f.write(resp.content)
print(f"合成完成，文件大小: {len(resp.content)/1024:.1f} KB")
```

**方式2：HTTP 流式（推荐实时场景）**
```python
import requests, time

t_start = time.time()
first_chunk = True

with requests.post(
    "https://api.fish.audio/v1/tts",
    json={
        "text": "这是流式合成，前端可以边收边播，降低等待感。",
        "reference_id": "8a4a6717a4984a70b1413f0d7d60c434",
        "format": "mp3",
        "latency": "balanced",   # 均衡模式，首音约 1~2 秒
        "streaming": True,        # ⬅ 开启流式
    },
    headers={"Authorization": "Bearer 你的API_KEY"},
    timeout=60,
    stream=True,  # ⬅ requests 也要设置 stream=True
) as resp:
    with open("output_stream.mp3", "wb") as f:
        for chunk in resp.iter_content(chunk_size=4096):
            if chunk:
                if first_chunk:
                    print(f"⚡ 首字节延迟: {time.time()-t_start:.2f}s")
                    first_chunk = False
                f.write(chunk)
                # 这里可以把 chunk 直接推给前端播放器！
```

**方式3：WebSocket 实时流式（最低延迟）**
```python
import asyncio, json, websockets

async def tts_websocket():
    uri = "wss://api.fish.audio/v1/tts/live"
    headers = {"Authorization": "Bearer 你的API_KEY"}

    async with websockets.connect(uri, additional_headers=headers) as ws:

        # 第1步：发送配置（告诉服务器用什么声音、什么格式）
        await ws.send(json.dumps({
            "event": "start",
            "request": {
                "text": "",
                "reference_id": "8a4a6717a4984a70b1413f0d7d60c434",
                "format": "mp3",
                "latency": "low",  # 最低延迟模式
            }
        }))

        # 第2步：发送要合成的文字
        await ws.send(json.dumps({
            "event": "text",
            "text": "WebSocket流式测试，延迟极低，适合实时数字人对话。"
        }))

        # 第3步：发送结束信号
        await ws.send(json.dumps({"event": "stop"}))

        # 第4步：接收音频块（可直接推送给前端）
        audio = b""
        async for msg in ws:
            if isinstance(msg, bytes):
                audio += msg  # 每收到一块就可以播放
            else:
                ev = json.loads(msg)
                if ev.get("event") == "finish":
                    break  # 合成结束

    with open("output_ws.mp3", "wb") as f:
        f.write(audio)
    print(f"完成，大小: {len(audio)/1024:.1f} KB")

asyncio.run(tts_websocket())
# 需要先安装: pip install websockets
```

### 🗣️ 多说话人对话（S2-Pro 功能）

适合合成"两个人对话"的场景，用 `<|speaker:0|>` 标签切换说话人：

```python
resp = requests.post(
    "https://api.fish.audio/v1/tts",
    json={
        # 用标签标注谁在说话
        "text": "<|speaker:0|>您好，请问有什么需要帮助的？"
                "<|speaker:1|>我想了解一下免费电业务怎么申请。"
                "<|speaker:0|>好的，我来帮您介绍。",
        # 传两个声音ID，分别对应 speaker:0 和 speaker:1
        "reference_id": ["声音ID_A", "声音ID_B"],
        "format": "mp3",
    },
    headers={"Authorization": "Bearer 你的API_KEY"},
)
```

---

## 三、ASR 语音转文字

### 🤔 它能做什么？

```
你上传音频文件  →  Fish Speech  →  输出文字 + 时间戳
  output.mp3          识别               "你好，请问..."
                                         [0.0s → 1.2s]
```

### 📮 接口信息

```
POST https://api.fish.audio/v1/asr
Content-Type: multipart/form-data
```

### 📝 代码示例

```python
import requests

with open("audio.mp3", "rb") as f:
    resp = requests.post(
        "https://api.fish.audio/v1/asr",
        headers={"Authorization": "Bearer 你的API_KEY"},
        files={"audio": ("audio.mp3", f, "audio/mpeg")},
        data={
            "language": "zh",              # 语言，zh=中文，en=英文，不填自动识别
            "ignore_timestamps": "false",  # false=返回精确时间戳（稍慢），true=只要文字
        },
        timeout=60,
    )

result = resp.json()
print("识别文字:", result["text"])
print("音频时长:", result["duration"], "秒")
print("分段详情:")
for seg in result["segments"]:
    print(f"  [{seg['start']:.1f}s → {seg['end']:.1f}s]  {seg['text']}")
```

### 📤 返回结果示例

```json
{
  "text": "你好，我是AI陪练数字人，很高兴为您服务。",
  "duration": 3.5,
  "segments": [
    {"text": "你好，我是AI陪练数字人，", "start": 0.0, "end": 2.0},
    {"text": "很高兴为您服务。",         "start": 2.0, "end": 3.5}
  ]
}
```

---

## 四、声音模型管理（克隆声音）

### 🤔 声音模型是什么？

```
上传3~10秒参考音频  →  Fish Speech训练  →  生成"声音模型"
   某人说话的录音           自动学习              得到一个 model_id
                                                  ↓
                                         用这个 ID 就能让AI
                                         用这个人的声音说话
```

### 📋 接口概览

| 操作 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 创建克隆声音 | POST | `/model` | 上传音频文件，生成声音模型 |
| 列出我的声音 | GET | `/model?self=true` | 查看我创建的所有声音 |
| 搜索公开声音 | GET | `/model?title=小美` | 搜索平台上的公开声音 |
| 查看某个声音 | GET | `/model/{model_id}` | 查看声音详情 |
| 修改声音信息 | PATCH | `/model/{model_id}` | 改名字/描述 |
| 删除声音 | DELETE | `/model/{model_id}` | 删除自己创建的声音 |

### 📝 代码示例

**① 创建声音模型（上传参考音频）**
```python
import requests

with open("my_voice_sample.wav", "rb") as f:
    resp = requests.post(
        "https://api.fish.audio/model",
        headers={"Authorization": "Bearer 你的API_KEY"},
        data={
            "title": "我的克隆声音",
            "description": "用于AI陪练数字人",
            "visibility": "private",  # private=仅自己用，public=公开
        },
        files={
            "voices": ("sample.wav", f, "audio/wav"),
            # 可以上传多个音频文件，提高克隆质量
        },
    )
model = resp.json()
print("声音模型ID:", model["_id"])  # 这个ID就是 reference_id
```

**② 查看我的所有声音**
```python
resp = requests.get(
    "https://api.fish.audio/model",
    headers={"Authorization": "Bearer 你的API_KEY"},
    params={
        "self": "true",      # 只看自己的
        "page_size": 20,     # 每页数量
        "page_number": 1,    # 第几页
    },
)
data = resp.json()
print(f"共 {data['total']} 个声音模型:")
for m in data["items"]:
    print(f"  ID: {m['_id']}  名称: {m['title']}")
```

**③ 搜索平台公开声音**
```python
resp = requests.get(
    "https://api.fish.audio/model",
    headers={"Authorization": "Bearer 你的API_KEY"},
    params={
        "title": "客服",     # 按名称搜索
        "language": "zh",    # 只要中文声音
        "sort_by": "task_count",  # 按使用量排序
    },
)
```

**④ 删除声音模型**
```python
resp = requests.delete(
    "https://api.fish.audio/model/你的model_id",
    headers={"Authorization": "Bearer 你的API_KEY"},
)
print("删除成功" if resp.status_code == 200 else "失败")
```

---

## 五、查询账户积分和套餐

### 🤔 为什么需要这个？

每次调用 TTS/ASR 都会消耗积分，这两个接口可以查余额，避免因积分不足导致合成失败。

```
查积分: GET /wallet/self/api-credit  →  {"credit": "1234.56"}
查套餐: GET /wallet/self/package     →  {"type": "pro", ...}
```

### 📝 代码示例

```python
import requests

headers = {"Authorization": "Bearer 你的API_KEY"}

# 查询积分余额
resp = requests.get("https://api.fish.audio/wallet/self/api-credit", headers=headers)
data = resp.json()
print(f"当前积分余额: {data['credit']}")

# 查询套餐信息
resp = requests.get("https://api.fish.audio/wallet/self/package", headers=headers)
data = resp.json()
print(f"当前套餐: {data.get('type', '无')}，总量: {data.get('total')}")
```

---

## 六、延迟模式与音频格式速查

### ⚡ 延迟模式

```
latency="normal"    质量最好，首音约 3~5 秒    适合：离线生成
latency="balanced"  质量好，首音约 1~2 秒     适合：实时对话 ✅推荐
latency="low"       质量略低，首音 < 1 秒     适合：极低延迟场景
```

### 🎵 音频格式

```
format="mp3"   → 兼容性最好，适合网页播放        约 160KB/10秒
format="wav"   → 无损音质，文件大               约 1.7MB/10秒
format="pcm"   → 裸数据，适合直接送入播放缓冲区  约 1.7MB/10秒
format="opus"  → 高压缩，适合 WebRTC/实时通信   约  30KB/10秒
```

---

## 七、.env 配置

在项目根目录 `.env` 文件中配置：

```ini
# Fish Speech TTS（当 TTS_USE_SOUTHGRID=false 且 TTS_USE_LOCAL=false 时自动使用）
FISH_API_URL=https://api.fish.audio/v1/tts
FISH_API_KEY=<FISH_API_KEY>
FISH_DEFAULT_VOICE=8a4a6717a4984a70b1413f0d7d60c434

TTS_USE_SOUTHGRID=false
TTS_USE_LOCAL=false
```

---

## 八、运行测试用例

```bash
# 运行全部测试（Case 1~5）
python scripts/test_fish_speech_full.py

# 只跑指定用例
python scripts/test_fish_speech_full.py --cases 1,2

# Case 6 WebSocket 需额外安装依赖
pip install websockets
python scripts/test_fish_speech_full.py --cases 6
```

| Case | 测什么 | 新学到的东西 |
|------|--------|-------------|
| 1 | 基础非流式 TTS | 最简单的用法 |
| 2 | HTTP 流式（streaming=true） | 首字节延迟优化 |
| 3 | 多种 format/latency 组合 | 找到适合自己的配置 |
| 4 | 多说话人对话 | `<\|speaker:0\|>` 标签用法 |
| 5 | ASR 语音识别 | 把合成的音频再识别回文字 |
| 6 | WebSocket 流式 | 最低延迟方案 |

---

## 九、常见问题

**Q: 积分不够怎么办？**  
A: 先用 `/wallet/self/api-credit` 查余额，然后去 https://fish.audio/app 充值。

**Q: 声音不自然怎么办？**  
- 换 `latency="normal"` 获得最高质量
- 参考音频尽量 3~30 秒，安静无噪音
- 开启 `normalize=true` 让数字/英文更自然

**Q: 第一声为什么要等很久？**  
- 改用 `latency="balanced"` 或 `"low"`
- 开启 `streaming=true` 边合成边播放
- 极致低延迟用 WebSocket（Case 6）

**Q: 多说话人不工作？**  
A: 需要账号开通 S2-Pro 功能，普通账号不支持。

---

## 十、Curl 速查（全部 10 个 API）

> API Key: `<FISH_API_KEY>`  |  默认声音: `8a4a6717a4984a70b1413f0d7d60c434`

### 💰 Wallet — 账户查询

```bash
# 查询 API 积分余额
curl -X GET "https://api.fish.audio/wallet/self/api-credit" \
  -H "Authorization: Bearer <FISH_API_KEY>"

# 查询当前套餐信息
curl -X GET "https://api.fish.audio/wallet/self/package" \
  -H "Authorization: Bearer <FISH_API_KEY>"
```

---

### 🎙️ Voice Models — 声音模型管理

```bash
# 搜索/列出声音模型（公开 + 自己的）
curl -X GET "https://api.fish.audio/model?self=true&page_size=20" \
  -H "Authorization: Bearer <FISH_API_KEY>"

# 按关键词搜索公开声音
curl -X GET "https://api.fish.audio/model?title=客服&language=zh&sort_by=task_count" \
  -H "Authorization: Bearer <FISH_API_KEY>"

# 创建声音克隆模型（上传参考音频）
curl -X POST "https://api.fish.audio/model" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -F "title=我的克隆声音" \
  -F "description=用于AI陪练" \
  -F "visibility=private" \
  -F "voices=@/path/to/sample.wav;type=audio/wav"

# 获取某个声音模型详情
curl -X GET "https://api.fish.audio/model/YOUR_MODEL_ID" \
  -H "Authorization: Bearer <FISH_API_KEY>"

# 修改声音模型名称/描述
curl -X PATCH "https://api.fish.audio/model/YOUR_MODEL_ID" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"title": "新名字", "description": "新描述"}'

# 删除声音模型
curl -X DELETE "https://api.fish.audio/model/YOUR_MODEL_ID" \
  -H "Authorization: Bearer <FISH_API_KEY>"
```

---

### 🔊 TTS — 文字转语音

```bash
# 基础 TTS（保存为 mp3 文件）
curl -X POST "https://api.fish.audio/v1/tts" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好，我是AI陪练数字人，很高兴为您服务。",
    "reference_id": "8a4a6717a4984a70b1413f0d7d60c434",
    "format": "mp3",
    "mp3_bitrate": 128,
    "latency": "normal",
    "normalize": true
  }' \
  --output output.mp3

# 流式 TTS（边合成边写入，降低首音延迟）
curl -X POST "https://api.fish.audio/v1/tts" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这是流式合成测试，前端可以边接收边播放。",
    "reference_id": "8a4a6717a4984a70b1413f0d7d60c434",
    "format": "mp3",
    "latency": "balanced",
    "streaming": true
  }' \
  --output output_stream.mp3

# TTS 输出 WAV 格式
curl -X POST "https://api.fish.audio/v1/tts" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "WAV 格式无损输出测试。",
    "reference_id": "8a4a6717a4984a70b1413f0d7d60c434",
    "format": "wav",
    "sample_rate": 22050,
    "latency": "low"
  }' \
  --output output.wav

# 多说话人对话（S2-Pro）
curl -X POST "https://api.fish.audio/v1/tts" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "<|speaker:0|>您好，请问有什么需要帮助的？<|speaker:1|>我想了解免费电业务。",
    "reference_id": ["8a4a6717a4984a70b1413f0d7d60c434", "8a4a6717a4984a70b1413f0d7d60c434"],
    "format": "mp3"
  }' \
  --output dialogue.mp3
```

---

### 🎤 ASR — 语音转文字

```bash
# 语音识别（返回文字 + 时间戳）
curl -X POST "https://api.fish.audio/v1/asr" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -F "audio=@/path/to/audio.mp3" \
  -F "language=zh" \
  -F "ignore_timestamps=false"

# 只要文字，不要时间戳（速度更快）
curl -X POST "https://api.fish.audio/v1/asr" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -F "audio=@/path/to/audio.mp3" \
  -F "language=zh" \
  -F "ignore_timestamps=true"
```

---

### 🔗 一键测试（组合使用）

```bash
# 先合成语音，再识别回文字，验证 TTS+ASR 全流程
API_KEY="<FISH_API_KEY>"
VOICE_ID="8a4a6717a4984a70b1413f0d7d60c434"

# Step 1: 合成
curl -s -X POST "https://api.fish.audio/v1/tts" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"你好，这是一个TTS加ASR全流程测试。\",\"reference_id\":\"8a4a6717a4984a70b1413f0d7d60c434\",\"format\":\"mp3\"}" \
  --output /tmp/tts_test.mp3

# Step 2: 识别
curl -s -X POST "https://api.fish.audio/v1/asr" \
  -H "Authorization: Bearer <FISH_API_KEY>" \
  -F "audio=@/tmp/tts_test.mp3" \
  -F "language=zh" | python3 -c "import sys,json; d=json.load(sys.stdin); print('识别结果:', d['text'])"
```
