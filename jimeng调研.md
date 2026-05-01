# 即梦 Jimeng API 对接调研与 TTSApp/漫剧 Agent 集成方案

> 生成时间：2026-04-30  
> 目标：将现有 `jimeng` 分析、实测结果和接入经验整理成可落地的 API 对接文档，并设计迁移到 TTSApp 页面与漫剧 Agent 的实现方案。

---

## 1. 结论摘要

### 1.1 是否值得接入

**值得接入。** 即梦 Jimeng 在当前实测中表现为“国内高画质、中文理解强、速度稳定”的图像生成通道，适合作为 TTSApp 漫剧创作链路中的高质量图片生成工具。

### 1.2 推荐定位

| 使用场景 | 推荐程度 | 说明 |
|---|---:|---|
| 竖屏漫剧分镜图 | 高 | 画质高、中文 Prompt 理解好，适合生成单格画面 |
| 角色/场景概念图 | 高 | 光影、细节、氛围表现优于普通开源模型 |
| 高质量插画封面 | 高 | 风格偏插画，适合封面和关键视觉 |
| 强角色一致性连续漫画 | 中 | 面部一致性较好，但服装配色可能漂移，需要“角色圣经”策略约束 |
| 低成本快速草图 | 中 | 速度约 8 秒/张，成本与额度取决于火山引擎账号，不适合作为唯一草图通道 |
| 本地可控复杂工作流 | 低 | 不如 ComfyUI 适合精细控制、多节点工作流、局部修复链路 |

### 1.3 最终建议

- **重要修正**：即梦当前不是单一 `CVProcess + req_key` 老接口，而是一组官方正式产品接口。本文中 `CVProcess` 只作为“历史已测通路/兼容通路”记录，正式接入应优先按火山官方即梦 AI 文档接入图片 4.6、图片 4.0、图生图、视频生成、动作模仿等接口。
- **接入形态**：优先做成后端 `tool`，内化到漫剧 Agent；同时在 TTSApp 页面提供独立“即梦图片/视频工具箱”面板。
- **不是优先 MCP**：当前需求是产品内稳定调用，不是跨应用开放协议，MCP 会增加部署和权限复杂度。
- **Skill 与 Tool 的关系**：
  - `Tool` 负责真实 API 调用、鉴权、落盘、返回图片 URL。
  - `Skill` 负责提示词工程、角色圣经、分镜复用、失败重试策略。
  - 后续如需给外部 Agent/IDE 复用，再把同一服务包装为 MCP。

### 1.4 官方接口体系修正

用户提供的官方文档入口：

```text
https://www.volcengine.com/docs/85621/2201579?lang=zh
```

该链接实际标题为“动作模仿2.0-接口文档--即梦AI-火山引擎”。从页面左侧目录与搜索索引可确认，即梦 AI 已包含一组正式接口，而不是单个文生图接口。

下面是按当前火山文档索引整理出的“即梦 API 清单”。其中带明确 URL 的条目已经从搜索索引确认；未拿到 URL 的条目是从同一目录索引确认存在，后续需要在浏览器左侧目录中点开补 ID。

| 官方能力 | 文档链接 | 对 TTSApp/漫剧 Agent 的价值 |
|---|---|---|
| 快速入门 | `https://www.volcengine.com/docs/85621/1995636?lang=zh` | 总入口，确认 AK/SK、调用方式和开通流程 |
| 即梦AI-图片生成4.6 | `https://www.volcengine.com/docs/85621/2275082?lang=zh` | 最新图片生成主通道，优先作为高画质文生图工具验证 |
| 即梦AI-图片生成4.0 | `https://www.volcengine.com/docs/85621/1817045?lang=zh` | 稳定图片生成通道，可作为 4.6 备用或对比 |
| 即梦AI-图片生成4.0 SP | `https://www.volcengine.com/docs/85621/1863351` | 图片 4.0 特殊版本/专用通道，需要确认账号权限和参数差异 |
| 即梦AI-素材提取(POD按需定制) | `https://www.volcengine.com/docs/85621/1537648` | 商品/POD 素材抽取，偏电商素材工作流 |
| 即梦AI-素材提取(商品提取) | `https://www.volcengine.com/docs/85621/2129114?lang=zh` | 商品主体/素材提取，可用于商品图、带货短视频素材准备 |
| 即梦AI-交互编辑 inpainting | `https://www.volcengine.com/docs/85621/1976207` | 局部重绘、修图、漫画画面修复 |
| 即梦AI-智能超清 | `https://www.volcengine.com/docs/85621/2164806` | 图片超分，可替代部分 ComfyUI 超分工作流 |
| 即梦文生图3.1 | `https://www.volcengine.com/docs/85621/1756900?lang=zh` | 老一代文生图通道，可用于兼容测试 |
| 即梦文生图3.0 | `https://www.volcengine.com/docs/85621/1616429?lang=zh` | 老一代文生图通道，可用于成本/效果对比 |
| 即梦图生图3.0智能参考 | `https://www.volcengine.com/docs/85621/1747301?lang=zh` | 角色一致性、参考图生成、形象延展的关键接口 |
| 即梦AI-AI营销商品图3.0 | `https://www.volcengine.com/docs/85621/1956024` | 商品营销图生成，适合电商图、推广素材、商品短剧素材 |
| 即梦AI-视频生成3.0 Pro | `https://www.volcengine.com/docs/85621/1777001?lang=zh` | 高质量视频生成，适合漫剧关键动态镜头 |
| 即梦AI-视频生成3.0 720P | `https://www.volcengine.com/docs/85621/1792710?lang=zh` | 成本较低的视频生成通道 |
| 即梦AI-视频生成3.0 1080P | `https://www.volcengine.com/docs/85621/1792711?lang=zh` | 高清视频生成通道 |
| 即梦AI-视频生成3.0 720P-图生视频-运镜 | `https://www.volcengine.com/docs/85621/1785201?lang=zh` | 图生视频镜头运动控制，适合漫画关键帧动态化 |
| 即梦AI-视频生成3.0 720P-图生视频-首帧 | `https://www.volcengine.com/docs/85621/1785204` | 以首帧控制视频起始画面 |
| 即梦AI-视频生成3.0 720P-图生视频-首尾帧 | `https://www.volcengine.com/docs/85621/1791184` | 通过首尾帧控制镜头变化 |
| 即梦AI-视频生成3.0 1080P-图生视频-首尾帧 | `https://www.volcengine.com/docs/85621/1802721?lang=zh` | 高清首尾帧视频生成 |
| 即梦AI-视频生成S2.0 Pro（陆续下线中） | 待从目录补全 | 老视频接口，除非兼容历史项目，不建议新接入 |
| 即梦AI-文生视频S2.0Pro（陆续下线中） | 待从目录补全 | 老文生视频接口，不建议作为新主通道 |
| 即梦AI-图生视频S2.0Pro（陆续下线中） | 待从目录补全 | 老图生视频接口，不建议作为新主通道 |
| 动作模仿 | `https://www.volcengine.com/docs/85621/1798351` | 旧动作模仿接口，可与 2.0 对比 |
| 动作模仿2.0 | `https://www.volcengine.com/docs/85621/2201579?lang=zh` | 角色动作迁移、数字人/漫剧动作控制 |
| 数字人快速模式 OmniHuman1.0-产品介绍 | `https://www.volcengine.com/docs/85621/1810468` | 数字人链路总说明 |
| 数字人快速模式-调用步骤1：主体识别 | `https://www.volcengine.com/docs/85621/1810469?lang=zh` | 数字人主体识别 |
| 数字人快速模式-调用步骤2：视频生成 | `https://www.volcengine.com/docs/85621/1810471?lang=zh` | 数字人口播/视频生成，与 TTS 可结合 |
| 视频翻译2.0 | `https://www.volcengine.com/docs/85621/2189006?lang=zh` | 视频翻译/本地化能力，适合成片多语言发布 |
| 小云雀智能生视频 Agent | `https://www.volcengine.com/docs/85621/2283633?lang=zh`、`https://www.volcengine.com/docs/85621/2359610?lang=zh`、`https://www.volcengine.com/docs/85621/2359611?lang=zh` | 更高层的视频 Agent 能力，可作为后续“成片生成”工具 |
| 小云雀营销成片 Agent | 待从目录补全 | 营销短视频成片 Agent，适合电商/商品推广链路 |

