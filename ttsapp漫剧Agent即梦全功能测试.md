# TTSApp 漫剧 Agent 即梦全功能测试指南

> 目标：指导你确认“即梦能力”已经在漫剧 Agent 中显示，并验证工具开关、Agent 调用、真实文生图能力以及后续异步能力接入状态。

---

## 1. 当前即梦接入范围

### 1.1 已注册到漫剧 Agent 的 6 个工具

| 工具标识名 | 前端显示名 | 执行器 | 当前状态 | 说明 |
|---|---|---|---|---|
| `jimeng_generate_image` | 即梦文生图 | `jimeng` | 已真实可用 | 当前走 legacy `CVProcess`，已验证可真实出图 |
| `jimeng_reference_image` | 即梦图生图 | `jimeng` | 已显示，待完整异步接入 | 预留图生图/智能参考能力 |
| `jimeng_edit_image` | 即梦局部编辑 | `jimeng` | 已显示，待完整异步接入 | 预留 inpainting 能力 |
| `jimeng_upscale_image` | 即梦智能超清 | `jimeng` | 已显示，待完整异步接入 | 预留智能超清能力 |
| `jimeng_generate_video` | 即梦视频生成 | `jimeng` | 已显示，待完整异步接入 | 预留文生视频/图生视频能力 |
| `jimeng_motion_mimic` | 即梦动作模仿 | `jimeng` | 已显示，待完整异步接入 | 预留动作模仿 2.0 能力 |

### 1.2 关键实现文件

| 文件 | 作用 |
|---|---|
| `backend/app/core/jimeng_client.py` | 即梦 Provider，包含签名、legacy 文生图、异步任务基础方法 |
| `backend/app/core/comic_chat_agent/tool_executor.py` | Agent 工具执行器注册，即梦工具真实调用入口 |
| `backend/app/api/v1/comic_agent.py` | `SEED_TOOLS` 工具种子、`/comic-agent/tools` API |
| `backend/app/config.py` | `JIMENG_*` 配置项 |
| `backend/.env` | 本地真实即梦 AK/SK 配置，不要提交明文 |
| `frontend/src/views/comic-agent/ComicAgentView.vue` | 漫剧 Agent 页面，设置抽屉中展示工具列表 |
| `frontend/src/api/comic-agent.ts` | 前端请求 `/v1/comic-agent/tools` |

---

## 2. 前置条件检查

### 2.1 后端环境变量

确认 `backend/.env` 中存在以下配置：

```env
JIMENG_ENABLED=true
JIMENG_AK=你的火山引擎AK
JIMENG_SK=你的火山引擎SK
JIMENG_REGION=cn-north-1
JIMENG_HOST=visual.volcengineapi.com
JIMENG_TIMEOUT=300
JIMENG_DEFAULT_WIDTH=768
JIMENG_DEFAULT_HEIGHT=1024
JIMENG_LEGACY_REQ_KEY=jimeng_high_aes_general_v21_L
```

### 2.2 后端和前端服务

项目默认端口：

| 服务 | 默认地址 |
|---|---|
| 后端 | `http://127.0.0.1:8000` |
| 前端 | `http://127.0.0.1:3000` |

如果刚修改过 `SEED_TOOLS` 或 `.env`，需要重启后端。

---

## 3. 后端工具注册验证

### 3.1 登录获取 Token

使用默认账号登录：

```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/v1/auth/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=zjjzjw&password=zjjzjwQQ11'
```

预期返回：

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

### 3.2 查询工具列表

把上一步 token 放到 `Authorization`：

```bash
TOKEN='替换为登录返回的 access_token'

curl -sS 'http://127.0.0.1:8000/api/v1/comic-agent/tools' \
  -H "Authorization: Bearer $TOKEN"
```

### 3.3 必须看到的 6 个工具

检查返回 JSON 中是否包含：

```text
jimeng_generate_image
jimeng_reference_image
jimeng_edit_image
jimeng_upscale_image
jimeng_generate_video
jimeng_motion_mimic
```

每个工具应满足：

```json
{
  "executor_type": "jimeng",
  "is_enabled": true
}
```

### 3.4 如果接口里看不到即梦工具

优先按顺序排查：

1. **代码是否包含 `SEED_TOOLS`**
   - 文件：`backend/app/api/v1/comic_agent.py`
   - 搜索：`jimeng_generate_image`

