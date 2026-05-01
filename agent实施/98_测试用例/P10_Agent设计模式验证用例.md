# P10 Agent 设计模式验证用例

## 用例 1：阶段模式映射完整

- **检查**：README 和 P10 文档
- **期望**：
  - [ ] P0.5 有 Event-Driven / Artifact-Centric
  - [ ] P1 有 DB State / Event Sourcing 基础
  - [ ] P2 有 Plan-and-Execute / TaskGraph
  - [ ] P3 有 Scheduler / State Machine
  - [ ] P4 有 CompletionAuditor
  - [ ] P5 有 Replanner
  - [ ] P7 有 Sandbox
  - [ ] P11 有 Budgeted Agent

## 用例 2：避免纯 Prompt 修补

- **场景**：任务只列计划不执行
- **期望**：
  - [ ] 使用 Auditor / TaskGraph 解决，不只加 prompt

## 用例 3：避免过早 Multi-Agent

- **检查**：P10 文档
- **期望**：
  - [ ] Multi-Agent 明确标为后期模式
  - [ ] 有暂缓理由

## 用例 4：设计模式能映射到代码模块

- **检查**：每种必须模式
- **期望**：
  - [ ] 能找到对应计划模块或现有模块
  - [ ] 没有只停留在概念层

## 用例 5：最终链路完整

- **检查**：P10 最终组合架构
- **期望**：
  - [ ] 从 User Goal 到 FinalReport 路径完整
  - [ ] 包含安全、预算、审计、恢复、状态层