---

## 2. 资料来源与现有分析

### 2.1 项目内已有材料

| 材料 | 路径 | 价值 |
|---|---|---|
| 漫剧 Agent API 实测报告 | `漫剧Agent-API实测报告.md` | 记录即梦与硅基流动等模型对比、认证坑点、成功 req_key |
| 即梦 4 格输出样图 | `backend/comic_api_test/jimeng/` | 已生成 4 张实测图，可用于主观质量复核 |
| 历史测试脚本 | `/private/tmp/test_jimeng_comic.py` | 含完整 V4 签名、4 格生成逻辑、图片下载/保存流程 |
| 历史排查脚本 | `/private/tmp/test_jimeng_full_debug.py` | 验证不同 host/req_key 组合，定位 401 与成功参数 |
| Agent 工具注册入口 | `backend/app/api/v1/comic_agent.py` | `SEED_TOOLS` 定义工具 schema 和 system prompt |
| Agent 工具执行器 | `backend/app/core/comic_chat_agent/tool_executor.py` | `TOOL_EXECUTORS` 分发真实工具调用 |
| 前端 Agent 页面 | `frontend/src/views/comic-agent/ComicAgentView.vue` | 工具列表、模型服务配置、WebSocket 对话入口 |
| 前端路由 | `frontend/src/router/index.ts` | 已有 `/comic`、`/comic-agent`、`/workflow` 页面 |

### 2.2 已验证关键点与适用范围

- **已实测通路**：`visual.volcengineapi.com` + `Action=CVProcess` + `Version=2022-08-31` + `req_key=jimeng_high_aes_general_v21_L`。
- **适用范围**：该通路只能证明旧式图像生成链路在当前账号可用，不能代表即梦 AI 全量官方接口。
- **正式接入优先级**：应先验证官方“即梦AI-图片生成4.6-接口文档”，再验证图生图、视频生成、动作模仿、智能超清等接口。
- **签名方式**：火山引擎接口通常使用 AK/SK 与 V4 签名；具体 host、path、Action、Version、请求体字段必须以对应官方接口文档为准。
- **Content-Type**：历史 `CVProcess` 通路必须使用 `application/json;charset=utf-8`；其他官方新接口以各自文档要求为准。
- **SK 使用方式**：历史测试中 SK 直接使用原始字符串，不需要 base64 解码；正式接口仍应按火山 AK/SK 标准处理。

---

## 3. API 对接文档

### 3.1 正式接入原则

即梦已开通全量 API 后，不应只封装一个 `jimeng_image_gen`。更合理的做法是设计一个统一 `JimengProvider`，内部按能力分发到不同官方接口：