2. **数据库是否同步过 seed**
   - 后端启动时会执行 `seed_agent_data()`。
   - 如果启动时 seed 被其他模型唯一键冲突阻塞，工具不会进入 DB。

3. **重启后端**
   - 修改 `SEED_TOOLS` 或 `.env` 后必须重启后端。

4. **确认 seed 修复已存在**
   - `seed_agent_data()` 中模型同步应按 `name` 查重，避免 `model_config.name` 重复插入。

---

## 4. 前端显示验证

### 4.1 打开漫剧 Agent 页面

浏览器访问：

```text
http://127.0.0.1:3000
```

登录后进入“漫剧 Agent”页面。

### 4.2 打开配置抽屉

在漫剧 Agent 页面：

1. 点击右上角或页面上的 **Agent 配置管理** 入口。
2. 打开右侧抽屉。
3. 进入 **🔧 工具列表** Tab。

### 4.3 预期显示

工具列表中应出现以下 6 行：

| 前端显示名 | 标识名 | 执行器 | 开关 |
|---|---|---|---|
| 即梦文生图 | `jimeng_generate_image` | `jimeng` | 开 |
| 即梦图生图 | `jimeng_reference_image` | `jimeng` | 开 |
| 即梦局部编辑 | `jimeng_edit_image` | `jimeng` | 开 |
| 即梦智能超清 | `jimeng_upscale_image` | `jimeng` | 开 |
| 即梦视频生成 | `jimeng_generate_video` | `jimeng` | 开 |
| 即梦动作模仿 | `jimeng_motion_mimic` | `jimeng` | 开 |

### 4.4 如果后端接口有、前端没有

排查顺序：

1. **刷新前端页面**
   - 工具列表由前端加载时调用 `fetchTools()` 获取。

2. **确认登录状态有效**
   - 如果 token 过期，工具接口会返回 `Not authenticated`。

3. **打开浏览器开发者工具 Network**
   - 找到请求：`/api/v1/comic-agent/tools` 或 `/v1/comic-agent/tools`。
   - 预期状态码：`200`。
   - 响应中应包含 `jimeng_generate_image`。

4. **确认前端代理配置**
   - 前端 API 文件：`frontend/src/api/comic-agent.ts`
   - 工具接口：`fetchTools()` 请求 `/v1/comic-agent/tools`。

---

## 5. 即梦文生图真实能力测试

### 5.1 在 Agent 对话中输入

```text
请使用即梦文生图生成一张竖屏漫剧封面：黑发少年身穿白色长袍，手持青色长剑，站在云雾山巅，国风仙侠漫画风，高质量光影，不要文字水印。尺寸 768x1024。
```

### 5.2 预期 Agent 行为

| 步骤 | 预期 |
|---|---|
| 1 | Agent 识别应调用 `jimeng_generate_image` |
| 2 | 如果当前审批策略要求确认，会出现工具确认卡 |
| 3 | 批准后调用即梦接口 |
| 4 | 返回 `status=success` |
| 5 | 聊天区展示生成图片 |
| 6 | 结果中包含 `/uploads/agent_outputs/*.png` |

### 5.3 成功返回结构参考

```json
{
  "status": "success",
  "provider": "jimeng",
  "capability": "legacy_image_generation",
  "model": "jimeng_high_aes_general_v21_L",
  "image_url": "/uploads/agent_outputs/xxxx.png",
  "image_path": "/Users/zjj/home/learn26/ttsapp/backend/uploads/agent_outputs/xxxx.png",
  "file_urls": ["/uploads/agent_outputs/xxxx.png"]
}
```

### 5.4 本地文件验证

成功后检查：

```text
backend/uploads/agent_outputs/
```

应出现新的 `.png` 文件。

---

## 6. 其他即梦工具显示与占位行为测试

> 当前除 `jimeng_generate_image` 外，其余工具已经显示和注册，但仍等待官方新异步接口字段完全接入。

### 6.1 图生图工具显示测试

输入：

```text
请使用即梦图生图，根据上一张图片生成一个同角色的雨夜街头版本。
```

预期：

- Agent 应倾向调用 `jimeng_reference_image`。
- 工具存在，不应提示“未知工具”。
- 当前可能返回“异步能力未配置/待接入”类错误，这是预期状态。

