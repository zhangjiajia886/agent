# P3 Scheduler 测试用例

## 用例 1：依赖顺序

- **TaskGraph**：s1 image → s2 video
- **期望**：
  - [ ] s1 succeeded 前 s2 不会 running
  - [ ] s1 succeeded 后 s2 ready

## 用例 2：并行 ready steps

- **TaskGraph**：s1 image；s2 tts；s3 merge depends_on s1,s2
- **期望**：
  - [ ] s1 和 s2 可同时 ready
  - [ ] s3 等待 s1/s2 都 succeeded

## 用例 3：失败阻断下游

- **TaskGraph**：s1 image failed；s2 video depends_on s1
- **期望**：
  - [ ] s2 不执行
  - [ ] 进入 Replanner 或 failed/blocked

## 用例 4：用户审批

- **工具**：高风险工具
- **期望**：
  - [ ] step awaiting_approval
  - [ ] 用户 approve 后 running
  - [ ] 用户 reject 后 canceled/skipped