```text
JimengProvider
  ├── generate_image_46()       # 图片生成4.6，主推文生图
  ├── generate_image_40()       # 图片生成4.0，备用/对照
  ├── generate_image_40_sp()    # 图片生成4.0 SP，专用通道
  ├── text_to_image_31()        # 文生图3.1，兼容通道
  ├── image_to_image_30()       # 图生图3.0智能参考，角色一致性关键
  ├── inpaint_image()           # 交互编辑 inpainting
  ├── upscale_image()           # 智能超清
  ├── extract_pod_material()    # 素材提取 POD 按需定制
  ├── extract_product_material()# 素材提取 商品提取
  ├── generate_marketing_image()# AI 营销商品图3.0
  ├── generate_video_30_pro()   # 视频生成3.0 Pro
  ├── generate_video_720p()
  ├── generate_video_1080p()
  ├── generate_video_i2v_camera_720p()
  ├── generate_video_i2v_first_frame_720p()
  ├── generate_video_i2v_first_last_frame_720p()
  ├── generate_video_i2v_first_last_frame_1080p()
  ├── motion_mimic()            # 动作模仿旧版
  ├── motion_mimic_20()         # 动作模仿2.0
  ├── digital_human_detect()    # 数字人主体识别
  ├── digital_human_generate()  # 数字人视频生成
  ├── translate_video_20()      # 视频翻译2.0
  ├── xiaoyunque_video_agent()  # 小云雀智能生视频 Agent
  └── xiaoyunque_marketing_agent() # 小云雀营销成片 Agent
```

Agent 层不直接暴露所有底层接口细节，而是暴露语义化工具：

| Agent 工具 | 底层优先接口 | 用途 |
|---|---|---|
| `jimeng_generate_image` | 图片生成4.6 → 图片生成4.0 → 文生图3.1 | 文生图、封面、分镜关键帧 |
| `jimeng_reference_image` | 图生图3.0智能参考 | 参考图生图、角色一致性 |
| `jimeng_edit_image` | 交互编辑 inpainting | 局部修改、修复画面 |
| `jimeng_upscale_image` | 智能超清 | 图片放大和增强 |
| `jimeng_generate_video` | 视频生成3.0 Pro / 720P / 1080P | 文生视频或图生视频 |
| `jimeng_motion_mimic` | 动作模仿2.0 | 让角色模仿参考动作 |
| `jimeng_product_material` | 素材提取 / AI营销商品图3.0 | 商品素材提取、商品营销图生成 |
| `jimeng_digital_human` | 数字人快速模式 | 主体识别 + 数字人视频生成 |
| `jimeng_video_translate` | 视频翻译2.0 | 成片多语言化 |
| `jimeng_video_agent` | 小云雀智能生视频 / 营销成片 Agent | 更高层的一键成片 |

### 3.2 API 落地优先级

即梦接口很多，但不应该一口气全部做进 Agent。建议按 TTSApp 当前漫剧链路分三层：

| 优先级 | 能力 | 具体接口 | 是否第一阶段实现 | 原因 |
|---|---|---|---|---|
| P0 | 高质量图片生成 | 图片生成4.6、图片生成4.0、文生图3.1 | 是 | 替代/补充 ComfyUI 与 Qwen-Image，是漫剧关键帧核心能力 |
| P0 | 角色一致性/参考图 | 图生图3.0智能参考 | 是 | 解决连续分镜角色漂移问题 |
| P0 | 局部编辑 | 交互编辑 inpainting | 是 | 分镜返修高频需求 |
| P0 | 图片增强 | 智能超清 | 是 | 生成图进入视频前通常需要增强 |
| P0 | 视频生成 | 视频生成3.0 Pro、720P、1080P、图生视频首帧/首尾帧/运镜 | 是 | 漫剧从关键帧到动态镜头的核心链路 |
| P0 | 动作控制 | 动作模仿2.0 | 是 | 角色动作迁移，比普通图生视频更适合剧情动作 |
| P1 | 商品图链路 | 素材提取、AI营销商品图3.0 | 否 | 对商品短剧/带货视频有价值，但不是普通漫剧第一优先级 |
| P1 | 数字人 | 数字人快速模式 OmniHuman1.0 | 否 | 可与 TTS 结合做口播数字人，属于独立产品线 |
| P1 | 视频翻译 | 视频翻译2.0 | 否 | 发布与本地化阶段能力，不是生成主链路 |
| P2 | 小云雀 Agent | 智能生视频 Agent、营销成片 Agent | 否 | 高层黑盒 Agent，适合后续“一键成片”，不适合先替代底层可控工具 |
| P3 | 下线接口 | S2.0 Pro 文生/图生视频 | 否 | 官方标记陆续下线，不建议新接入 |

### 3.3 历史兼容通路：CVProcess

```text
POST https://visual.volcengineapi.com/?Action=CVProcess&Version=2022-08-31
```

该通路来自历史实测，只用于保留可复现经验。正式开发时应把它标记为 `legacy_cvprocess`，不要作为唯一即梦接入方案。

### 3.4 请求头

| Header | 必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | V4 签名生成结果 |
| `X-Date` | 是 | UTC 时间，格式 `YYYYMMDDTHHMMSSZ` |
| `Host` | 是 | `visual.volcengineapi.com` |
| `Content-Type` | 是 | `application/json;charset=utf-8`，仅针对历史 `CVProcess` 通路 |

### 3.5 请求体

```json
{
  "req_key": "jimeng_high_aes_general_v21_L",
  "prompt": "中国仙侠漫画风格，一个黑发少年身穿白色长袍，手持青色长剑，站在云雾缭绕的山巅，日出时分。线条清晰，色彩鲜明，漫画分镜构图。",
  "width": 768,
  "height": 1024,
  "seed": -1,
  "return_url": true
}
```

### 3.6 参数说明

| 参数 | 类型 | 必填 | 推荐值 | 说明 |
|---|---|---:|---|---|
| `req_key` | string | 是 | `jimeng_high_aes_general_v21_L` | 当前已验证可用的即梦 v2.1 Large 模型通道 |
| `prompt` | string | 是 | 中文即可 | 即梦中文理解很好，建议保留中文创作表达 |
| `width` | integer | 是 | `768` | 竖屏漫剧推荐宽度 |
| `height` | integer | 是 | `1024` | 竖屏漫剧推荐高度 |
| `seed` | integer | 否 | `-1` | `-1` 表示随机种子 |
| `return_url` | boolean | 否 | `true` | 返回 URL；实际响应也可能含 base64，需要两种都兼容 |

### 3.7 响应结构

成功时业务码为：

