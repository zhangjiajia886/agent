/**
 * useConfig —— 配置数据加载与 toggle 处理 composable
 * 管理工具列表、模型列表、工作流列表、Prompt 列表的加载和更新。
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchModels, updateModel,
  fetchTools, updateTool,
  fetchWorkflows, updateWorkflow,
  fetchPrompts, updatePrompt,
  type ModelConfigItem, type ToolRegistryItem, type WorkflowTemplateItem,
  type AgentPromptItem,
} from '@/api/comic-agent'

export function useConfig() {
  const toolList = ref<ToolRegistryItem[]>([])
  const modelList = ref<ModelConfigItem[]>([])
  const workflowList = ref<WorkflowTemplateItem[]>([])
  const promptList = ref<AgentPromptItem[]>([])
  const selectedModel = ref('claude-sonnet-4-6')

  // ──────────── 可用 Agent 模型 ────────────
  const enabledAgentModels = computed(() =>
    modelList.value.filter(m => m.is_enabled && (m.category === 'agent_brain' || m.category === 'l1_llm'))
  )

  // ──────────── 加载 ────────────
  async function loadConfigData() {
    const token = localStorage.getItem('access_token')
    if (!token) return

    try { modelList.value = await fetchModels() }
    catch (e) { console.warn('[Agent] 模型加载失败', e) }

    try { toolList.value = await fetchTools() }
    catch (e) { console.warn('[Agent] 工具加载失败', e) }

    try { workflowList.value = await fetchWorkflows() }
    catch (e) { console.warn('[Agent] 工作流加载失败', e) }

    try { promptList.value = await fetchPrompts() }
    catch (e) { console.warn('[Agent] Prompt 加载失败', e) }

    // 自动选中默认 agent 模型
    const defaultAgent = modelList.value.find(m => m.is_enabled && m.is_default && m.category === 'agent_brain')
    if (defaultAgent) selectedModel.value = defaultAgent.model_id
  }

  onMounted(() => { loadConfigData() })

  // ──────────── Toggle 处理 ────────────
  async function handleToolToggle(id: number, val: boolean) {
    try { await updateTool(id, { is_enabled: val }) }
    catch { ElMessage.error('更新失败') }
  }

  async function handleModelToggle(id: number, val: boolean) {
    try { await updateModel(id, { is_enabled: val }) }
    catch { ElMessage.error('更新失败') }
  }

  async function handleSaveModelParams(row: ModelConfigItem) {
    try {
      await updateModel(row.id, { model_params: row.model_params || {} })
      ElMessage.success('模型参数已保存')
    } catch {
      ElMessage.error('保存失败')
    }
  }

  async function handleSaveModelConnection(row: ModelConfigItem) {
    try {
      await updateModel(row.id, {
        base_url: row.base_url || '',
        api_key: row.api_key || '',
        model_id: row.model_id,
      })
      ElMessage.success('服务连接配置已保存')
    } catch {
      ElMessage.error('保存失败')
    }
  }

  async function handleWorkflowToggle(id: number, val: boolean) {
    try { await updateWorkflow(id, { is_enabled: val }) }
    catch { ElMessage.error('更新失败') }
  }

  async function handlePromptToggle(id: number, val: boolean) {
    try { await updatePrompt(id, { is_enabled: val }) }
    catch { ElMessage.error('更新失败') }
  }

  async function handlePromptSave(p: AgentPromptItem) {
    try {
      await updatePrompt(p.id, { content: p.content })
      ElMessage.success(`Prompt "${p.display_name}" 已保存`)
    } catch {
      ElMessage.error('Prompt 保存失败')
    }
  }

  // ──────────── 辅助标签 ────────────
  function executorTagType(type: string): string {
    return ({ comfyui: 'primary', tts: 'success', local: 'info', http: 'warning' } as Record<string, string>)[type] || 'info'
  }

  function categoryTagType(cat: string): string {
    const m: Record<string, string> = {
      agent_brain: 'danger', l1_llm: 'warning', multimodal: 'warning',
      embedding: 'info', generation: 'success',
    }
    return m[cat] || 'info'
  }

  function categoryLabel(cat: string): string {
    const m: Record<string, string> = {
      agent_brain: 'Agent 大脑', l1_llm: '轻量 LLM', multimodal: '多模态',
      embedding: 'Embedding', generation: 'GPU 生成',
    }
    return m[cat] || cat
  }

  function wfCategoryTagType(cat: string): string {
    const m: Record<string, string> = {
      t2i: 'primary', edit: 'warning', face: 'danger',
      i2v: 'success', t2v: 'success', upscale: 'info', audio: '',
    }
    return m[cat] || 'info'
  }

  function wfCategoryLabel(cat: string): string {
    const m: Record<string, string> = {
      t2i: '文生图', edit: '图像编辑', face: '人脸保持',
      i2v: '图生视频', t2v: '文生视频', upscale: '超分辨率', audio: '音频',
    }
    return m[cat] || cat
  }

  return {
    toolList,
    modelList,
    workflowList,
    promptList,
    selectedModel,
    enabledAgentModels,
    loadConfigData,
    handleToolToggle,
    handleModelToggle,
    handleSaveModelParams,
    handleSaveModelConnection,
    handleWorkflowToggle,
    handlePromptToggle,
    handlePromptSave,
    executorTagType,
    categoryTagType,
    categoryLabel,
    wfCategoryTagType,
    wfCategoryLabel,
  }
}
