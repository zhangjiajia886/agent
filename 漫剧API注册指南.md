# 漫剧 Agent 图像 API 注册指南

> 4 个平台的注册 + 获取 API Key 步骤，注册完成后将 Key 告诉我即可开始测试

---

## 1. OpenAI GPT-Image ⭐ 最推荐

> 角色一致性最强，API 最简单

| 项目 | 详情 |
|------|------|
| 注册地址 | https://platform.openai.com/signup |
| API Key 页面 | https://platform.openai.com/api-keys |
| 免费额度 | 新用户 $5（可生成约 60-125 张图片） |
| 需要 | 邮箱 + 手机号（支持国内号） |

### 获取步骤
1. 打开 https://platform.openai.com/signup 注册账号
2. 登录后点击左侧菜单 **API Keys**
3. 点击 **Create new secret key**，命名为 `ttsapp-comic`
4. 复制 `sk-...` 格式的 Key（只显示一次）
5. 确认 **Billing** 页面有余额（新用户自带 $5）

### 备选：你的 AIPRO 代理可能已支持
> 你现有的 `AIPRO_BASE_URL=https://vip.aipro.love/v1` 可能支持 `dall-e-3` 模型
> 我可以先用这个测试，如果不支持再注册 OpenAI

---

## 2. fal.ai (FLUX Kontext) ⭐ 推荐

> 速度最快，Kontext 角色一致性优秀

| 项目 | 详情 |
|------|------|
| 注册地址 | https://fal.ai/dashboard/keys （GitHub 登录即可） |
| API Key 页面 | https://fal.ai/dashboard/keys |
| 免费额度 | **$10 免费额度**（可生成约 200-500 张图片） |
| 需要 | GitHub 账号 或 Google 账号 |

### 获取步骤
1. 打开 https://fal.ai 点击右上角 **Sign In**
2. 用 **GitHub** 或 **Google** 登录
3. 进入 https://fal.ai/dashboard/keys
4. 点击 **Create Key**
5. 复制 Key（格式类似 `fal_...`）
6. 免费 $10 额度自动到账

---

## 3. 硅基流动 SiliconFlow ⭐ 国内最便宜

> 国内访问无障碍，聚合 FLUX/SD/Kolors 等模型

| 项目 | 详情 |
|------|------|
| 注册地址 | https://cloud.siliconflow.cn/account/login （手机号注册） |
| API Key 页面 | https://cloud.siliconflow.cn/account/ak |
| 免费额度 | 注册送 **¥14 免费额度**（FLUX Schnell 可生成 1400+ 张） |
| 需要 | 手机号 |

### 获取步骤
1. 打开 https://cloud.siliconflow.cn 点击注册
2. 用手机号注册并登录
3. 进入 **账户管理 → API 密钥**
4. 点击 **新建密钥**
5. 复制 Key（格式 `sk-...`）
6. 免费额度自动到账（可在"费用"页面查看）

### 可用模型
- `black-forest-labs/FLUX.1-schnell` — 免费！
- `black-forest-labs/FLUX.1-dev` — ¥0.01/张
- `stabilityai/stable-diffusion-3-5-large` — ¥0.035/张
- `Kwai-Kolors/Kolors` — ¥0.01/张

---

## 4. 即梦 Jimeng（字节跳动）

> 国内中文理解最好，配合可灵做视频

| 项目 | 详情 |
|------|------|
| 注册地址 | https://jimeng.jianying.com（抖音账号登录） |
| API 开放平台 | https://www.volcengine.com/docs/6791 （火山引擎） |
| 免费额度 | 每日 **66 免费积分**（≈66 次生成） |
| 需要 | 抖音/字节账号 |

### 获取步骤（火山引擎 API 方式）
1. 打开 https://console.volcengine.com 注册火山引擎账号
2. 搜索 **智能美化特效** 或 **即梦**，开通服务
3. 进入 **密钥管理** 获取 Access Key + Secret Key
4. 或者用即梦网页版获取 session token（更简单但不稳定）

### 备选：即梦逆向 API（仅测试用）
> GitHub 上有 `jimeng-free-api` 项目，用 session token 调用
> 仅供测试，正式使用请走火山引擎官方 API

---

## 注册优先级建议

| 优先级 | 平台 | 原因 |
|--------|------|------|
| 🔴 先注册 | **硅基流动** | 国内手机号即可，1 分钟搞定，免费额度 ¥14 |
| 🔴 先注册 | **fal.ai** | GitHub 登录即可，1 分钟搞定，免费 $10 |
| 🟡 其次 | **OpenAI** | 可先用你的 AIPRO 代理测试 dall-e-3 |
| 🟢 可选 | **即梦** | 火山引擎注册流程较复杂，可后续再接 |

---

## 注册完成后

把获取到的 Key 告诉我，格式如下：

```

硅基流动: <请填写你的 SiliconFlow API Key>
即梦: <请填写你的即梦 Access Key / Secret Key>
```

我会立即：
1. 写 4 个测试脚本，分别调用各平台生成同一组漫剧分镜
2. 对比角色一致性、画质、速度、成本
3. 生成完整的对比报告
