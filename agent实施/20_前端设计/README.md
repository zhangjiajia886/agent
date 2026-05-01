# 漫剧 Agent 前端设计

> 与后端 P0–P11 对应的前端模块设计。  
> 每个重要功能节点有独立目录，包含设计文档和基础知识讲解。

---

## 目录结构

```text
20_前端设计/
├── F1_任务工作台/        # 核心：步骤面板、状态流转、产物展示
├── F2_事件回放/          # P6 前端：断线恢复、历史事件重建
├── F3_审批交互/          # P5/P7 前端：工具审批确认、ask_user 对话
├── F4_工具管理/          # P8 前端：工具列表、健康状态、调用统计
├── F5_预算展示/          # P11 前端：Token/工具/成本预算面板
├── F6_Trace时间线/       # P6 前端：工具调用详情、执行耗时可视化
└── F7_组件拆分/          # 架构：ComicAgentView 拆分为可维护的子组件
```

---

## 设计原则

- 每个目录包含 `设计文档.md` 和 `基础知识讲解.md`。
- 前端组件与后端事件协议对齐（task_created / step_update / tool_done / artifact_created / done）。
- 优先拆分组件，后续可独立迭代。
- 使用 Vue 3 Composition API + TypeScript。

---

## 与后端的映射关系

| 前端模块 | 对应后端阶段 | 关键 API / 事件 |
|---|---|---|
| F1 任务工作台 | P0/P3 | WebSocket 事件流、`GET /tasks/{uid}` |
| F2 事件回放 | P6 | `GET /tasks/{uid}/events`、`GET /tasks/{uid}/trace` |
| F3 审批交互 | P5/P7 | WebSocket `tool_confirm`、`approve/reject` 消息 |
| F4 工具管理 | P8 | `GET /tools/health`、`GET /tools/stats` |
| F5 预算展示 | P11 | `done.metadata.budget_usage` |
| F6 Trace 时间线 | P6 | `GET /tasks/{uid}/trace` |
| F7 组件拆分 | — | 架构重构 |
