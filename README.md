# TTS 语音平台

基于 Fish Audio 的全栈语音合成平台，支持文字转语音、语音识别、AI 对话等功能。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Vue 3 + Element Plus + Vite + TypeScript |
| 后端 | FastAPI + SQLAlchemy + Pydantic |
| 数据库 | MySQL 8+ (本地 Homebrew) |
| 缓存 | Redis 7+ (本地 Homebrew) |
| TTS 引擎 | Fish Audio API (S1 / S2-Pro) |
| LLM | AIPro (Claude/GPT/Gemini) + 南格 AI Gateway (Qwen3-32B) |
| 漫剧 Agent | LLM ReAct 循环 + ComfyUI 40+ 工作流 |

## 环境要求

- **macOS**（Homebrew）
- **Conda**（Miniconda / Anaconda）
- **Python 3.13**（conda 环境名: `ttsapp`）
- **Node.js 18+**
- **MySQL 8+**：`brew install mysql && brew services start mysql`
- **Redis 7+**：`brew install redis && brew services start redis`

## 快速启动

```bash
# 克隆项目
git clone <repo_url> && cd ttsapp

# 一键启动（自动创建虚拟环境、安装依赖、启动 Docker 容器）
./start.sh
```

首次启动会自动完成：
1. 检查本地 MySQL / Redis，未运行则自动 `brew services start`
2. 创建 / 激活 conda `ttsapp` 环境 (Python 3.13)
3. 安装 Python 依赖 (`pip install -r requirements.txt`)
4. 安装前端依赖 (`npm install`)
5. 启动后端 (默认 :8000) 和前端 (默认 :3000)

### 默认账号

| 用户名 | 密码 |
|---|---|
| zjjzjw | zjjzjwQQ11 |

### 数据库初始化（仅首次）

```bash
mysql -u root -h 127.0.0.1 -e "
CREATE DATABASE IF NOT EXISTS ttsapp DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'ttsapp'@'localhost' IDENTIFIED BY 'ttsapp123';
CREATE USER IF NOT EXISTS 'ttsapp'@'127.0.0.1' IDENTIFIED BY 'ttsapp123';
GRANT ALL PRIVILEGES ON ttsapp.* TO 'ttsapp'@'localhost';
GRANT ALL PRIVILEGES ON ttsapp.* TO 'ttsapp'@'127.0.0.1';
FLUSH PRIVILEGES;
"
```

## 服务管理

```bash
./start.sh              # 启动（默认）
./start.sh stop         # 停止前后端进程（Docker 容器保留）
./start.sh restart      # 重启全部服务
./start.sh status       # 查看服务状态
./stop.sh               # 等同于 ./start.sh stop
```

## 服务地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |

> 端口被占用时会自动切换备用端口，启动日志会显示实际端口。

## 项目结构

```
ttsapp/
├── start.sh                  # 启动 / 停止 / 重启脚本
├── stop.sh                   # 快捷停止
├── docker-compose.yml        # MySQL + Redis + ES + Milvus
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 配置（读取 .env）
│   │   ├── api/v1/           # 路由
│   │   │   ├── auth.py       # 注册 / 登录 / JWT
│   │   │   ├── chat.py       # AI 对话（流式 SSE）
│   │   │   ├── tts.py        # TTS 合成
│   │   │   ├── asr.py        # 语音识别
│   │   │   └── voice_models.py  # 音色管理
│   │   ├── core/
│   │   │   ├── fish_speech.py   # Fish Audio API 客户端
│   │   │   └── llm_client.py    # LLM 客户端
│   │   ├── models/           # SQLAlchemy 模型
│   │   └── schemas/          # Pydantic 验证
│   ├── requirements.txt
│   └── .env                  # 环境变量（不提交 git）
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── chat/ChatView.vue      # AI 对话页
│   │   │   ├── tts/TTSView.vue        # TTS 合成页
│   │   │   └── voice-models/          # 音色管理页
│   │   ├── api/              # Axios 请求封装
│   │   └── router/           # Vue Router
│   └── package.json
└── fish_test深度科研报告.md    # Fish Audio 情感标记研究
```

## 配置说明

后端配置文件：`backend/.env`

```env
# 数据库
DATABASE_URL=mysql+aiomysql://ttsapp:ttsapp123@localhost:3306/ttsapp

# Redis
REDIS_URL=redis://:redis123456@localhost:6379/0

# JWT
JWT_SECRET_KEY=<your-secret-key>

# Fish Audio TTS
FISH_API_URL=https://api.fish.audio
FISH_API_KEY=<your-fish-api-key>
FISH_DEFAULT_VOICE=<default-voice-id>

# LLM
L1_LLM_BINDING=southgrid
L1_LLM_BINDING_HOST=<llm-gateway-url>
L1_LLM_BINDING_API_KEY=<llm-api-key>
```

## 功能模块

### AI 对话
- 多会话管理，支持自定义 system prompt
- 流式 SSE 响应，`<think>` 标签过滤
- 消息 TTS 朗读

### TTS 语音合成
- 支持 Fish Audio S1 / S2 / S2-Pro 引擎
- 语气提示词（style_prompt）控制说话风格
- MP3 / WAV / PCM / OPUS 输出格式
- 音量均衡（normalize）、延迟模式选择

### 音色管理
- 自定义音色：上传音频文件创建克隆音色
- 官方音色：搜索、浏览、一键导入 Fish Audio 官方预设音色
- 支持中/英/日语言筛选

### 语音识别 (ASR)
- 上传音频文件转文字

### 漫剧 Agent 对话创作
- **LLM ReAct 循环**：用户选择模型（Claude/GPT/Qwen）作为大脑，自动推理 + 工具调用
- **8 个工具**：文生图 / 人脸保持 / 图像编辑 / 图生视频 / 超分 / TTS / 媒体合成 / 字幕
- **40+ ComfyUI 工作流**：仙侠/水墨/盲盒/动漫/写实/Flux 多风格
- **Prompt 可视化管理**：设置面板内编辑各节点 System/User 模板
- **对话历史持久化**：多轮上下文记忆

## 依赖同步

`start.sh` 会自动检测 `requirements.txt` 变更（基于 MD5 hash），变更时在 conda `ttsapp` 环境中自动执行 `pip install`，无需手动操作。

### 手动环境初始化

```bash
# 创建 conda 环境
conda create -n ttsapp python=3.13 -y
conda activate ttsapp

# 安装后端依赖
cd backend && pip install -r requirements.txt

# 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 常见问题

**Q: 登录时报 500 错误**
A: 检查 `backend/logs/backend.log`，如果提示 `cryptography package is required`，运行 `./start.sh restart` 即可自动安装。

**Q: 端口被占用**
A: 脚本会自动寻找空闲端口（8000→10001→10003→随机），启动日志会显示实际端口。

**Q: MySQL/Redis 未启动**
A: 运行 `brew services start mysql redis` 或 `./start.sh restart`（会自动尝试启动）。
