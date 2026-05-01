"""P0.5 状态闭环验证 —— 全模块 import + 功能烟测（无需 .env）"""
import sys, os, types

sys.path.insert(0, ".")
sys.path.insert(0, os.path.join(".", "backend"))

# mock app.config 模块以避免 .env 依赖
_mock_config = types.ModuleType("app.config")
_mock_config.settings = types.SimpleNamespace(
    COMFYUI_BASE_URL="http://localhost:8188",
    UPLOAD_DIR="/tmp/uploads",
)
sys.modules["app.config"] = _mock_config

from backend.app.core.comic_chat_agent.task_runtime import RuntimeTask, RuntimeStep, audit_task
from backend.app.core.comic_chat_agent.tool_capability import TOOL_CAPABILITIES, get_capability, get_fallbacks
from backend.app.core.comic_chat_agent.budget import BudgetController
from backend.app.core.comic_chat_agent.task_planner import TaskPlanner
from backend.app.core.comic_chat_agent.task_scheduler import TaskScheduler
from backend.app.core.comic_chat_agent.completion_auditor import CompletionAuditor
from backend.app.core.comic_chat_agent.replanner import Replanner
from backend.app.core.comic_chat_agent.event_tracer import EventTracer, TraceType
from backend.app.core.comic_chat_agent.sandbox import SandboxChecker
from backend.app.core.comic_chat_agent.agent_protocols import TaskPlannerProtocol
print("[OK] All imports")

# P2
planner = TaskPlanner()
steps = planner.plan("生成图片并转视频，配旁白，合成完整视频")
print(f"[OK] P2 plan: {len(steps)} steps")
for s in steps:
    print(f"     {s.title}  tool={s.tool_name}  deps={s.depends_on}")

# P3
rt = planner.plan_to_runtime("生成图片并转视频")
sched = TaskScheduler(rt)
d = sched.evaluate()
print(f"[OK] P3 scheduler: ready={len(d.ready_steps)} all_done={d.all_done}")

# P4
auditor = CompletionAuditor()
r = auditor.audit(rt)
print(f"[OK] P4 audit: status={r.status} remaining={len(r.remaining_steps)}")

# P5
rp = Replanner()
fs = RuntimeStep(step_uid="s1", title="t", tool_name="generate_image", status="failed")
rd = rp.decide(rt, fs, {"message": "timeout error"})
print(f"[OK] P5 replan: action={rd.action} next_tool={rd.next_tool}")

# P6
tr = EventTracer(task_uid="test")
tr.trace_llm_call(model="m", input_tokens=100, output_tokens=50)
tr.trace_tool_call(tool_name="generate_image", status="ok", duration_ms=1500)
print(f"[OK] P6 tracer: {len(tr.records)} records")

# P8
cap = get_capability("generate_image")
print(f"[OK] P8 capability: risk={cap.risk_level} fallbacks={cap.fallback_tools}")

# P11
bc = BudgetController()
bc.record_tool_call("generate_image")
bc.record_tokens(500, 200)
print(f"[OK] P11 budget: tool_calls={bc.usage.tool_calls}")

print("\n=== All P0.5 verification PASSED ===")
