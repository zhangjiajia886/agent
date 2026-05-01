# P7 Sandbox 与安全隔离设计

> 所属阶段：P7  
> 状态：最小实现已落地  
> 目标：为 Agent 工具执行建立安全隔离、权限审批和审计机制。

---

## 1. 背景

当前 Agent 已具备 `bash`、`python_exec`、`write_file`、`edit_file`、`http_request` 等高能力工具。随着自动执行能力增强，如果缺少沙箱，存在文件破坏、密钥泄露、任意外连和资源失控风险。

## 2. 目标

- [x] 定义工具风险等级（L0-L4）。
- [x] 定义 SandboxPolicy（路径 / 命令 / 网络 denylist）。
- [x] 限制文件访问范围（denied_filenames / denied_path_patterns）。
- [x] 限制网络访问范围（denied_hosts / denied_network_cidrs）。
- [x] 限制执行时间和输出大小（policy.timeout_seconds / max_output_chars）。
- [x] 隔离敏感环境变量（python_exec 检查 os.environ）。
- [x] 高风险操作强制拦截（L4 直接 block）。
- [ ] 工具执行审计落库（待 sandbox_check 事件持久化）。

## 3. 非目标

- 首期不实现 Docker 强隔离。
- 首期不实现多租户安全边界。
- 首期不允许 Agent 任意安装系统依赖。

## 4. 涉及文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/app/core/comic_chat_agent/sandbox.py` | 新增 | SandboxPolicy / SandboxExecutor |
| `backend/app/core/comic_chat_agent/tool_executor.py` | 修改 | 高风险工具接入沙箱 |
| `backend/app/core/comic_chat_agent/agent_runner.py` | 修改 | 审批与沙箱事件 |
| `backend/app/models/agent_config.py` | 可能修改 | ToolRegistry 风险字段 |
| `backend/app/models/agent_task.py` | 可能修改 | 审计记录扩展 |

## 5. 风险等级

| 等级 | 类型 | 示例 | 策略 |
|---|---|---|---|
| L0 | 只读安全 | list_dir/read_file 限定目录 | 自动执行 |
| L1 | 创作类 | generate_image/text_to_speech | auto_mode 可自动执行 |
| L2 | 文件写入/HTTP | write_file/edit_file/http_request | 审批 + 沙箱 |
| L3 | 命令执行 | bash/python_exec | 强审批 + 沙箱 |
| L4 | 禁止级 | rm -rf、读取 .env、外发密钥 | 默认禁止 |

## 6. SandboxPolicy

```python
@dataclass
class SandboxPolicy:
    allowed_read_dirs: list[str]
    allowed_write_dirs: list[str]
    denied_paths: list[str]
    network_mode: Literal['deny', 'allowlist', 'open']
    allowed_hosts: list[str]
    timeout_seconds: int
    max_output_chars: int
    allow_subprocess: bool
    env_allowlist: list[str]
```

## 7. 文件系统策略

允许：

```text
backend/uploads/agent_outputs/
backend/uploads/agent_uploads/
/tmp/ttsapp_agent_tasks/{task_uid}/
```

禁止：

```text
.env
backend/.env
~/.ssh/
.git/
node_modules/
系统根目录写入
```

## 8. 网络策略

首期建议：

```text
http_request 默认需要审批
仅允许白名单 host
禁止访问内网敏感地址
禁止访问 metadata IP
```

禁止地址：

```text
127.0.0.1 非白名单端口
169.254.169.254
0.0.0.0
私有网段非白名单
```

## 9. 命令策略

禁止命令片段：

```text
rm -rf /
mkfs
dd if=
chmod -R 777
curl ... | sh
wget ... | sh
:(){:|:&};:
```

## 10. 审计事件

新增事件建议：

```json
{
  "type": "sandbox_check",
  "task_uid": "task_xxx",
  "step_uid": "step_xxx",
  "tool": "bash",
  "risk_level": "L3",
  "decision": "blocked",
  "reason": "命令包含危险片段 rm -rf"
}
```

## 11. TODO

- [x] 新建 `sandbox.py`。
- [x] 定义 `SandboxPolicy`。
- [x] 定义路径 allowlist/denylist。
- [x] 为 `bash/python_exec/write_file/edit_file/http_request/read_file/web_fetch` 接入沙箱检查。
- [x] 高风险拒绝返回结构化 error + error_code + risk_level。
- [ ] 增加 `sandbox_check` 审计事件持久化。
- [ ] 增加自动化测试。

## 12. 验收标准

- [x] `bash rm -rf /` 被阻止。
- [x] 读取 `.env` 被阻止。
- [x] 写入非允许目录被阻止。
- [x] http_request 访问 metadata IP 被阻止。
- [x] 安全拒绝返回结构化 error / error_code / risk_level。
- [ ] 审计事件持久化（待 P1 审计扩展）。
