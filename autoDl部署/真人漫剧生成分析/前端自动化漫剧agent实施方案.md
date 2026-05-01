# 前端自动化漫剧 Agent 实施方案

> 基于《自动化漫剧 Agent 设计》文档，规划前端第一版实现。
> 技术栈：Vue 3 + Vite + Element Plus + TypeScript + SCSS
> 后端尚未就绪，本版使用 **Mock 模拟模式** 演示完整交互流程。

---

## 一、实施范围

### 1.1 本版做什么

| 功能 | 说明 |
|---|---|
| 对话式漫剧创作页面 | 新增 `/comic-agent` 路由，聊天式交互 |
| WebSocket 事件协议对接 | 处理 `text` / `tool_start` / `tool_done` / `error` 四种事件 |
| 工具执行卡片 | 展示 Agent 调用工具的实时进度（工具名、输入参数、耗时） |
| 图片/视频内联展示 | `tool_done` 返回图片路径时，直接在对话中渲染缩略图 |
| 附件上传 | 支持上传参考图片（人脸照片），通过 WebSocket 发送给 Agent |
| Mock 模拟模式 | 后端未就绪时，前端自带模拟 Agent 响应，可完整演示 UI 流程 |

### 1.2 本版不做什么

- 后端 Agent Loop 实现（后端独立迭代）
- 会话持久化（本版会话仅在内存中，后端就绪后接 DB）
- 模型管理页面（后期独立页面）
- 工作流模板管理页面（后期独立页面）

---

## 二、文件变更清单

```text
frontend/src/
├── api/
│   └── comic-agent.ts            ← 新增：WebSocket 连接管理 + Mock 模式
├── views/
│   └── comic-agent/
│       └── ComicAgentView.vue    ← 新增：对话式漫剧创作页面
├── router/
│   └── index.ts                  ← 修改：新增 /comic-agent 路由
└── views/layout/
    └── MainLayout.vue            ← 修改：侧边栏新增菜单项
```

---

## 三、WebSocket 事件协议

### 3.1 客户端 → 服务端

```json
{
  "message": "把这段小说变成漫剧：李逍遥初入仙灵岛...",
  "attachments": ["/uploads/face_xxx.png"]
}
```

### 3.2 服务端 → 客户端

四种事件类型：

```typescript
// Agent 文字回复
{ type: "text", content: "我来分析这段故事..." }

// Agent 开始调用工具
{ type: "tool_start", tool: "generate_image", input: { prompt: "...", style: "xianxia" } }

// 工具执行完成
{ type: "tool_done", tool: "generate_image", result: "图像已生成，路径: /uploads/comic/gen_xxx.png" }

// 错误
{ type: "error", message: "工具执行失败: ..." }
```

---

## 四、页面布局设计

```text
┌──────────────────────────────────────────────────────────┐
│  漫剧 Agent 对话创作                                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─ 消息区域 ────────────────────────────────────────┐   │
│  │                                                    │   │
│  │  👤 用户: 帮我把这段变成漫剧：李逍遥初入仙灵岛...    │   │
│  │                                                    │   │
│  │  🤖 Agent: 好的！这是仙侠题材，我规划了4格分镜...    │   │
│  │                                                    │   │
│  │  ┌─ 🔧 generate_image ──────────────────────┐     │   │
│  │  │  style: xianxia                            │     │   │
│  │  │  prompt: "wide shot, mystical island..."   │     │   │
│  │  │  ✅ 完成 (23.4s)                           │     │   │
│  │  │  ┌──────────────┐                          │     │   │
│  │  │  │  📷 生成图片  │                          │     │   │
│  │  │  └──────────────┘                          │     │   │
│  │  └────────────────────────────────────────────┘     │   │
│  │                                                    │   │
│  │  🤖 Agent: 第1格完成 ✓ 正在生成第2格...             │   │
│  │                                                    │   │
│  │  ┌─ 🔧 generate_image ──────────────────────┐     │   │
│  │  │  ⏳ 执行中... (12.3s)                      │     │   │
│  │  └────────────────────────────────────────────┘     │   │
│  │                                                    │   │
│  └────────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ 输入区域 ────────────────────────────────────────┐   │
│  │  [📎] [输入消息...                        ] [发送]  │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 五、核心组件设计

### 5.1 消息类型定义

```typescript
interface AgentMessage {
  id: number
  type: 'user' | 'assistant' | 'tool_start' | 'tool_done' | 'error'
  content?: string          // type=user/assistant/error 时
  tool?: string             // type=tool_start/tool_done 时
  toolInput?: Record<string, any>  // type=tool_start 时
  toolResult?: string       // type=tool_done 时
  imageUrl?: string         // 从 toolResult 中提取的图片路径
  videoUrl?: string         // 从 toolResult 中提取的视频路径
  timestamp: string
  duration?: number         // 工具执行耗时(秒)
}
```

### 5.2 消息渲染规则

| type | 渲染方式 |
|---|---|
| `user` | 右侧蓝色气泡 |
| `assistant` | 左侧白色气泡，支持 Markdown |
| `tool_start` | 工具卡片（蓝色边框），显示工具名 + 参数 + 旋转加载图标 |
| `tool_done` | 工具卡片（绿色边框），显示结果 + 耗时 + 图片/视频预览 |
| `error` | 红色警告条 |

### 5.3 Mock 模拟策略

后端未就绪时，前端内置一套模拟流程：

1. 用户输入任意文本 → 延迟 500ms 返回 `text`（Agent 分析规划）
2. 延迟 1s → 返回 `tool_start`（generate_image）
3. 延迟 2s → 返回 `tool_done`（使用 picsum.photos 随机图片模拟）
4. 延迟 500ms → 返回 `text`（第1格完成）
5. 循环 2~3 格
6. 延迟 500ms → 返回 `text`（全部完成，是否动态化？）

---

## 六、实施步骤

```text
Step 1: 创建 api/comic-agent.ts（WebSocket 管理 + Mock）
Step 2: 创建 views/comic-agent/ComicAgentView.vue（页面组件）
Step 3: 修改 router/index.ts（新增路由）
Step 4: 修改 views/layout/MainLayout.vue（侧边栏菜单）
Step 5: 启动 dev server 验证
```

---

## 七、与现有页面的关系

| 页面 | 路由 | 状态 |
|---|---|---|
| 漫剧生成（表单式） | `/comic` | 保留，作为"快速模式" |
| **漫剧 Agent（对话式）** | `/comic-agent` | **新增** |

两个页面并存，用户可自由选择。侧边栏同时显示两个入口。
