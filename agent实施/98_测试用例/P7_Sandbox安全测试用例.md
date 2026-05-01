# P7 Sandbox 安全测试用例

## 用例 1：禁止危险命令

- **工具**：bash
- **输入**：`rm -rf /`
- **期望**：
  - [ ] 工具不执行
  - [ ] 返回 ToolResult.status=error/blocked
  - [ ] error_code=SHELL_COMMAND_BLOCKED
  - [ ] 产生 `sandbox_check` 事件

## 用例 2：禁止读取敏感文件

- **工具**：read_file 或 bash cat
- **输入**：`backend/.env`
- **期望**：
  - [ ] 读取被拒绝
  - [ ] 不返回文件内容
  - [ ] 记录审计事件

## 用例 3：限制写入目录

- **工具**：write_file
- **输入**：写入 `/tmp/outside.txt` 或项目根目录敏感文件
- **期望**：
  - [ ] 非允许目录写入被拒绝
  - [ ] 允许写入 `uploads/agent_outputs/`

## 用例 4：HTTP 白名单

- **工具**：http_request
- **输入**：访问非白名单 host
- **期望**：
  - [ ] 自动执行模式下被阻止或要求审批
  - [ ] 访问 metadata IP 被拒绝

## 用例 5：超时控制

- **工具**：python_exec/bash
- **输入**：无限循环
- **期望**：
  - [ ] 超时终止
  - [ ] 返回 timeout 错误
  - [ ] 记录 duration
