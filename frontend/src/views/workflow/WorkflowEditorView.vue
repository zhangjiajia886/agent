<template>
  <div class="workflow-page">
    <!-- ── 顶部工具栏 ── -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="selectedWorkflowId" placeholder="选择工作流" style="width: 240px" @change="loadWorkflow">
          <el-option v-for="wf in workflows" :key="wf.id" :label="wf.name" :value="wf.id" />
        </el-select>
        <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">新建</el-button>
        <el-button :icon="Delete" :disabled="!selectedWorkflowId" @click="handleDelete">删除</el-button>
      </div>
      <div class="toolbar-right">
        <el-button type="success" :icon="VideoPlay" :disabled="!selectedWorkflowId" :loading="executing" @click="showExecuteDialog = true">
          执行
        </el-button>
        <el-button :icon="Check" :disabled="!dirty" @click="saveWorkflow">保存</el-button>
      </div>
    </div>

    <!-- ── 主体：左侧节点面板 + 中间画布 + 右侧属性 ── -->
    <div class="editor-body">
      <!-- 左侧节点面板 -->
      <div class="node-palette">
        <div class="palette-title">节点类型</div>
        <div
          v-for="nt in nodeTypes"
          :key="nt.type"
          class="palette-item"
          draggable="true"
          @dragstart="onDragStart($event, nt.type)"
        >
          <span class="palette-icon">{{ nt.icon }}</span>
          <span>{{ nt.label }}</span>
        </div>
      </div>

      <!-- 中间 Vue Flow 画布 -->
      <div class="canvas-wrapper" @drop="onDrop" @dragover.prevent>
        <VueFlow
          v-model:nodes="flowNodes"
          v-model:edges="flowEdges"
          :default-viewport="{ zoom: 0.9, x: 50, y: 50 }"
          fit-view-on-init
          @node-click="onNodeClick"
          @connect="onConnect"
        >
          <Background />
          <Controls />
          <MiniMap />

          <!-- 自定义节点渲染 -->
          <template #node-start="{ data }">
            <div class="custom-node node-start">
              <div class="node-icon">🚀</div>
              <div class="node-label">{{ data.label || 'Start' }}</div>
              <Handle type="source" :position="Position.Bottom" />
            </div>
          </template>

          <template #node-end="{ data }">
            <div class="custom-node node-end">
              <Handle type="target" :position="Position.Top" />
              <div class="node-icon">🏁</div>
              <div class="node-label">{{ data.label || 'End' }}</div>
            </div>
          </template>

          <template #node-llm="{ data }">
            <div class="custom-node node-llm" :class="{ 'node-running': data._status === 'running', 'node-done': data._status === 'done', 'node-error': data._status === 'error' }">
              <Handle type="target" :position="Position.Top" />
              <div class="node-icon">🧠</div>
              <div class="node-label">{{ data.label || 'LLM' }}</div>
              <div class="node-sub">{{ data.model || 'default' }}</div>
              <Handle type="source" :position="Position.Bottom" />
            </div>
          </template>

          <template #node-tool="{ data }">
            <div class="custom-node node-tool" :class="{ 'node-running': data._status === 'running', 'node-done': data._status === 'done', 'node-error': data._status === 'error' }">
              <Handle type="target" :position="Position.Top" />
              <div class="node-icon">🔧</div>
              <div class="node-label">{{ data.label || 'Tool' }}</div>
              <div class="node-sub">{{ data.toolName || '' }}</div>
              <Handle type="source" :position="Position.Bottom" />
            </div>
          </template>

          <template #node-condition="{ data }">
            <div class="custom-node node-condition" :class="{ 'node-running': data._status === 'running', 'node-done': data._status === 'done' }">
              <Handle type="target" :position="Position.Top" />
              <div class="node-icon">🔀</div>
              <div class="node-label">{{ data.label || 'Condition' }}</div>
              <Handle type="source" :position="Position.Bottom" />
            </div>
          </template>

          <template #node-loop="{ data }">
            <div class="custom-node node-loop" :class="{ 'node-running': data._status === 'running', 'node-done': data._status === 'done' }">
              <Handle type="target" :position="Position.Top" />
              <div class="node-icon">🔄</div>
              <div class="node-label">{{ data.label || 'Loop' }}</div>
              <Handle type="source" :position="Position.Bottom" />
            </div>
          </template>

          <template #node-variable="{ data }">
            <div class="custom-node node-variable" :class="{ 'node-done': data._status === 'done' }">
              <Handle type="target" :position="Position.Top" />
              <div class="node-icon">📦</div>
              <div class="node-label">{{ data.label || 'Variable' }}</div>
              <Handle type="source" :position="Position.Bottom" />
            </div>
          </template>

          <template #node-merge="{ data }">
            <div class="custom-node node-merge" :class="{ 'node-done': data._status === 'done' }">
              <Handle type="target" :position="Position.Top" />
              <div class="node-icon">🔗</div>
              <div class="node-label">{{ data.label || 'Merge' }}</div>
              <Handle type="source" :position="Position.Bottom" />
            </div>
          </template>
        </VueFlow>
      </div>

      <!-- 右侧属性面板 -->
      <div class="props-panel" v-if="selectedNode">
        <div class="panel-title">
          节点属性
          <el-button text type="danger" size="small" @click="deleteSelectedNode">删除节点</el-button>
        </div>

        <el-form label-position="top" size="small">
          <el-form-item label="ID">
            <el-input v-model="selectedNode.id" disabled />
          </el-form-item>
          <el-form-item label="类型">
            <el-tag>{{ selectedNode.type }}</el-tag>
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="selectedNode.data.label" @input="markDirty" />
          </el-form-item>

          <!-- LLM 节点配置 -->
          <template v-if="selectedNode.type === 'llm'">
            <el-form-item label="模型">
              <el-input v-model="selectedNode.data.model" placeholder="default" @input="markDirty" />
            </el-form-item>
            <el-form-item label="System Prompt">
              <el-input v-model="selectedNode.data.systemPrompt" type="textarea" :rows="3" @input="markDirty" />
            </el-form-item>
            <el-form-item label="User Prompt Template">
              <el-input v-model="selectedNode.data.userPromptTemplate" type="textarea" :rows="3" placeholder="{{variable}}" @input="markDirty" />
            </el-form-item>
            <el-form-item label="输出变量">
              <el-input v-model="selectedNode.data.outputVariable" @input="markDirty" />
            </el-form-item>
          </template>

          <!-- Tool 节点配置 -->
          <template v-if="selectedNode.type === 'tool'">
            <el-form-item label="工具名">
              <el-select v-model="selectedNode.data.toolName" filterable @change="markDirty">
                <el-option v-for="t in toolOptions" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
            <el-form-item label="参数映射 (JSON)">
              <el-input v-model="selectedNode.data._paramMappingStr" type="textarea" :rows="3" placeholder='{"prompt": "var_name"}' @input="markDirty" />
            </el-form-item>
            <el-form-item label="输出变量">
              <el-input v-model="selectedNode.data.outputVariable" @input="markDirty" />
            </el-form-item>
          </template>

          <!-- Condition 节点 -->
          <template v-if="selectedNode.type === 'condition'">
            <el-form-item label="分支条件 (JSON Array)">
              <el-input v-model="selectedNode.data._branchesStr" type="textarea" :rows="4" @input="markDirty" />
            </el-form-item>
            <el-form-item label="默认分支">
              <el-input v-model="selectedNode.data.defaultBranch" @input="markDirty" />
            </el-form-item>
          </template>

          <!-- Variable 节点 -->
          <template v-if="selectedNode.type === 'variable'">
            <el-form-item label="表达式">
              <el-input v-model="selectedNode.data.expression" @input="markDirty" />
            </el-form-item>
            <el-form-item label="输出变量">
              <el-input v-model="selectedNode.data.outputVariable" @input="markDirty" />
            </el-form-item>
          </template>

          <!-- Start 节点 -->
          <template v-if="selectedNode.type === 'start'">
            <el-form-item label="输出变量列表 (逗号分隔)">
              <el-input v-model="selectedNode.data._outputsStr" placeholder="description, style" @input="markDirty" />
            </el-form-item>
          </template>

          <!-- End 节点 -->
          <template v-if="selectedNode.type === 'end'">
            <el-form-item label="收集变量列表 (逗号分隔)">
              <el-input v-model="selectedNode.data._outputsStr" @input="markDirty" />
            </el-form-item>
          </template>
        </el-form>
      </div>

      <!-- 无选中时展示执行日志 -->
      <div class="props-panel" v-else-if="executionLog.length > 0">
        <div class="panel-title">执行日志</div>
        <div class="exec-log">
          <div v-for="(log, i) in executionLog" :key="i" class="log-item" :class="'log-' + log.type">
            <span class="log-time">{{ log.time }}</span>
            <span class="log-text">{{ log.text }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 新建工作流对话框 ── -->
    <el-dialog v-model="showCreateDialog" title="新建工作流" width="450px">
      <el-form label-position="top">
        <el-form-item label="名称">
          <el-input v-model="newWfName" placeholder="例: 仙侠4格漫剧" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newWfDesc" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- ── 执行对话框 ── -->
    <el-dialog v-model="showExecuteDialog" title="执行工作流" width="500px">
      <el-form label-position="top">
        <el-form-item label="输入变量 (JSON)">
          <el-input v-model="executeInputStr" type="textarea" :rows="5" placeholder='{"description": "...", "style": "xianxia"}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showExecuteDialog = false">取消</el-button>
        <el-button type="success" :loading="executing" @click="handleExecute">执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { VueFlow, Position, Handle } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { Plus, Delete, VideoPlay, Check } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listWorkflows, getWorkflow, createWorkflow, updateWorkflow, deleteWorkflow,
  connectWorkflowWS, type WorkflowDefinition, type WfEvent,
} from '@/api/workflow'