### 6.2 局部编辑工具显示测试

输入：

```text
请用即梦局部编辑，把上一张图中主角手里的剑改成燃烧的金色长剑。
```

预期：

- Agent 应倾向调用 `jimeng_edit_image`。
- 工具存在，不应提示“工具不存在”。
- 当前可能返回待接入提示。

### 6.3 智能超清工具显示测试

输入：

```text
请用即梦智能超清把上一张图片放大 2 倍并提升清晰度。
```

预期：

- Agent 应倾向调用 `jimeng_upscale_image`。
- 工具存在，执行器为 `jimeng`。
- 当前可能返回待接入提示。

### 6.4 视频生成工具显示测试

输入：

```text
请用即梦视频生成，把上一张图片变成 5 秒视频：镜头缓慢推进，云雾流动，主角衣袍飘动。
```

预期：

- Agent 应倾向调用 `jimeng_generate_video`。
- 工具存在，执行器为 `jimeng`。
- 当前可能返回待接入提示。

### 6.5 动作模仿工具显示测试

输入：

```text
请用即梦动作模仿，让主角图片模仿参考视频里的挥剑动作。
```

预期：

- Agent 应倾向调用 `jimeng_motion_mimic`。
- 工具存在，执行器为 `jimeng`。
- 当前可能返回待接入提示。

---

## 7. 工具开关测试

### 7.1 在前端关闭即梦文生图

操作：

1. 打开 **Agent 配置管理**。
2. 进入 **工具列表**。
3. 找到 `jimeng_generate_image`。
4. 关闭开关。

预期：

- 前端调用 `PUT /v1/comic-agent/tools/{id}`。
- `is_enabled` 变为 `false`。
- Agent 后续不应优先选择已关闭工具。

### 7.2 再次打开即梦文生图

操作：

1. 打开 `jimeng_generate_image` 开关。
2. 刷新工具列表。

预期：

- `is_enabled` 变回 `true`。
- Agent 可以再次调用即梦文生图。

---

## 8. 常见问题排查

### 8.1 前端工具列表完全为空

可能原因：

- 未登录或 token 失效。
- 后端未启动。
- 前端代理到错误后端端口。

检查：

```bash
curl -sS http://127.0.0.1:8000/health
```

### 8.2 工具接口返回 `Not authenticated`

说明未带 token 或 token 过期。

处理：

- 重新登录前端。
- 或通过 `/api/v1/auth/login` 重新获取 token。

### 8.3 工具列表没有即梦工具

可能原因：

- 后端没有重启，`SEED_TOOLS` 未执行。
- `seed_agent_data()` 执行失败。
- 数据库 `tool_registry` 没同步。

处理：

1. 重启后端。
2. 查看 `backend/logs/backend.log`。
3. 搜索日志：`Seed`、`工具同步`、`IntegrityError`。

### 8.4 即梦文生图返回 AK/SK 未配置

错误类似：

```text
JIMENG_AK/JIMENG_SK 未配置
```

处理：

1. 检查 `backend/.env`。
2. 确认 `JIMENG_ENABLED=true`。
3. 确认 `JIMENG_AK`、`JIMENG_SK` 非空。
4. 重启后端。

### 8.5 即梦文生图接口返回鉴权失败

可能原因：

- AK/SK 错误。
- 火山账号权限未开通对应接口。
- 系统时间偏差太大影响 V4 签名。
- `JIMENG_REGION` 或 `JIMENG_HOST` 错误。

推荐配置：

```env
JIMENG_REGION=cn-north-1
JIMENG_HOST=visual.volcengineapi.com
```

### 8.6 Agent 没选择即梦工具，而选择 ComfyUI 工具

可能原因：

- Prompt 没明确写“即梦”。
- ComfyUI 相关工具仍开启。
- Agent 模型对工具描述理解不稳定。

测试时建议明确输入：

```text
请使用 jimeng_generate_image / 即梦文生图，不要使用 ComfyUI，生成一张……
```

---

## 9. 最小验收清单

### 9.1 后端验收