```json
{
  "code": 10000,
  "data": {
    "binary_data_base64": ["..."],
    "image_urls": ["..."]
  },
  "message": "Success"
}
```

实际调用中需要同时兼容：

- **`data.binary_data_base64`**：base64 图片数据，解码后保存为 PNG。
- **`data.image_urls`**：图片 URL，需要二次 GET 下载后保存。

### 3.8 历史兼容通路最小 Python 调用流程

```python
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import quote

import httpx


def sign_v4(ak: str, sk: str, host: str, body_bytes: bytes) -> dict:
    now = datetime.now(timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = now.strftime("%Y%m%d")
    service = "cv"
    region = "cn-north-1"
    content_type = "application/json;charset=utf-8"

    query = {"Action": "CVProcess", "Version": "2022-08-31"}
    canonical_query = "&".join(
        f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}"
        for k, v in sorted(query.items())
    )
    canonical_headers = f"content-type:{content_type}\nhost:{host}\nx-date:{x_date}\n"
    signed_headers = "content-type;host;x-date"
    payload_hash = hashlib.sha256(body_bytes).hexdigest()
    canonical_request = f"POST\n/\n{canonical_query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = (
        f"HMAC-SHA256\n{x_date}\n{scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )

    def hmac_sha256(key, msg: str) -> bytes:
        return hmac.new(key if isinstance(key, bytes) else key.encode(), msg.encode(), hashlib.sha256).digest()

    signing_key = hmac_sha256(sk, short_date)
    signing_key = hmac_sha256(signing_key, region)
    signing_key = hmac_sha256(signing_key, service)
    signing_key = hmac_sha256(signing_key, "request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    return {
        "Authorization": f"HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={signed_headers}, Signature={signature}",
        "X-Date": x_date,
        "Host": host,
        "Content-Type": content_type,
    }


def jimeng_generate(prompt: str, ak: str, sk: str, width: int = 768, height: int = 1024) -> bytes:
    host = "visual.volcengineapi.com"
    body = json.dumps({
        "req_key": "jimeng_high_aes_general_v21_L",
        "prompt": prompt,
        "width": width,
        "height": height,
        "seed": -1,
        "return_url": True,
    }).encode()

    headers = sign_v4(ak, sk, host, body)
    url = f"https://{host}/?Action=CVProcess&Version=2022-08-31"

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, headers=headers, content=body)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 10000:
            raise RuntimeError(f"Jimeng error: {data}")

        payload = data.get("data") or {}
        b64_list = payload.get("binary_data_base64") or []
        if b64_list:
            return base64.b64decode(b64_list[0])

        urls = payload.get("image_urls") or []
        if urls:
            return client.get(urls[0], timeout=60).content

        raise RuntimeError(f"Jimeng response has no image payload: {data}")
```

### 3.9 鉴权坑点

| 问题 | 表现 | 原因 | 解决方案 |
|---|---|---|---|
| 旧 req_key 返回 401 | `code=50400` / `Access Denied` | 账号没有 `high_aes_general_v20_L` 权限 | 使用 `jimeng_high_aes_general_v21_L` |
| Content-Type 不一致 | 签名或鉴权失败 | 签名中的 canonical headers 与实际请求头不一致 | 固定为 `application/json;charset=utf-8` |
| SK 被错误 base64 解码 | 签名失败 | 火山 SK 应按控制台原值使用 | 直接使用原始 SK 字符串 |
| 只处理 URL 或只处理 base64 | 调用成功但拿不到图 | 响应结构可能因参数/服务变化而不同 | 同时兼容 `binary_data_base64` 和 `image_urls` |

---

## 4. 测试记录

### 4.1 历史 4 格漫剧测试

测试脚本：`/private/tmp/test_jimeng_comic.py`  
输出目录：`backend/comic_api_test/jimeng/`

| 格 | 耗时 | 文件大小 | 主观评价 |
|---|---:|---:|---|
| 第 1 格：山巅持剑 | 8.9s | 798KB | 画质高，角色精致，山河壮阔，青色配饰和发冠清晰 |
| 第 2 格：竹林夜战 | 7.8s | 817KB | 暗影妖设计好，动作氛围强，但腰带颜色变红 |
| 第 3 格：水晶洞修炼 | 7.5s | 813KB | 场景极美，角色面部一致性较好 |
| 第 4 格：乘鹤飞行 | 8.1s | 936KB | 构图震撼，但多生成一个人物 |

综合结果：

- **成功率**：4/4
- **平均耗时**：约 8.1s/张
- **画质**：⭐⭐⭐⭐⭐
- **中文理解**：⭐⭐⭐⭐⭐
- **角色一致性**：⭐⭐⭐⭐
- **漫画适配**：⭐⭐⭐⭐，偏高质量插画/竖屏漫剧，不是强分格漫画风

### 4.2 本次连通性复测

执行命令：

```bash
conda run -n ttsapp python /private/tmp/test_jimeng_full_debug.py
```

复测结果：

| 测试项 | HTTP | 业务码 | 结论 |
|---|---:|---|---|
| `high_aes_general_v20_L` + `visual.volcengineapi.com` | 401 | `50400` | 无权限，不可用 |
| `high_aes_general_v20_L` + `open.volcengineapi.com` | 401 | `50400` | 无权限，不可用 |
| `jimeng_high_aes_general_v21_L` + `visual.volcengineapi.com` | 200 | `10000` | 可用 |

复测结论：

- 当前账号和签名实现仍可正常调用即梦 `jimeng_high_aes_general_v21_L`。
- 文档中应明确禁止回退到 `high_aes_general_v20_L`。
- 后端正式接入时必须将 AK/SK 放入 `.env`，不能硬编码到脚本或前端。

---

## 5. 与现有方案对比

