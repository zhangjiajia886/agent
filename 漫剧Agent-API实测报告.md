# 漫剧 Agent API 实测报告

> 基于仙侠 4 格漫剧实际生成效果的对比测试
> 测试时间：2026-04-30
> 测试环境：硅基流动 SiliconFlow API + 火山引擎/即梦 API

---

## 一、测试设计

### 测试场景
同一角色（黑发少年，白色长袍，青色长剑）在 4 个不同场景中的表现：
1. **山巅持剑** — 日出云雾中立于山巅
2. **竹林夜战** — 月夜竹林中与暗影妖魔战斗
3. **水晶洞修炼** — 洞穴中盘腿打坐，灵气环绕
4. **乘鹤飞行** — 骑仙鹤俯瞰山河

### 评估维度
- **角色一致性**：同一角色在不同场景中外观是否一致
- **漫画风格**：是否呈现清晰的漫画/动漫画风
- **场景表现力**：是否准确表现指定场景
- **中文 Prompt 理解**：是否准确理解中文描述
- **速度**：出图耗时
- **成本**：每张图费用

---

## 二、测试结果

### 2.1 硅基流动 — Kolors（快手可图）

| 格 | 耗时 | 大小 | 评价 |
|----|------|------|------|
| 第1格 山巅持剑 | 2.9s | 1180KB | 水墨画风，背影构图，意境好 |
| 第2格 竹林夜战 | 2.9s | 1274KB | 氛围到位，但角色面部不可见 |
| 第3格 水晶洞修炼 | 3.2s | 1469KB | 唯一正脸，但面部风格与其他格差异大 |
| 第4格 乘鹤飞行 | 3.1s | 1273KB | 构图好，人鹤比例佳 |

**总评**：
- 画风：⭐⭐⭐⭐ 水墨+数字绘画，偏写实，适合封面/海报
- 角色一致性：⭐⭐⭐ 服装一致，但面部/体型每格不同
- 漫画适配：⭐⭐⭐ 更像插画而非漫画分镜
- 速度：⭐⭐⭐⭐⭐ 平均 3.0s/张（最快）
- 图片路径：`/tmp/comic_api_test/siliconflow/kolors/`

---

### 2.2 硅基流动 — Qwen-Image（通义图片生成）⭐ 最佳

| 格 | 耗时 | 大小 | 评价 |
|----|------|------|------|
| 第1格 山巅持剑 | 13.7s | 863KB | **纯正漫画风**，角色设计清晰，青色腰带+发冠 |
| 第2格 竹林夜战 | 23.7s | 1028KB | **自带分格线！** 动作感极强，暗影妖设计到位 |
| 第3格 水晶洞修炼 | 17.0s | 922KB | 闭眼打坐，水晶+灵光效果美，**角色高度一致** |
| 第4格 乘鹤飞行 | 9.0s | 956KB | 骑鹤俯瞰，角色+鹤的构图完美 |

**总评**：
- 画风：⭐⭐⭐⭐⭐ **纯正漫画/动漫风格**，线条清晰，配色鲜明
- 角色一致性：⭐⭐⭐⭐⭐ **4 格角色几乎完全一致**（发型、服装、配色、体型）
- 漫画适配：⭐⭐⭐⭐⭐ 天然适合漫画分镜，第2格甚至自动生成分格线
- 速度：⭐⭐⭐ 平均 15.9s/张（可接受）
- 中文理解：⭐⭐⭐⭐⭐ 完美理解"仙侠漫画风格"等中文描述
- 图片路径：`/tmp/comic_api_test/siliconflow/qwen_image/`

---

### 2.3 火山引擎 — 即梦（Jimeng v2.1 Large）

| 格 | 耗时 | 大小 | 评价 |
|----|------|------|------|
| 第1格 山巅持剑 | 8.9s | 798KB | **画质最高**，角色精致，山河壮阔，青色配饰+发冠 |
| 第2格 竹林夜战 | 7.8s | 817KB | 暗影妖设计出色！但腰带变红色（角色不一致） |
| 第3格 水晶洞修炼 | 7.5s | 813KB | 水晶洞极美，角色面部一致性好 |
| 第4格 乘鹤飞行 | 8.1s | 936KB | 山河构图震撼，但多出一个人物 |

**总评**：
- 画风：⭐⭐⭐⭐⭐ 顶级插画品质，光影细节丰富
- 角色一致性：⭐⭐⭐⭐ 面部一致性好，但服装配色每格有变化（腰带颜色不同）
- 漫画适配：⭐⭐⭐⭐ 偏高质量插画风，适合竖屏漫剧
- 速度：⭐⭐⭐⭐ 平均 8.1s/张
- 中文理解：⭐⭐⭐⭐⭐ 完美理解仙侠场景
- 图片路径：`/tmp/comic_api_test/jimeng/`
- API 调用：火山引擎 V4 签名 + `req_key=jimeng_high_aes_general_v21_L`

---

### 2.4 其他模型测试结果

| 模型 | 状态 | 说明 |
|------|------|------|
| FLUX.1-schnell | ❌ Model disabled | 硅基流动免费账户被限制 |
| FLUX.1-dev | ❌ Model disabled | 同上 |
| SD3.5-large | ❌ Model disabled | 同上 |

---

## 三、对比总结