- [ ] `backend/.env` 已配置 `JIMENG_ENABLED=true`。
- [ ] `backend/.env` 已配置 `JIMENG_AK` 和 `JIMENG_SK`。
- [ ] 后端启动成功。
- [ ] `/api/v1/auth/login` 登录成功。
- [ ] `/api/v1/comic-agent/tools` 返回 200。
- [ ] 工具列表包含 6 个 `jimeng_*` 工具。
- [ ] 6 个即梦工具 `executor_type` 均为 `jimeng`。
- [ ] 6 个即梦工具 `is_enabled` 均为 `true`。

### 9.2 前端显示验收

- [ ] 漫剧 Agent 页面可打开。
- [ ] Agent 配置管理抽屉可打开。
- [ ] 工具列表 Tab 可加载。
- [ ] 能看到“即梦文生图”。
- [ ] 能看到“即梦图生图”。
- [ ] 能看到“即梦局部编辑”。
- [ ] 能看到“即梦智能超清”。
- [ ] 能看到“即梦视频生成”。
- [ ] 能看到“即梦动作模仿”。
- [ ] 6 个工具的执行器标签显示为 `jimeng`。

### 9.3 真实能力验收

- [ ] Agent 能调用 `jimeng_generate_image`。
- [ ] 调用后返回 `status=success`。
- [ ] 返回 `image_url`。
- [ ] `backend/uploads/agent_outputs/` 中生成新图片。
- [ ] 聊天区能显示生成图片。

### 9.4 占位能力验收

- [ ] `jimeng_reference_image` 工具存在。
- [ ] `jimeng_edit_image` 工具存在。
- [ ] `jimeng_upscale_image` 工具存在。
- [ ] `jimeng_generate_video` 工具存在。
- [ ] `jimeng_motion_mimic` 工具存在。
- [ ] 调用这些工具时不会报“未知工具”。
- [ ] 当前返回待接入提示属于预期。

---

## 10. 后续开发路线

### 10.1 第一阶段：显示完成

目标：让所有即梦能力在 Agent 工具列表中显示。

状态：已完成。

### 10.2 第二阶段：文生图真实可用

目标：`jimeng_generate_image` 能真实生成图片并返回到聊天区。

状态：已完成。

### 10.3 第三阶段：新异步接口全面接入

目标：补齐以下能力的真实 API 调用：

- `jimeng_reference_image`
- `jimeng_edit_image`
- `jimeng_upscale_image`
- `jimeng_generate_video`
- `jimeng_motion_mimic`

需要从官方文档核对：

- `Action`
- `Version`
- `req_key`
- 请求字段
- 返回字段
- 任务 ID 字段
- 轮询状态字段
- 图片/视频结果字段

### 10.4 第四阶段：Agent 编排优化

目标：让 Agent 在漫剧任务中自动优先使用即梦能力。

可优化方向：

- 工具描述中强化“中文提示词、国风、仙侠、漫剧封面优先用即梦”。
- System Prompt 中加入即梦工具选择规则。
- 在 ComfyUI 工具关闭时，Agent 自动选择即梦工具。
- 为即梦工具增加更明确的参数示例。

---

## 11. 推荐测试输入合集

### 11.1 只测显示

```text
请列出你当前可用的即梦工具，并说明每个工具适合做什么。
```

### 11.2 测真实文生图

```text
请使用即梦文生图生成一张竖屏漫剧封面：黑发少年身穿白色长袍，手持青色长剑，站在云雾山巅，国风仙侠漫画风，高质量光影，不要文字水印。尺寸 768x1024。
```

### 11.3 测工具选择

```text
请不要使用 ComfyUI，只使用即梦生成一张仙侠退婚流短剧封面。
```

### 11.4 测图生图占位

```text
请使用即梦图生图，把上一张图改成雨夜街头版本，保持同一个角色。
```

### 11.5 测视频生成占位

```text
请使用即梦视频生成，把上一张图片变成镜头缓慢推进、云雾流动、衣袍飘动的 5 秒视频。
```

---

## 12. 当前结论

当前系统已经满足“让即梦能力在漫剧 Agent 里显示”的核心要求：

- 后端已注册 6 个即梦工具。
- 数据库工具表已同步 6 个即梦工具。
- 前端工具列表通过 `/v1/comic-agent/tools` 可显示这些工具。
- `jimeng_generate_image` 已真实可用并通过出图验证。
- 其他 5 个能力已完成显示与调用入口，等待官方异步接口字段补齐后即可转为真实调用。
