<template>
  <div class="trace-timeline">
    <div class="trace-toolbar">
      <el-select v-model="filterType" size="small" clearable placeholder="筛选类型" style="width:140px">
        <el-option label="全部" value="" />
        <el-option label="🤖 LLM 调用" value="llm" />
        <el-option label="🔧 工具调用" value="tool" />
        <el-option label="📊 步骤更新" value="step" />
      </el-select>
      <el-input v-model="searchText" size="small" placeholder="搜索..." clearable style="width:180px" />
      <el-button size="small" :icon="Refresh" :loading="loading" @click="loadTrace">刷新</el-button>
    </div>

    <div v-if="loading" class="trace-loading">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <div v-else-if="!taskUid" class="trace-empty">暂无任务，发送消息后可查看 Trace</div>

    <div v-else-if="filteredItems.length === 0" class="trace-empty">无匹配记录</div>

    <div v-else class="trace-list">
      <div v-for="item in filteredItems" :key="item.id" class="trace-item" :class="`trace-item--${item.category}`">
        <div class="trace-item-time">{{ formatTraceTime(item.timestamp) }}</div>
        <div class="trace-item-dot" :class="`trace-dot--${item.category}`"></div>
        <div class="trace-item-body">
          <div class="trace-item-header">
            <span class="trace-item-icon">{{ item.icon }}</span>
            <span class="trace-item-title">{{ item.title }}</span>
            <el-tag v-if="item.status" :type="traceStatusType(item.status)" size="small" effect="plain">
              {{ item.status }}
            </el-tag>
            <span v-if="item.duration" class="trace-item-duration">{{ (item.duration / 1000).toFixed(1) }}s</span>
          </div>
          <div v-if="item.detail" class="trace-item-detail">{{ item.detail }}</div>
          <div v-if="item.tokens" class="trace-item-tokens">
            <span>输入: {{ item.tokens.input }}</span>
            <span>输出: {{ item.tokens.output }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Refresh, Loading } from '@element-plus/icons-vue'
import { fetchTaskTrace } from '@/api/comic-agent'
import type { TracePayload } from '@/api/comic-agent'

const props = defineProps<{ taskUid: string | null }>()

const loading = ref(false)
const filterType = ref('')
const searchText = ref('')
const traceData = ref<TracePayload | null>(null)

interface TraceItem {
  id: string
  category: 'tool' | 'llm' | 'step' | 'event'
  icon: string
  title: string
  detail?: string
  status?: string
  duration?: number
  timestamp: string
  tokens?: { input: number; output: number }
}

const allItems = computed<TraceItem[]>(() => {
  if (!traceData.value) return []
  const items: TraceItem[] = []

  for (const inv of traceData.value.tool_invocations) {
    items.push({
      id: `tool-${inv.invocation_uid}`,
      category: 'tool',
      icon: '🔧',
      title: inv.tool_name,
      detail: inv.inputs ? Object.entries(inv.inputs).map(([k, v]) => `${k}: ${typeof v === 'string' ? v.slice(0, 80) : JSON.stringify(v).slice(0, 80)}`).join(', ') : undefined,
      status: inv.status,
      duration: inv.duration_ms ?? undefined,
      timestamp: inv.started_at || inv.finished_at || '',
    })
  }

  for (const ev of traceData.value.events) {
    if (ev.event_type === 'step_update') {
      items.push({
        id: `ev-${ev.event_uid}`,
        category: 'step',
        icon: '📊',
        title: `步骤: ${ev.payload?.title || ev.payload?.step_uid || ''}`,
        detail: ev.payload?.description as string | undefined,
        status: ev.payload?.status as string | undefined,
        timestamp: ev.created_at,
      })
    } else if (['text', 'delta', 'thinking'].includes(ev.event_type)) {
      // LLM events
      items.push({
        id: `ev-${ev.event_uid}`,
        category: 'llm',
        icon: '🤖',
        title: `LLM ${ev.event_type}`,
        detail: (ev.payload?.content as string)?.slice(0, 100),
        timestamp: ev.created_at,
        tokens: ev.payload?.input_tokens ? { input: ev.payload.input_tokens as number, output: ev.payload.output_tokens as number || 0 } : undefined,
      })
    } else {
      items.push({
        id: `ev-${ev.event_uid}`,
        category: 'event',
        icon: '📌',
        title: ev.event_type,
        timestamp: ev.created_at,
      })
    }
  }

  items.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  return items
})

const filteredItems = computed(() => {
  let result = allItems.value
  if (filterType.value) {
    result = result.filter(i => i.category === filterType.value)
  }
  if (searchText.value) {
    const kw = searchText.value.toLowerCase()
    result = result.filter(i => i.title.toLowerCase().includes(kw) || i.detail?.toLowerCase().includes(kw))
  }
  return result
})

function traceStatusType(status: string) {
  if (['succeeded', 'completed'].includes(status)) return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed') return 'danger'
  return 'info'
}

function formatTraceTime(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

async function loadTrace() {
  if (!props.taskUid) return
  loading.value = true
  try {
    traceData.value = await fetchTaskTrace(props.taskUid)
  } finally {
    loading.value = false
  }
}

watch(() => props.taskUid, (uid) => {
  if (uid) loadTrace()
}, { immediate: true })
</script>

<style scoped lang="scss">
.trace-timeline {
  .trace-toolbar {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
    align-items: center;
  }

  .trace-loading, .trace-empty {
    text-align: center;
    color: #909399;
    padding: 24px 0;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
}

.trace-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.trace-item {
  display: grid;
  grid-template-columns: 70px 16px 1fr;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;

  &:last-child { border-bottom: none; }
}

.trace-item-time {
  font-size: 11px;
  color: #909399;
  font-family: 'SF Mono', Consolas, monospace;
  text-align: right;
  padding-top: 2px;
}

.trace-item-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 4px;
  justify-self: center;
  position: relative;

  &.trace-dot--tool { background: #409eff; }
  &.trace-dot--llm { background: #67c23a; }
  &.trace-dot--step { background: #e6a23c; }
  &.trace-dot--event { background: #909399; }
}

.trace-item-body {
  min-width: 0;
}

.trace-item-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.trace-item-icon { font-size: 14px; }
.trace-item-title { font-size: 13px; font-weight: 600; color: #303133; }
.trace-item-duration { font-size: 11px; color: #e6a23c; font-family: monospace; }

.trace-item-detail {
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-item-tokens {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
}
</style>