| 维度 | 即梦 Jimeng | Qwen-Image / 硅基流动 | ComfyUI |
|---|---|---|---|
| 画质 | 极高 | 高 | 取决于模型和工作流 |
| 中文理解 | 很强 | 很强 | 通常需要英文 Prompt 更稳 |
| 速度 | 约 8s/张 | 约 9-24s/张 | 10-60s，受 GPU 和工作流影响 |
| 角色一致性 | 中高 | 高 | 高，但需要 IPAdapter/InstantID 等工作流 |
| 运维复杂度 | 中，需火山鉴权 | 低，Bearer Token | 高，需 GPU、模型和节点管理 |
| 成本 | 按火山计费 | 按 API 计费 | GPU 租赁/本地算力 |
| 可控性 | 中 | 中 | 高 |
| 适合定位 | 高画质图片工具 | 漫画分镜首选工具 | 精细控制和复杂工作流 |

推荐策略：

1. **Qwen-Image**：默认漫画分镜工具。
2. **Jimeng**：高画质/国风/封面/关键帧工具。
3. **ComfyUI**：复杂工作流、图生视频、局部编辑、超分、角色一致性增强。

---

## 6. 迁移到 TTSApp 页面设计

### 6.1 页面入口设计

现有前端路由包含：

- `/comic`：漫剧生成
- `/comic-agent`：漫剧 Agent
- `/workflow`：工作流编排
- `/tts`：语音合成

建议新增或扩展两类入口：

#### 方案 A：扩展 `/comic` 页面

在漫剧生成页增加“图像模型选择”：

- `ComfyUI`：当前默认
- `Qwen-Image`：漫画分镜
- `Jimeng`：高画质国风/插画

适合普通用户，不需要理解 Agent 工具。

#### 方案 B：新增“AI 图像工具箱”子面板

页面能力：

- 输入 Prompt
- 选择模型：即梦/Qwen/ComfyUI
- 选择尺寸：`768x1024`、`1024x768`、`1024x1024`
- 选择用途：分镜、封面、角色设定、场景设定
- 展示生成结果，支持发送到漫剧 Agent 上下文

适合调试和工具化创作。

#### 方案 C：在 `/comic-agent` 设置抽屉中增强工具配置

当前 `ComicAgentView.vue` 已有“工具列表”和“服务配置”Tab，可以增加：

- 即梦工具组开关：`jimeng_generate_image` / `jimeng_reference_image` / `jimeng_edit_image` / `jimeng_upscale_image` / `jimeng_generate_video` / `jimeng_motion_mimic`
- 即梦服务状态显示
- 模型参数：默认图片模型、默认视频模型、默认宽高、默认用途、是否启用 legacy 通路

### 6.2 推荐 UI 流程

```text
用户打开 漫剧生成/Agent 页面
        ↓
选择生成模式：快速漫画 / 高画质插画 / 精细工作流
        ↓
快速漫画 → Qwen-Image
高画质插画 → Jimeng
精细工作流 → ComfyUI
        ↓
生成图片保存到 uploads/agent_outputs
        ↓
图片进入 Agent artifacts，可继续转视频/TTS/合成
```

### 6.3 后端 API 设计

建议新增 REST API：

```text
POST /api/v1/jimeng/images/generate
POST /api/v1/jimeng/images/reference
POST /api/v1/jimeng/images/edit
POST /api/v1/jimeng/images/upscale
POST /api/v1/jimeng/videos/generate
POST /api/v1/jimeng/videos/motion-mimic
```

请求体：

```json
{
  "model": "image_46",
  "prompt": "中国仙侠漫画风格...",
  "width": 768,
  "height": 1024,
  "seed": -1
}
```

响应体：

```json
{
  "status": "success",
  "provider": "jimeng",
  "image_url": "/uploads/agent_outputs/xxxx.png",
  "image_path": "/Users/zjj/home/learn26/ttsapp/backend/uploads/agent_outputs/xxxx.png",
  "elapsed": 8.1,
  "metadata": {
    "capability": "image_generation",
    "model": "image_46",
    "width": 768,
    "height": 1024
  }
}
```

建议后端模块划分：

```text
backend/app/core/image_providers/
  __init__.py
  jimeng_client.py        # 火山 V4 签名 + API 调用
  siliconflow_client.py   # 后续统一硅基流动图像生成
  image_service.py        # 保存图片、统一返回结构
```

---

## 7. 内化到漫剧 Agent 的架构判断：Tool / Skill / MCP

### 7.1 三种形态对比

| 形态 | 适合什么 | 优点 | 缺点 | 对即梦建议 |
|---|---|---|---|---|
| Tool | Agent 可直接调用的原子能力 | 与当前 `SEED_TOOLS`/`TOOL_EXECUTORS` 架构完全匹配，可审批、可记录、可流式展示 | 只解决执行，不解决复杂创作策略 | **必须做** |
| Skill | 可复用创作方法/提示词策略/多步流程 | 适合角色圣经、分镜 Prompt、模型选择策略 | 需要 Agent Runner 或 prompt 层支持 | **应该做** |
| MCP | 面向外部客户端/多 Agent 的标准工具协议 | 跨系统复用好，边界清晰 | 当前产品内调用会增加服务部署、鉴权、状态管理复杂度 | **暂缓** |

### 7.2 推荐结论

**短期：Tool + Skill，不做 MCP。**

原因：

1. 当前漫剧 Agent 已有 DB 工具注册和工具执行器，接入成本最低。
2. 即梦能力属于产品内核心生成能力，不需要一开始对外暴露为 MCP。
3. 真正影响效果的是“提示词策略”和“角色一致性策略”，这更适合用 Skill/Prompt 模板承载。
4. MCP 适合后续当 TTSApp 要把图像生成能力开放给 IDE、外部 Agent 或多个应用复用时再做。

### 7.3 Agent 工具设计

新增工具组：

```text
jimeng_generate_image    # 文生图/图片生成4.6优先
jimeng_reference_image   # 图生图/智能参考
jimeng_edit_image        # inpainting 局部编辑
jimeng_upscale_image     # 智能超清
jimeng_generate_video    # 视频生成
jimeng_motion_mimic      # 动作模仿2.0
```

