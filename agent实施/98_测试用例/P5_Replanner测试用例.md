# P5 Replanner 测试用例

## 用例 1：retry

- **输入**：ToolResult error retryable=true，retry_count < max_retries
- **期望**：
  - [ ] action=retry
  - [ ] next_tool 为原工具

## 用例 2：fallback

- **输入**：generate_image 失败，fallback_tools 包含 jimeng_generate_image
- **期望**：
  - [ ] action=fallback_tool
  - [ ] next_tool=jimeng_generate_image

## 用例 3：ask_user

- **输入**：缺少图片输入，ArtifactMemory 无可用图片
- **期望**：
  - [ ] action=ask_user
  - [ ] question 不为空
  - [ ] choices 不为空

## 用例 4：防无限循环

- **输入**：同一 step 连续失败超过预算
- **期望**：
  - [ ] action=fail 或 block
  - [ ] 不继续 retry
