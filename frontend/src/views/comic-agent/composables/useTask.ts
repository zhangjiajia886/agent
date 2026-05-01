/**
 * useTask —— 任务状态管理 composable
 * 从 ComicAgentView.vue 提取的任务/步骤/产物/日志管理逻辑。
 */
import { ref } from 'vue'
import type {
  TaskStatus, StepStatus, ArtifactType,
  TaskStep, TaskLog, AgentTaskViewModel,
} from '../types'
import { TOOL_NAMES } from '../types'

// ──────────── 工具显示辅助 ────────────
const TOOL_HINTS: Record<string, string> = {
  generate_image: '正在调用图像生成服务，通常需要 15-60 秒。',
  image_to_video: '正在生成视频内容，通常需要 30-120 秒。',
  bash: '正在执行系统命令。',
  python_exec: '正在执行 Python 代码。',
  web_search: '正在检索网络信息。',
  web_fetch: '正在获取网页内容。',
}

export function toolDisplayName(name?: string): string {
  return name ? (TOOL_NAMES[name] || `工具：${name}`) : '未识别工具'
}

export function toolHint(name?: string): string {
  return name ? (TOOL_HINTS[name] || '') : ''
}

export function taskStatusLabel(status: TaskStatus): string {
  const map: Record<TaskStatus, string> = {
    idle: '待启动', running: '执行中', awaiting_approval: '等待确认',
    completed: '已完成', failed: '执行失败', canceled: '已取消',
  }
  return map[status]
}

export function taskStatusType(status: TaskStatus): string {
  const map: Record<TaskStatus, string> = {
    idle: 'info', running: 'primary', awaiting_approval: 'warning',
    completed: 'success', failed: 'danger', canceled: 'info',
  }
  return map[status]
}

export function stepStatusLabel(status: StepStatus): string {
  const map: Record<StepStatus, string> = {
    pending: '待执行', running: '处理中', awaiting_approval: '待确认',
    completed: '已完成', failed: '失败', canceled: '已取消',
  }
  return map[status]
}

export function stepStatusType(status: StepStatus): string {
  const map: Record<StepStatus, string> = {
    pending: 'info', running: 'primary', awaiting_approval: 'warning',
    completed: 'success', failed: 'danger', canceled: 'info',
  }
  return map[status]
}

// ──────────── 状态映射 ────────────
export function mapServerStepStatus(status?: string): StepStatus {
  if (status === 'succeeded') return 'completed'
  if (status === 'awaiting_approval') return 'awaiting_approval'
  if (status === 'failed' || status === 'blocked') return 'failed'
  if (status === 'canceled' || status === 'skipped') return 'canceled'
  if (status === 'running') return 'running'
  return 'pending'
}

export function mapServerTaskStatus(status?: string): TaskStatus {
  if (status === 'completed') return 'completed'
  if (status === 'failed' || status === 'blocked' || status === 'incomplete') return 'failed'
  if (status === 'canceled') return 'canceled'
  if (status === 'awaiting_approval') return 'awaiting_approval'
  return 'running'
}