// ── 节点类型定义 ──
const nodeTypes = [
  { type: 'start', label: 'Start', icon: '🚀' },
  { type: 'llm', label: 'LLM', icon: '🧠' },
  { type: 'tool', label: 'Tool', icon: '🔧' },
  { type: 'condition', label: 'Condition', icon: '🔀' },
  { type: 'loop', label: 'Loop', icon: '🔄' },
  { type: 'variable', label: 'Variable', icon: '📦' },
  { type: 'merge', label: 'Merge', icon: '🔗' },
  { type: 'end', label: 'End', icon: '🏁' },
]

const toolOptions = [
  'generate_image', 'generate_video', 'generate_tts',
  'edit_image', 'describe_image', 'upscale_image',
]

// ── 状态 ──
const workflows = ref<WorkflowDefinition[]>([])
const selectedWorkflowId = ref('')
const currentWorkflow = ref<WorkflowDefinition | null>(null)
const dirty = ref(false)
const executing = ref(false)
const showCreateDialog = ref(false)
const showExecuteDialog = ref(false)
const newWfName = ref('')
const newWfDesc = ref('')
const executeInputStr = ref('{}')
const executionLog = ref<{ time: string; text: string; type: string }[]>([])

// Vue Flow
const flowNodes = ref<any[]>([])
const flowEdges = ref<any[]>([])
const selectedNode = ref<any>(null)

