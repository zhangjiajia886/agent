# 漫剧 Agent 实施目录

> 目的：把漫剧 Agent vNext 的设计、实施、验证、复盘统一放入独立目录管理。  
> 规则：每实施一个重要任务，都必须先建立对应的独立设计文档，再进行代码修改和验证。

---

## 目录结构

```text
agent实施/
├── 00_既有设计归档/          # 已有重要设计文档副本
├── 01_P0_验证/               # P0 已实现能力的验证与修复
├── 02_P1_持久化/             # Task/Step/Artifact/Event/ToolInvocation 落库
├── 03_P2_Planner/            # TaskPlanner 与 TaskGraph 明确化
├── 04_P3_Scheduler_Executor/ # Scheduler 与 StepExecutor
├── 05_P4_Auditor/            # CompletionAuditor 独立化
├── 06_P5_Replanner/          # Replanner / RecoveryPolicy
├── 07_P6_恢复与观测/          # 断线恢复、事件回放、Tracing
├── 08_P7_沙箱与安全/          # Sandbox、权限隔离、审批、安全审计
├── 09_P8_工具治理/            # 工具能力元数据、风险等级、fallback、健康检查
├── 10_P9_数据库与Redis状态层/  # DB 权威状态与 Redis 运行时状态边界
├── 11_P10_Agent设计模式/       # Agent 设计模式选型与组合架构
├── 12_P11_成本与预算控制/      # Token/GPU/API/视频生成等预算控制
├── 98_测试用例/              # 各阶段测试用例和验收样例
└── 99_实施记录/              # 每次实施记录、测试结果、问题复盘
```

---

## 实施铁律

- [ ] 每个重要任务开始前，必须在对应目录创建独立设计文档。
- [ ] 设计文档必须包含：目标、范围、涉及文件、数据流、事件协议、风险、验收标准。
- [ ] 代码修改后必须更新对应设计文档的“实施结果”。
- [ ] 验证命令和结果必须记录到 `99_实施记录/`。
- [ ] 不删除原始设计文档；本目录中的 `00_既有设计归档` 是副本。
- [ ] 每个阶段实施前必须在 `98_测试用例/` 中补充或更新对应测试用例。
- [ ] 每个目录必须包含 `基础知识讲解.md`，用于说明概念、价值、优缺点和竞品对比。

---

## 实施状态看板

| 阶段 | 设计文档 | 测试用例 | 当前状态 | 下一步 |
|---|---|---|---|---|
| P0.5 状态闭环验证 | `01_P0_验证/P0.5_状态闭环验证设计.md` | `98_测试用例/P0.5_状态闭环验证用例.md` | 待实施 | 启动前后端执行端到端验证 |
| P1 状态持久化 | `02_P1_持久化/P1_任务状态持久化设计.md` | `98_测试用例/P1_持久化测试用例.md` | **已落地** | 端到端运行时验证 |
| P9 数据库与 Redis 状态层 | `10_P9_数据库与Redis状态层/P9_数据库与Redis状态层设计.md` | `98_测试用例/P9_数据库与Redis状态层测试用例.md` | **已落地** | Alembic migration / 工具健康缓存接入 |
| P10 Agent 设计模式 | `11_P10_Agent设计模式/P10_Agent设计模式选型.md` | `98_测试用例/P10_Agent设计模式验证用例.md` | **已落地** | 后续模块实施时标注设计模式 |
| P2 TaskPlanner | `03_P2_Planner/P2_TaskPlanner设计.md` | `98_测试用例/P2_Planner测试用例.md` | **已落地** | style/image_paths 参数 / depends_on 持久化 |
| P3 Scheduler / Executor | `04_P3_Scheduler_Executor/P3_Scheduler与StepExecutor设计.md` | `98_测试用例/P3_Scheduler测试用例.md` | 待实施 | 实现 ready step 计算 |
| P4 CompletionAuditor | `05_P4_Auditor/P4_CompletionAuditor设计.md` | `98_测试用例/P4_Auditor测试用例.md` | 待实施 | 独立审计规则 |
| P5 Replanner | `06_P5_Replanner/P5_Replanner与RecoveryPolicy设计.md` | `98_测试用例/P5_Replanner测试用例.md` | 待实施 | 定义 retry/fallback/ask_user |
| P6 恢复与观测 | `07_P6_恢复与观测/P6_断线恢复事件回放与Tracing设计.md` | `98_测试用例/P6_恢复与观测测试用例.md` | 待实施 | 事件回放和任务控制 API |
| P7 沙箱与安全 | `08_P7_沙箱与安全/P7_Sandbox与安全隔离设计.md` | `98_测试用例/P7_Sandbox安全测试用例.md` | **已落地** | 审计事件持久化 / 自动化测试 |
| P8 工具治理 | `09_P8_工具治理/P8_工具治理设计.md` | `98_测试用例/P8_工具治理测试用例.md` | **已落地** | 健康检查 / 工具统计 / API 暴露 |
| P11 成本与预算控制 | `12_P11_成本与预算控制/P11_成本与预算控制设计.md` | `98_测试用例/P11_成本预算测试用例.md` | **已落地** | 前端预算展示 / budget_warning 事件 |

---

## 基础知识讲解文档

每个目录都包含 `基础知识讲解.md`，内容包括：

- 这个技术是什么。
- 为什么要用。
- 好处。
- 弊端。
- 替代方案/竞争技术。
- 与竞争方案对比。
- ASCII 图示。

---

## 当前推荐实施顺序

```text
01_P0_验证
  ↓
02_P1_持久化
  ↓
10_P9_数据库与Redis状态层
  ↓
11_P10_Agent设计模式
  ↓
08_P7_沙箱与安全
  ↓
09_P8_工具治理
  ↓
12_P11_成本与预算控制
  ↓
03_P2_Planner
  ↓
04_P3_Scheduler_Executor
  ↓
05_P4_Auditor
  ↓
06_P5_Replanner
  ↓
07_P6_恢复与观测
```

---

## 已归档的重要文档

- `漫剧agent深度分析.md`
- `漫剧agent深度优化设计.md`
- `主流agent知识体系.md`
- `主流agent对比.md`
- `漫剧agent优化TODO.md`
- `agent设计实施计划.md`
- `agent改造设计.md`