// ──────────── useTask composable ────────────
export function useTask() {
  const activeTask = ref<AgentTaskViewModel | null>(null)

  // ── 意图推断 ──
  function inferIntent(text: string): string {
    if (/视频|动态|图生视频|旁白|配音|音频/.test(text)) return '多步骤创作任务'
    if (/编辑|修改|改成|变成|弄成|超分|高清/.test(text)) return '图像编辑任务'
    if (/漫剧|漫画|分镜|[2-6]\s*格/.test(text)) return '漫剧生成任务'
    if (/生成|画|图片|图像/.test(text)) return '图像生成任务'
    return '综合创作任务'
  }

  // ── 构建初始计划 ──
  function buildInitialPlan(text: string): TaskStep[] {
    const steps: TaskStep[] = [{
      id: `analysis-${Date.now()}`,
      title: '需求分析与执行策略确认',
      description: '识别任务目标、创作约束、输入素材与后续工具调用路径。',
      status: 'completed',
      startedAt: new Date().toISOString(),
      finishedAt: new Date().toISOString(),
    }]

    if (/生成|画|图片|图像|漫剧|漫画/.test(text)) {
      steps.push({
        id: `plan-generate-${Date.now()}`, tool: 'generate_image',
        title: '生成首版视觉结果',
        description: '根据需求生成图片或分镜视觉产物，并作为后续步骤输入。',
        status: 'pending',
      })
    }
    if (/编辑|修改|改成|变成|弄成|幸福|开心|高清|超分/.test(text)) {
      steps.push({
        id: `plan-edit-${Date.now()}`,
        tool: /超分|高清/.test(text) ? 'upscale_image' : 'edit_image',
        title: /超分|高清/.test(text) ? '增强图像清晰度' : '执行图像编辑',
        description: '根据用户要求调整图片内容、情绪、风格或画面质量。',
        status: 'pending',
      })
    }
    if (/视频|动态|动起来|图生视频/.test(text)) {
      steps.push({
        id: `plan-video-${Date.now()}`, tool: 'image_to_video',
        title: '制作动态视频',
        description: '将已生成或已上传图片转化为动态视频。',
        status: 'pending',
      })
    }
    if (/旁白|配音|语音|音频/.test(text)) {
      steps.push({
        id: `plan-audio-${Date.now()}`, tool: 'text_to_speech',
        title: '生成旁白音频',
        description: '根据指定文本合成旁白语音。',
        status: 'pending',
      })
    }
    if (steps.length === 1) {
      steps.push({
        id: `plan-execute-${Date.now()}`,
        title: '执行核心任务',
        description: '根据 Agent 判断选择合适工具完成本轮请求。',
        status: 'pending',
      })
    }
    return steps
  }

  // ── 创建任务 ──
  function createTask(text: string) {
    const intent = inferIntent(text)
    activeTask.value = {
      id: `task-${Date.now()}`,
      title: '创作任务工作台',
      userRequest: text,
      intent,
      analysis: text.length > 72 ? `${text.slice(0, 72)}...` : text,
      currentStage: '已完成需求分析，正在等待执行计划落地。',
      status: 'running',
      steps: buildInitialPlan(text),
      artifacts: [],
      logs: [],
    }
  }

  // ── 日志 ──
  function addTaskLog(title: string, content?: string, stepId?: string) {
    if (!activeTask.value || !content) return
    activeTask.value.logs.push({
      id: `log-${Date.now()}-${activeTask.value.logs.length}`,
      stepId, title, content,
      timestamp: new Date().toISOString(),
    })
  }

  function stepLogs(step: TaskStep): TaskLog[] {
    if (!activeTask.value) return []
    return activeTask.value.logs.filter(log => log.stepId === step.id)
  }

  function compactLogContent(content: string): string {
    const text = content.replace(/\s+/g, ' ').trim()
    return text.length > 220 ? `${text.slice(0, 220)}...` : text
  }

  // ── 步骤查找/创建 ──
  function findTaskStepByTool(tool?: string, toolCallId?: string): TaskStep | undefined {
    if (!activeTask.value) return undefined
    if (toolCallId) {
      const byCall = activeTask.value.steps.find(s => s.toolCallId === toolCallId)
      if (byCall) return byCall
    }
    if (tool) {
      const running = activeTask.value.steps.find(s => s.tool === tool && ['running', 'awaiting_approval', 'pending'].includes(s.status))
      if (running) return running
    }
    return activeTask.value.steps.find(s => s.status === 'pending')
  }

  function ensureToolStep(tool?: string, description?: string, toolCallId?: string): TaskStep | undefined {
    if (!activeTask.value) return undefined
    let step = findTaskStepByTool(tool, toolCallId)
    if (!step) {
      step = {
        id: `step-${Date.now()}-${activeTask.value.steps.length}`,
        tool, toolCallId,
        title: toolDisplayName(tool),
        description: description || toolHint(tool) || '执行本阶段所需操作。',
        status: 'pending',
      }
      activeTask.value.steps.push(step)
    }
    if (tool) step.tool = tool
    if (toolCallId) step.toolCallId = toolCallId
    if (description) step.description = description
    return step
  }

  // ── 产物 ──
  function addArtifact(type: ArtifactType, url: string, fromStep: string) {
    if (!activeTask.value) return
    if (activeTask.value.artifacts.some(item => item.url === url)) return
    activeTask.value.artifacts.push({
      id: `artifact-${Date.now()}-${activeTask.value.artifacts.length}`,
      type, url, fromStep,
      title: type === 'image' ? '图像结果' : type === 'video' ? '视频结果' : type === 'audio' ? '音频结果' : '文件结果',
    })
  }

  // ── 后端步骤/产物同步 ──
  function upsertServerStep(raw: Record<string, any>) {
    if (!activeTask.value) return
    const id = raw.step_uid || raw.id
    if (!id) return
    let step = activeTask.value.steps.find(s => s.id === id)
    if (!step) {
      step = {
        id,
        tool: raw.tool_name || raw.tool,
        title: raw.title || toolDisplayName(raw.tool_name || raw.tool),
        description: raw.description || '后端任务图步骤。',
        status: mapServerStepStatus(raw.status),
      }
      activeTask.value.steps.push(step)
    }
    step.tool = raw.tool_name || raw.tool || step.tool
    step.title = raw.title || step.title
    step.description = raw.description || step.description
    step.status = mapServerStepStatus(raw.status)
    if (raw.status === 'running') step.startedAt = step.startedAt || new Date().toISOString()
    if (['succeeded', 'failed', 'blocked', 'canceled', 'skipped'].includes(raw.status)) step.finishedAt = step.finishedAt || new Date().toISOString()
  }

  function upsertServerArtifact(raw: Record<string, any>, stepId?: string) {
    const type = (raw.type || raw.artifact_type || 'file') as ArtifactType
    const url = raw.url
    if (!url || !['image', 'video', 'audio', 'file'].includes(type)) return
    addArtifact(type, url, stepId || raw.step_uid || 'server')
  }

  // ── 重置 ──
  function resetTask() {
    activeTask.value = null
  }

  return {
    activeTask,
    createTask,
    resetTask,
    addTaskLog,
    stepLogs,
    compactLogContent,
    findTaskStepByTool,
    ensureToolStep,
    addArtifact,
    upsertServerStep,
    upsertServerArtifact,
  }
}
