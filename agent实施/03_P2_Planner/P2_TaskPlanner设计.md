# P2 TaskPlanner 设计

> 所属阶段：P2  
> 状态：待实施  
> 目标：从关键词 RuntimeStep 升级为结构化 TaskGraph Planner。

---

## 1. 背景

P0/P1 的任务步骤来自简单规则推断，不能稳定表达依赖关系、并行关系和 required artifact。

P2 要引入正式 `TaskPlanner`。

## 2. 目标

- [ ] 生成结构化 TaskGraph。
- [ ] 支持图片、视频、TTS、合成、多格漫剧模板。
- [ ] 支持 `depends_on`。
- [ ] 支持 `required` 标记。
- [ ] 支持工具可用性校验。

## 3. 非目标

- 不执行调度。
- 不实现 Replanner。
- 不做复杂 LLM 自由规划。

## 4. 目标文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `task_runtime/planner.py` | 新增 | Planner 主实现 |
| `task_runtime/models.py` | 新增/修改 | PlannedTask / PlannedStep |
| `task_runtime/store.py` | 修改 | 写入 PlannedStep |
| `agent_runner.py` | 修改 | 调用 Planner |

## 5. Planner 输入

```python
@dataclass
class PlanningInput:
    user_goal: str
    style: str
    frames: int
    tts: bool
    auto_video: bool
    image_paths: list[str]
    selected_model: str
    available_tools: list[ToolRegistry]
```

## 6. Planner 输出

```python
@dataclass
class PlannedStep:
    step_uid: str
    title: str
    description: str
    step_type: str
    tool_name: str | None
    depends_on: list[str]
    inputs: dict
    required: bool
    output_artifact_types: list[str]
    sort_order: int
```

## 7. 模板设计

### 单图生成

```text
s1 generate_image
```

### 图生视频

```text
s1 generate_image
s2 image_to_video depends_on s1
```

### 图 + 视频 + 旁白 + 合成

```text
s1 generate_image
s2 image_to_video depends_on s1
s3 text_to_speech
s4 merge_media depends_on s2,s3
```

### 多格漫剧

```text
s1 plan_storyboard
s2 generate_image frame=1 depends_on s1
s3 generate_image frame=2 depends_on s1
s4 generate_image frame=3 depends_on s1
s5 generate_image frame=4 depends_on s1
s6 merge_comic depends_on s2,s3,s4,s5
```

## 8. 工具可用性校验

- 工具未启用：step blocked。
- 有 fallback：写入 fallback_tools。
- 无工具：任务 blocked 或 ask_user。

## 9. 工具能力元数据设计

Planner 不能只依赖工具名称和 description。为了生成可靠 TaskGraph，需要给每个工具补充能力元数据。

### 9.1 推荐字段

优先放入 `ToolRegistry.executor_config` 或后续扩展独立字段：

```json
{
  "risk_level": "L1",
  "requires_approval": false,
  "auto_mode_allowed": true,
  "input_artifact_types": ["image"],
  "output_artifact_types": ["video"],
  "fallback_tools": ["jimeng_generate_video"],
  "supports_batch": false,
  "supports_frame": true,
  "supports_parallel": true,
  "max_parallel": 2,
  "required_inputs": ["source_image"],
  "optional_inputs": ["motion_prompt", "duration"],
  "cost_level": "medium",
  "timeout_seconds": 300
}
```

### 9.2 字段说明

| 字段 | 用途 |
|---|---|
| `risk_level` | Planner/Scheduler 判断审批策略 |
| `requires_approval` | 是否默认需要用户确认 |
| `auto_mode_allowed` | 自动执行模式是否允许 |
| `input_artifact_types` | 该工具需要什么上游产物 |
| `output_artifact_types` | 该工具会产出什么 |
| `fallback_tools` | 失败时可替代工具 |
| `supports_batch` | 是否支持批量 |
| `supports_frame` | 是否支持多格 frame 参数 |
| `supports_parallel` | 是否允许并行执行 |
| `max_parallel` | 最大并发 |
| `required_inputs` | 必填参数 |
| `optional_inputs` | 可选参数 |
| `cost_level` | 成本等级 |
| `timeout_seconds` | 默认超时 |

### 9.3 漫剧核心工具能力示例

#### generate_image

```json
{
  "risk_level": "L1",
  "auto_mode_allowed": true,
  "input_artifact_types": [],
  "output_artifact_types": ["image"],
  "fallback_tools": ["jimeng_generate_image"],
  "supports_frame": true,
  "supports_parallel": true,
  "required_inputs": ["prompt"]
}
```

#### image_to_video

```json
{
  "risk_level": "L1",
  "auto_mode_allowed": true,
  "input_artifact_types": ["image"],
  "output_artifact_types": ["video"],
  "fallback_tools": ["jimeng_generate_video"],
  "supports_parallel": false,
  "required_inputs": ["source_image"]
}
```

#### text_to_speech

```json
{
  "risk_level": "L1",
  "auto_mode_allowed": true,
  "input_artifact_types": [],
  "output_artifact_types": ["audio"],
  "fallback_tools": [],
  "supports_parallel": true,
  "required_inputs": ["text"]
}
```

#### merge_media

```json
{
  "risk_level": "L1",
  "auto_mode_allowed": true,
  "input_artifact_types": ["video", "audio"],
  "output_artifact_types": ["video"],
  "fallback_tools": [],
  "supports_parallel": false,
  "required_inputs": ["video_path", "audio_path"]
}
```

### 9.4 Planner 使用方式

```text
用户目标
  ↓
规则模板生成候选 step
  ↓
读取 ToolRegistry 能力元数据
  ↓
校验工具是否启用
  ↓
校验输入产物依赖
  ↓
写入 output_artifact_types / required_inputs / fallback_tools
  ↓
生成可调度 TaskGraph
```

### 9.5 与 Scheduler 的关系

Planner 负责生成：

- `depends_on`
- `required_inputs`
- `output_artifact_types`
- `fallback_tools`
- `risk_level`

Scheduler 使用这些字段判断：

- 什么时候 step ready。
- 是否允许 auto_mode。
- 是否能并行。
- 失败后是否进入 Replanner。

## 10. TODO

- [ ] 新建 `planner.py`。
- [ ] 定义 PlannedTask / PlannedStep。
- [ ] 实现规则模板。
- [ ] 接入 style/frames/tts/autoVideo/image_paths。
- [ ] 接入工具可用性校验。
- [ ] 写入 `AgentStep.depends_on`。
- [ ] 为核心工具补充能力元数据。
- [ ] Planner 读取 `ToolRegistry.executor_config`。
- [ ] 缺少 required input 时生成 blocked/ask_user。

## 11. 验收标准

- [ ] 复杂创作任务能生成带依赖的 TaskGraph。
- [ ] 多格任务能生成多 frame 步骤。
- [ ] 缺工具时明确 blocked。
- [ ] 前端计划来自后端。
- [ ] Planner 生成的每个工具 step 都有输入/输出产物类型。
- [ ] 禁用工具不会被 Planner 放入可执行步骤。