工具返回：

```json
{
  "status": "success",
  "provider": "jimeng",
  "capability": "image_generation",
  "model": "image_46",
  "image_url": "/uploads/agent_outputs/xxx.png",
  "image_path": "/absolute/path/to/xxx.png",
  "file_urls": ["/uploads/agent_outputs/xxx.png"],
  "elapsed": 8.1
}
```

### 7.4 Skill 设计

建议增加“高画质国风分镜 Skill”：

```text
jimeng_xianxia_panel_skill
```

职责：

1. 把用户故事提炼为角色圣经。
2. 每一格 Prompt 都重复完整角色描述，减少角色漂移。
3. 对即梦增加固定约束：
   - “同一个角色”不够，必须写明发型、服装、颜色、武器、年龄、脸型。
   - 明确“单人画面”以避免多生人物。
   - 明确“漫画分镜构图、线条清晰”以降低纯插画偏移。
4. 根据用途自动补充 Prompt 片段：
   - `panel`：强调分镜、动作、景别。
   - `cover`：强调封面构图、标题留白、视觉中心。
   - `character`：强调全身设定、白底/纯色背景。
   - `scene`：强调环境、空间层次、无人。

Prompt 模板示例：

```text
中国仙侠漫画风格，竖屏漫剧分镜，单人画面。
固定角色：黑发少年，十八岁，清秀脸型，黑色长发束高马尾，白色长袍，青色腰带，手持青色长剑。
当前场景：{scene}
动作表情：{action}
构图：{shot_type}，线条清晰，色彩鲜明，高质量光影，不要额外人物，不要文字水印。
```

---

## 8. 落地实施方案

### 8.1 后端实施步骤

#### 第一步：配置项

在 `backend/app/config.py` 和 `.env.example` 增加：

```env
JIMENG_ENABLED=false
JIMENG_AK=
JIMENG_SK=
JIMENG_REGION=cn-north-1
JIMENG_DEFAULT_IMAGE_MODEL=image_46
JIMENG_DEFAULT_VIDEO_MODEL=video_30_pro
JIMENG_LEGACY_HOST=visual.volcengineapi.com
JIMENG_LEGACY_REQ_KEY=jimeng_high_aes_general_v21_L
JIMENG_DEFAULT_WIDTH=768
JIMENG_DEFAULT_HEIGHT=1024
```

注意：

- AK/SK 只能放后端 `.env`。
- 前端不能接触 AK/SK。
- 文档和日志不能打印完整密钥。

#### 第二步：新增客户端

新增：

```text
backend/app/core/image_providers/jimeng_client.py
```

职责：

- 统一管理火山 AK/SK、Region、签名和请求发送。
- 按官方接口封装图片 4.6、图片 4.0、图生图、inpainting、智能超清、视频生成、动作模仿、素材提取、商品图、数字人、视频翻译、小云雀 Agent 等方法。
- 把历史 `CVProcess` 通路保留为 `legacy_generate_image()`，仅用于兼容测试和回归对比。
- 统一解析不同接口返回的任务 ID、URL、base64、轮询状态和错误码。
- 返回标准化结果：`provider`、`capability`、`model`、`status`、`media_bytes/media_url/task_id`、`metadata`。

#### 第三步：新增 Agent 工具执行器

在 `tool_executor.py` 中新增一组语义化工具，而不是只新增一个 `jimeng_image_gen`：

```text
execute_jimeng_generate_image(params: dict) -> dict
execute_jimeng_reference_image(params: dict) -> dict
execute_jimeng_edit_image(params: dict) -> dict
execute_jimeng_upscale_image(params: dict) -> dict
execute_jimeng_generate_video(params: dict) -> dict
execute_jimeng_motion_mimic(params: dict) -> dict
execute_jimeng_product_material(params: dict) -> dict
execute_jimeng_digital_human(params: dict) -> dict
execute_jimeng_video_translate(params: dict) -> dict
execute_jimeng_video_agent(params: dict) -> dict
```

职责：

- 检查 `JIMENG_ENABLED`。
- 根据工具语义调用 `JimengProvider` 的对应方法。
- 图片结果使用现有 `_save_bytes()` 保存到 `uploads/agent_outputs`。
- 视频结果保存为 `mp4` 并返回 `video_url`、`video_path`。
- 若官方接口是异步任务模式，需要返回任务进度并在执行器内部完成轮询或封装为可恢复任务。
- 返回统一 `image_url` / `video_url` / `image_path` / `video_path` / `file_urls`，便于 Agent artifacts 继续串联。

#### 第四步：注册工具

在 `comic_agent.py` 的 `SEED_TOOLS` 增加：

```text
jimeng_generate_image
jimeng_reference_image
jimeng_edit_image
jimeng_upscale_image
jimeng_generate_video
jimeng_motion_mimic
jimeng_product_material
jimeng_digital_human
jimeng_video_translate
jimeng_video_agent
```

在 `tool_executor.py` 的 `TOOL_EXECUTORS` 增加：

```python
"jimeng_generate_image": execute_jimeng_generate_image,
"jimeng_reference_image": execute_jimeng_reference_image,
"jimeng_edit_image": execute_jimeng_edit_image,
"jimeng_upscale_image": execute_jimeng_upscale_image,
"jimeng_generate_video": execute_jimeng_generate_video,
"jimeng_motion_mimic": execute_jimeng_motion_mimic,
"jimeng_product_material": execute_jimeng_product_material,
"jimeng_digital_human": execute_jimeng_digital_human,
"jimeng_video_translate": execute_jimeng_video_translate,
"jimeng_video_agent": execute_jimeng_video_agent,
```

在 `TOOL_ALIASES` 增加：