```
维度            Kolors          Qwen-Image       即梦 v2.1L       ComfyUI(现有)
────────────────────────────────────────────────────────────────────────────
画质            ⭐⭐⭐⭐         ⭐⭐⭐⭐⭐          ⭐⭐⭐⭐⭐         ⭐⭐⭐⭐⭐
漫画风格        ⭐⭐⭐           ⭐⭐⭐⭐⭐          ⭐⭐⭐⭐           ⭐⭐⭐⭐
角色一致性      ⭐⭐⭐           ⭐⭐⭐⭐⭐          ⭐⭐⭐⭐           ⭐⭐⭐⭐(IPAdapter)
速度            ⭐⭐⭐⭐⭐(3s)   ⭐⭐⭐(16s)        ⭐⭐⭐⭐(8s)       ⭐⭐⭐(10-60s)
成本            ⭐⭐⭐⭐⭐(免费)  ⭐⭐⭐⭐            ⭐⭐⭐⭐           ⭐⭐⭐(GPU租赁)
集成难度        🟢 极低          🟢 极低            � 中(V4签名)    �🔴 已完成但复杂
中文理解        ⭐⭐⭐⭐         ⭐⭐⭐⭐⭐          ⭐⭐⭐⭐⭐         ⭐⭐⭐
API 稳定性      ⭐⭐⭐⭐⭐        ⭐⭐⭐⭐⭐          ⭐⭐⭐⭐⭐         ⭐⭐⭐(需运维)
────────────────────────────────────────────────────────────────────────────
综合推荐        快速草图         🏆 首选(漫剧)     画质首选          精细控制时用
```

---

## 四、Agent 集成方案（推荐）

### 核心方案：Qwen-Image（硅基流动）

```
用户输入故事 → Agent(LLM) → 拆解分镜+角色设定
                              ↓
                    生成角色描述（角色圣经）
                              ↓
                    逐格调用 Qwen-Image API
                    （每格 prompt 包含完整角色描述）
                              ↓
                    4格图片 → 拼合漫画页 → TTS配音 → 输出
```

### API 调用方式

```python
import httpx

def generate_comic_panel(prompt: str, size: str = "768x1024") -> bytes:
    """通过硅基流动调用 Qwen-Image 生成漫画面板"""
    url = "https://api.siliconflow.cn/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "Qwen/Qwen-Image",
        "prompt": prompt,
        "image_size": size,
        "num_inference_steps": 20,
    }
    
    resp = httpx.post(url, headers=headers, json=payload, timeout=120)
    data = resp.json()
    img_url = data["images"][0]["url"]
    return httpx.get(img_url).content
```

### Agent 工具定义

```python
{
    "name": "qwen_image_gen",
    "description": "使用 Qwen-Image 生成漫画风格图片。适合漫剧分镜、角色插画。角色一致性极好。",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图片描述。必须包含：1)风格(如'中国仙侠漫画风格') 2)角色完整描述(发型/服装/配色) 3)场景 4)动作/表情 5)构图指示"
            },
            "size": {
                "type": "string",
                "enum": ["768x1024", "1024x768", "1024x1024"],
                "description": "图片尺寸。竖版分镜用768x1024，横版用1024x768"
            }
        },
        "required": ["prompt"]
    }
}
```

---

## 五、即梦 API 调用要点（已解决）

### 认证排查过程
- 初始 401 错误原因：`req_key` 用错（`high_aes_general_v20_L` → 无权限）
- 正确 `req_key`：**`jimeng_high_aes_general_v21_L`** ✅
- SK 格式：**直接使用原始值**（不需要 base64 解码）
- Content-Type：必须是 `application/json;charset=utf-8`

### 即梦 API 调用方式

```python
import hashlib, hmac, json, httpx
from datetime import datetime, timezone
from urllib.parse import quote

def jimeng_generate(prompt, ak, sk, width=768, height=1024):
    """即梦文生图 API"""
    host = "visual.volcengineapi.com"
    body = json.dumps({
        "req_key": "jimeng_high_aes_general_v21_L",
        "prompt": prompt,
        "width": width, "height": height,
        "seed": -1, "return_url": True,
    }).encode()
    
    # V4 签名（见完整签名函数）
    headers = sign_v4(ak, sk, host, body)
    url = f"https://{host}/?Action=CVProcess&Version=2022-08-31"
    
    resp = httpx.post(url, headers=headers, content=body, timeout=120)
    data = resp.json()
    if data.get("code") == 10000:
        return base64.b64decode(data["data"]["binary_data_base64"][0])
    raise Exception(f"Jimeng error: {data}")
```

---

## 六、下一步行动

| 优先级 | 行动 | 预估工时 |
|--------|------|---------|
| 🔴 高 | 在 Agent 中新增 `qwen_image_gen` 工具（漫画首选） | 2h |
| 🔴 高 | 在 Agent 中新增 `jimeng_image_gen` 工具（画质首选） | 2h |
| 🔴 高 | 新增 `kolors_image_gen` 工具（快速草图模式） | 1h |
| 🟡 中 | 实现"角色圣经"机制（LLM 先生成角色描述，后续分镜复用） | 2h |
| 🟡 中 | 硅基流动 Wan2.2 文生视频/图生视频测试 | 1h |
| 🟢 低 | 硅基流动 Qwen-Image-Edit 图片编辑测试 | 0.5h |
| 🟢 低 | 充值解锁 FLUX 模型测试 | 0.5h |
