# P4 Auditor 测试用例

## 用例 1：全部完成

- **输入状态**：required steps 全部 succeeded，required artifacts verified=true
- **期望**：
  - [ ] status=completed
  - [ ] complete=true

## 用例 2：仍有 pending

- **输入状态**：存在 required step pending/ready/running
- **期望**：
  - [ ] status=incomplete
  - [ ] remaining_steps 不为空

## 用例 3：失败不可恢复

- **输入状态**：required step failed，retry_count >= max_retries，无 fallback
- **期望**：
  - [ ] status=failed
  - [ ] failed_steps 不为空

## 用例 4：阻塞需用户输入

- **输入状态**：缺少必要图片输入
- **期望**：
  - [ ] status=blocked
  - [ ] next_action.type=ask_user