// ── 加载工作流列表 ──
async function fetchWorkflows() {
  try {
    workflows.value = await listWorkflows()
  } catch { /* handled by interceptor */ }
}

async function loadWorkflow(id?: string) {
  const wfId = id || selectedWorkflowId.value
  if (!wfId) return
  try {
    const wf = await getWorkflow(wfId)
    currentWorkflow.value = wf
    selectedWorkflowId.value = wf.id
    dirty.value = false
    selectedNode.value = null
    executionLog.value = []

    // 将 definition 转换为 Vue Flow 格式
    const def = wf.definition
    flowNodes.value = (def.nodes || []).map((n: any, i: number) => ({
      id: n.id,
      type: n.type,
      position: n.position || { x: 250, y: i * 120 },
      data: {
        label: n.data?.label || n.id,
        ...n.data,
        _outputsStr: (n.data?.outputs || []).join(', '),
        _paramMappingStr: n.data?.paramMapping ? JSON.stringify(n.data.paramMapping, null, 2) : '',
        _branchesStr: n.data?.branches ? JSON.stringify(n.data.branches, null, 2) : '',
      },
    }))
    flowEdges.value = (def.edges || []).map((e: any, i: number) => ({
      id: `e-${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      animated: true,
      style: { stroke: '#667eea' },
    }))
  } catch { /* handled by interceptor */ }
}

// ── 保存 ──
function buildDefinitionFromFlow() {
  const nodes = flowNodes.value.map((n: any) => {
    const data = { ...n.data }
    // 解析特殊字段
    if (data._outputsStr !== undefined) {
      data.outputs = data._outputsStr.split(',').map((s: string) => s.trim()).filter(Boolean)
      delete data._outputsStr
    }
    if (data._paramMappingStr !== undefined) {
      try { data.paramMapping = JSON.parse(data._paramMappingStr) } catch { /* keep old */ }
      delete data._paramMappingStr
    }
    if (data._branchesStr !== undefined) {
      try { data.branches = JSON.parse(data._branchesStr) } catch { /* keep old */ }
      delete data._branchesStr
    }
    // 清理运行时字段
    delete data._status
    delete data.label
    return {
      id: n.id,
      type: n.type,
      position: n.position,
      data: { label: n.data.label, ...data },
    }
  })
  const edges = flowEdges.value.map((e: any) => ({
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle || undefined,
  }))
  return { nodes, edges, variables: currentWorkflow.value?.definition?.variables || {} }
}

async function saveWorkflow() {
  if (!currentWorkflow.value) return
  try {
    const definition = buildDefinitionFromFlow()
    await updateWorkflow(currentWorkflow.value.id, { definition })
    dirty.value = false
    ElMessage.success('保存成功')
  } catch { /* handled */ }
}

// ── 新建 ──
async function handleCreate() {
  if (!newWfName.value.trim()) { ElMessage.warning('请输入名称'); return }
  try {
    const wf = await createWorkflow({
      name: newWfName.value.trim(),
      description: newWfDesc.value.trim(),
      definition: {
        nodes: [
          { id: 'start', type: 'start', data: { label: 'Start', outputs: [] }, position: { x: 250, y: 50 } },
          { id: 'end', type: 'end', data: { label: 'End', outputs: [] }, position: { x: 250, y: 300 } },
        ],
        edges: [{ source: 'start', target: 'end' }],
        variables: {},
      },
    })
    showCreateDialog.value = false
    newWfName.value = ''
    newWfDesc.value = ''
    await fetchWorkflows()
    selectedWorkflowId.value = wf.id
    await loadWorkflow(wf.id)
    ElMessage.success('创建成功')
  } catch { /* handled */ }
}

// ── 删除 ──
async function handleDelete() {
  if (!selectedWorkflowId.value) return
  try {
    await ElMessageBox.confirm('确定删除此工作流？', '确认', { type: 'warning' })
    await deleteWorkflow(selectedWorkflowId.value)
    selectedWorkflowId.value = ''
    currentWorkflow.value = null
    flowNodes.value = []
    flowEdges.value = []
    await fetchWorkflows()
    ElMessage.success('已删除')
  } catch { /* cancelled or error */ }
}

// ── 拖拽添加节点 ──
let dragType = ''
function onDragStart(event: DragEvent, type: string) {
  dragType = type
  event.dataTransfer!.effectAllowed = 'move'
}

function onDrop(event: DragEvent) {
  if (!dragType) return
  const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const position = { x: event.clientX - bounds.left - 75, y: event.clientY - bounds.top - 25 }
  const id = `${dragType}_${Date.now().toString(36)}`
  const nt = nodeTypes.find(n => n.type === dragType)

  flowNodes.value.push({
    id,
    type: dragType,
    position,
    data: {
      label: nt?.label || dragType,
      _outputsStr: '',
      _paramMappingStr: '',
      _branchesStr: '',
    },
  })
  dirty.value = true
  dragType = ''
}

// ── 节点点击 ──
function onNodeClick({ node }: any) {
  selectedNode.value = node
}

function deleteSelectedNode() {
  if (!selectedNode.value) return
  const id = selectedNode.value.id
  flowNodes.value = flowNodes.value.filter((n: any) => n.id !== id)
  flowEdges.value = flowEdges.value.filter((e: any) => e.source !== id && e.target !== id)
  selectedNode.value = null
  dirty.value = true
}

// ── 连线 ──
function onConnect(params: any) {
  flowEdges.value.push({
    id: `e-${params.source}-${params.target}-${Date.now()}`,
    source: params.source,
    target: params.target,
    animated: true,
    style: { stroke: '#667eea' },
  })
  dirty.value = true
}

function markDirty() { dirty.value = true }

// ── 执行 ──
async function handleExecute() {
  if (!selectedWorkflowId.value) return
  let inputs: Record<string, any> = {}
  try { inputs = JSON.parse(executeInputStr.value) } catch { ElMessage.error('JSON 格式错误'); return }

  executing.value = true
  showExecuteDialog.value = false
  executionLog.value = []
  selectedNode.value = null

  // 重置节点状态
  flowNodes.value.forEach((n: any) => { n.data._status = '' })

  const now = () => new Date().toLocaleTimeString()

  connectWorkflowWS(
    selectedWorkflowId.value,
    inputs,
    (event: WfEvent) => {
      if (event.type === 'node_status' && event.node_id) {
        const node = flowNodes.value.find((n: any) => n.id === event.node_id)
        if (node) node.data = { ...node.data, _status: event.status }
        executionLog.value.push({ time: now(), text: `[${event.node_id}] ${event.status}`, type: event.status || 'info' })
      } else if (event.type === 'llm_stream' && event.delta) {
        executionLog.value.push({ time: now(), text: `[${event.node_id}] ${event.delta}`, type: 'stream' })
      } else if (event.type === 'execution_started') {
        executionLog.value.push({ time: now(), text: `🚀 执行开始 (${event.total_nodes} 节点, ${event.total_batches} 层)`, type: 'info' })
      } else if (event.type === 'execution_finished') {
        executionLog.value.push({ time: now(), text: `${event.status === 'done' ? '✅' : '❌'} 执行完成: ${event.status}`, type: event.status || 'done' })
      } else if (event.type === 'execution_error' || event.type === 'error') {
        executionLog.value.push({ time: now(), text: `❌ ${event.error || event.content}`, type: 'error' })
      }
    },
    () => { executing.value = false },
  )
}

// ── 初始化 ──
onMounted(async () => {
  await fetchWorkflows()
  if (workflows.value.length > 0) {
    selectedWorkflowId.value = workflows.value[0].id
    await loadWorkflow()
  }
})
</script>

<style scoped lang="scss">
.workflow-page {
  height: calc(100vh - 112px);
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: white;
  border-bottom: 1px solid #e4e7ed;
  gap: 12px;

  &-left, &-right { display: flex; align-items: center; gap: 8px; }
}

.editor-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

// ── 左侧面板 ──
.node-palette {
  width: 140px;
  background: white;
  border-right: 1px solid #e4e7ed;
  padding: 12px 8px;
  overflow-y: auto;

  .palette-title {
    font-size: 12px;
    font-weight: 600;
    color: #909399;
    margin-bottom: 8px;
    padding: 0 4px;
  }

  .palette-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 8px;
    margin-bottom: 4px;
    border-radius: 6px;
    cursor: grab;
    font-size: 13px;
    transition: background 0.2s;

    &:hover { background: #f0f2f5; }
    .palette-icon { font-size: 16px; }
  }
}

// ── 中间画布 ──
.canvas-wrapper {
  flex: 1;
  position: relative;
}

// ── 右侧属性面板 ──
.props-panel {
  width: 280px;
  background: white;
  border-left: 1px solid #e4e7ed;
  padding: 16px;
  overflow-y: auto;

  .panel-title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

// ── 自定义节点样式 ──
.custom-node {
  background: white;
  border: 2px solid #e4e7ed;
  border-radius: 10px;
  padding: 10px 16px;
  min-width: 120px;
  text-align: center;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);

  .node-icon { font-size: 20px; margin-bottom: 2px; }
  .node-label { font-size: 13px; font-weight: 600; color: #303133; }
  .node-sub { font-size: 11px; color: #909399; margin-top: 2px; }

  &.node-running {
    border-color: #409eff;
    box-shadow: 0 0 12px rgba(64, 158, 255, 0.4);
    animation: pulse 1.5s infinite;
  }
  &.node-done { border-color: #67c23a; }
  &.node-error { border-color: #f56c6c; }
}

.node-start { border-color: #67c23a; background: #f0f9eb; }
.node-end { border-color: #909399; background: #f4f4f5; }
.node-llm { border-color: #667eea; }
.node-tool { border-color: #e6a23c; }
.node-condition { border-color: #409eff; }
.node-loop { border-color: #e6a23c; }

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 8px rgba(64, 158, 255, 0.3); }
  50% { box-shadow: 0 0 16px rgba(64, 158, 255, 0.6); }
}

// ── 执行日志 ──
.exec-log {
  font-size: 12px;
  max-height: 500px;
  overflow-y: auto;

  .log-item {
    padding: 4px 0;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    gap: 6px;

    .log-time { color: #c0c4cc; white-space: nowrap; }
    .log-text { word-break: break-all; }
  }
  .log-running .log-text { color: #409eff; }
  .log-done .log-text { color: #67c23a; }
  .log-error .log-text { color: #f56c6c; }
  .log-stream .log-text { color: #909399; }
}
</style>