```python
"jimeng": "jimeng_generate_image"
"jimeng_gen": "jimeng_generate_image"
"jimeng_image": "jimeng_generate_image"
"jimeng_i2i": "jimeng_reference_image"
"jimeng_edit": "jimeng_edit_image"
"jimeng_upscale": "jimeng_upscale_image"
"jimeng_video": "jimeng_generate_video"
"jimeng_motion": "jimeng_motion_mimic"
"jimeng_product": "jimeng_product_material"
"jimeng_digital_human": "jimeng_digital_human"
"jimeng_translate": "jimeng_video_translate"
"jimeng_agent": "jimeng_video_agent"
```

#### 第五步：更新 Prompt

在 Agent system prompt 的创作工具说明中增加：

```text
- jimeng_generate_image：即梦高画质中文图片生成，适合国风、仙侠、封面、关键帧。
- jimeng_reference_image：即梦图生图/智能参考，适合角色一致性和参考图延展。
- jimeng_edit_image：即梦局部编辑/inpainting，适合修复和局部改图。
- jimeng_upscale_image：即梦智能超清，适合图片增强。
- jimeng_generate_video：即梦视频生成，适合关键镜头动态化。
- jimeng_motion_mimic：即梦动作模仿，适合角色动作迁移。
- jimeng_product_material：即梦素材提取/商品图生成，适合电商、商品短剧和推广素材。
- jimeng_digital_human：即梦数字人快速模式，适合口播、讲解、带货数字人。
- jimeng_video_translate：即梦视频翻译2.0，适合成片多语言发布。
- jimeng_video_agent：小云雀视频 Agent，适合一键生成短视频成片。
```

同时增加模型选择规则：

| 用户意图 | 推荐工具 |
|---|---|
| “生成漫画分镜/4 格漫画” | `qwen_image_gen` 或当前 `generate_image` |
| “高画质/国风/仙侠/封面/即梦” | `jimeng_generate_image` |
| “用这张图继续生成/保持角色/参考图” | `jimeng_reference_image` |
| “局部修改/替换背景/修复画面” | `jimeng_edit_image` |
| “图片变清晰/超清/放大” | `jimeng_upscale_image` |
| “转视频/图生视频/文生视频” | `jimeng_generate_video` 或 `image_to_video` |
| “模仿动作/让角色做参考视频动作” | `jimeng_motion_mimic` |
| “商品图/带货素材/提取商品主体” | `jimeng_product_material` |
| “数字人口播/照片说话/讲解视频” | `jimeng_digital_human` |
| “把视频翻译成英文/多语言发布” | `jimeng_video_translate` |
| “一键成片/营销短视频/小云雀” | `jimeng_video_agent` |
| “保持人脸/参考图” | `generate_image_with_face` 或 `jimeng_reference_image` |
| “精细工作流/ComfyUI 风格” | `generate_image` |

### 8.2 前端实施步骤

#### `/comic-agent` 增强

- 工具列表会自动从后端 `/v1/comic-agent/tools` 获取，新增工具注册后可显示。
- 设置抽屉文案从“8 大工具”改为“多类创作工具”。
- 工具结果卡片已支持 `image_url`，无需大改。

#### `/comic` 页面增强

新增“生成引擎”选择：

```text
生成引擎：
[智能推荐] [ComfyUI] [Qwen-Image] [即梦 Jimeng]
```

选择规则：

- 默认 `智能推荐`。
- 用户选 `即梦` 时调用后端 Jimeng REST API 或走 Agent 工具。
- 输出图片可继续发送给图生视频/TTS/合成链路。

#### 服务配置 UI

在服务配置中显示：

- 即梦启用状态
- 当前 req_key
- 默认尺寸
- 连通性测试按钮

连通性测试接口建议：

```text
POST /api/v1/image-generation/jimeng/test
```

只返回鉴权/配额状态，不生成大图，避免误消耗额度。若火山没有纯 ping 能力，可以使用小尺寸测试并明确提示会消耗额度。

---

## 9. 测试计划

### 9.1 单元测试

| 测试项 | 预期 |
|---|---|
| V4 签名 canonical query 排序 | 签名稳定 |
| 官方图片 4.6 请求参数映射 | 与官方文档字段一致 |
| 官方图生图/视频异步任务解析 | 能正确处理任务 ID、轮询状态和结果 URL |
| legacy `CVProcess` Content-Type | 固定为 `application/json;charset=utf-8` |
| `binary_data_base64` / `image_urls` 兼容解析 | 返回图片 bytes 或下载图片 bytes |
| 火山错误码解析 | 返回明确“权限/配额/参数/审核/任务失败”分类 |
| AK/SK 缺失 | 返回配置错误，不发起请求 |

### 9.2 集成测试

| 测试项 | 请求 | 验证 |
|---|---|---|
| 图片 4.6 单图生成 | 512x512 简短 Prompt | `status=success`，文件落盘 |
| 图片 4.6 竖屏分镜 | 768x1024 仙侠 Prompt | 图片可打开，大小合理 |
| 图生图智能参考 | 上传角色图 + 新场景 Prompt | 角色特征延续 |
| 智能超清 | 输入低清图 | 返回增强图 |
| 视频生成 | 输入 Prompt 或图片 | 返回视频 URL/文件 |
| 动作模仿2.0 | 输入主体图和动作参考 | 返回动作迁移视频或任务结果 |
| Agent 工具调用 | 用户说“用即梦生成一张仙侠封面” | Agent 调用 `jimeng_generate_image` |
| 多步链路 | 即梦生成图 → 即梦视频/ComfyUI 图生视频 | `image_path` 能被后续工具使用 |
| 错误处理 | 禁用 `JIMENG_ENABLED` | 返回明确错误 |

### 9.3 人工评测维度

| 维度 | 标准 |
|---|---|
| 中文理解 | 是否准确表现人物、动作、场景 |
| 角色一致性 | 多格生成时脸型、发型、服装颜色是否稳定 |
| 构图 | 是否符合竖屏分镜/封面用途 |
| 多人物误生成 | 单人 Prompt 是否出现额外人物 |
| 漫画感 | 是否有线条、分镜、动漫风，而非纯写实插画 |
| 可继续处理 | 生成图是否适合图生视频、超分、合成 |

---

## 10. 风险与优化策略

### 10.1 角色一致性漂移

表现：腰带颜色变化、服装细节不稳定。

优化：

- 使用角色圣经，每格重复完整角色描述。
- 明确颜色和关键物件，例如“青色腰带、青色长剑”。
- 用 Agent artifacts 保存上一张角色图，后续若即梦支持参考图/图生图再接入。

### 10.2 多生成额外人物

表现：第 4 格“乘鹤飞行”多出一个人物。

优化：

- Prompt 加入“单人画面、只有一个少年、不要额外人物”。
- 对封面和分镜模板都加入“不要文字水印、不要多人”。

### 10.3 账号权限、模型权限与接口版本变化

表现：401 / `Access Denied`。

优化：

- 不把 `req_key` 作为即梦全量接口的唯一模型选择方式；正式接口按官方文档的模型/接口字段配置。
- legacy 通路的 req_key 单独放在 `JIMENG_LEGACY_REQ_KEY`。
- 错误信息中明确提示“检查接口开通状态、模型权限、配额和接口版本”。
- 服务配置页提供连通性测试。

### 10.4 成本不可控

表现：Agent 多轮自动调用导致额度消耗。

优化：

- 即梦工具默认设为 L1 创作工具，自动模式下可执行，但批量生成需要审批或额度提示。
- 对 `frames > 4` 的批量任务增加确认。
- 日志记录调用次数、耗时和生成尺寸。

---

## 11. 推荐实施优先级

| 优先级 | 任务 | 预估工时 | 产出 |
|---|---|---:|---|
| P0 | 人工核对官方图片 4.6/图生图/视频/动作模仿接口正文 | 1h | 明确 host、path、Action、Version、请求字段、异步轮询方式 |
| P0 | 封装 `JimengProvider` 核心能力 | 2h | 图片、图生图、编辑、超清、视频、动作模仿可复用客户端 |
| P0 | Agent 新增核心工具组 | 2h | Agent 可调用图片、图生图、编辑、超清、视频、动作模仿 |
| P0 | 配置项和 `.env.example` | 0.5h | 安全管理 AK/SK |
| P1 | `/comic-agent` 工具文案和 Prompt 更新 | 1h | Agent 知道何时选即梦 |
| P1 | `/comic` 页面增加即梦图片/视频能力选择 | 2h | 普通页面可使用即梦 |
| P1 | 单元/集成测试 | 2h | 防止签名、任务轮询和响应解析回归 |
| P1 | Agent 扩展工具组 | 2h | 商品素材、数字人、视频翻译、小云雀 Agent 能力可用 |
| P2 | Skill：角色圣经与高画质分镜模板 | 2h | 多格一致性提升 |
| P2 | 服务配置页连通性测试 | 1h | 运维可视化 |
| P3 | MCP 包装 | 3h+ | 对外部 Agent/IDE 开放能力 |

---

## 12. 最终架构建议

### 12.1 短期架构

```text
Frontend /comic 或 /comic-agent
        ↓
Backend REST / WebSocket
        ↓
Agent Runner
        ↓
Tool Group:
  jimeng_generate_image / jimeng_reference_image / jimeng_edit_image
  jimeng_upscale_image / jimeng_generate_video / jimeng_motion_mimic
        ↓
JimengProvider（官方多接口 + V4 签名 + legacy CVProcess 兼容）
        ↓
保存图片/视频到 uploads/agent_outputs
        ↓
返回 image_url / video_url / image_path / video_path / file_urls
        ↓
Agent artifacts 继续用于图生视频、TTS、合成
```

### 12.2 中期架构

```text
统一 Image Generation Service
        ├── Jimeng Provider
        ├── SiliconFlow Provider
        ├── OpenAI/GPT-Image Provider
        └── ComfyUI Provider

Agent Tool 层只关心：
        generate_image(provider="jimeng", purpose="cover", prompt=...)
```

中期可以把多个图片模型统一成一个 `generate_image` 抽象，再通过 `provider` 或 `quality_mode` 选择底层通道。

中期再加入非核心生成链路：

```text
Jimeng Extended Tools
        ├── jimeng_product_material    # 商品素材/营销商品图
        ├── jimeng_digital_human       # 数字人快速模式
        ├── jimeng_video_translate     # 视频翻译2.0
        └── jimeng_video_agent         # 小云雀视频 Agent
```

### 12.3 长期架构

```text
TTSApp 内部工具服务
        ↓
MCP Server（可选）
        ↓
外部 Agent / IDE / 自动化工作流
```

MCP 不作为第一阶段目标，只在需要跨产品复用时建设。

---

## 13. 下一步可直接执行的落地清单

1. 新增 `backend/app/core/image_providers/jimeng_client.py`。
2. 增加 `JIMENG_*` 配置项。
3. 人工在浏览器中打开官方接口正文，先确认 P0：图片 4.6、图生图、编辑、超清、视频、动作模仿的请求/响应字段。
4. 在 `tool_executor.py` 增加 P0 即梦工具组执行器。
5. 在 `comic_agent.py` 的 `SEED_TOOLS` 注册 P0 即梦工具组。
6. 更新 Agent system prompt 的模型选择规则。
7. 添加最小测试：`tests/test_jimeng_client.py`。
8. 前端 `/comic` 增加“即梦 Jimeng”图片/视频能力选项。
9. 前端 `/comic-agent` 修改工具说明和服务配置展示。
10. 用图片 4.6、图生图、视频、动作模仿分别做最小用例复测，并记录图片/视频、耗时、错误码。
11. 基于复测结果继续优化角色圣经 Skill。
12. P0 稳定后，再接入商品素材、数字人、视频翻译、小云雀 Agent。
