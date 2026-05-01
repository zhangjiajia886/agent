<template>
  <div class="tool-health-panel">
    <div class="panel-desc">查看所有工具的运行状态和调用统计</div>

    <div class="health-actions">
      <el-button size="small" :icon="Refresh" :loading="loading" @click="refresh">刷新</el-button>
      <el-segmented v-model="viewMode" :options="['卡片', '表格']" size="small" />
    </div>

    <!-- 卡片视图 -->
    <div v-if="viewMode === '卡片'" class="health-cards">
      <div
        v-for="tool in mergedTools"
        :key="tool.name"
        class="health-card"
        :class="`health-card--${tool.health}`"
      >
        <div class="health-card-header">
          <span class="health-card-name">{{ tool.display_name || tool.name }}</span>
          <el-tag :type="healthTagType(tool.health)" size="small" effect="plain">
            {{ healthLabel(tool.health) }}
          </el-tag>
        </div>

        <div class="health-card-meta">
          <span>类型: {{ tool.executor_type }}</span>
          <span v-if="!tool.is_enabled" style="color:#f56c6c">已禁用</span>
        </div>

        <div v-if="tool.stats" class="health-card-stats">
          <div class="stat-item">
            <span class="stat-value">{{ tool.stats.total_calls }}</span>
            <span class="stat-label">总调用</span>
          </div>
          <div class="stat-item">
            <span class="stat-value" :style="{ color: tool.stats.success_rate >= 0.9 ? '#67c23a' : tool.stats.success_rate >= 0.7 ? '#e6a23c' : '#f56c6c' }">
              {{ (tool.stats.success_rate * 100).toFixed(0) }}%
            </span>
            <span class="stat-label">成功率</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ tool.stats.avg_duration_ms ? (tool.stats.avg_duration_ms / 1000).toFixed(1) + 's' : '-' }}</span>
            <span class="stat-label">平均耗时</span>
          </div>
          <div class="stat-item">
            <span class="stat-value" style="color:#f56c6c">{{ tool.stats.failed }}</span>
            <span class="stat-label">失败</span>
          </div>
        </div>

        <div v-else class="health-card-stats health-card-stats--empty">
          暂无调用记录
        </div>
      </div>
    </div>

    <!-- 表格视图 -->
    <el-table v-else :data="mergedTools" size="small" class="config-table" stripe>
      <el-table-column label="工具" min-width="140">
        <template #default="{ row }">
          <div>
            <strong>{{ row.display_name || row.name }}</strong>
            <div style="font-size:11px;color:#909399">{{ row.executor_type }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="healthTagType(row.health)" size="small">{{ healthLabel(row.health) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="总调用" width="70" align="center">
        <template #default="{ row }">{{ row.stats?.total_calls ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="成功率" width="80" align="center">
        <template #default="{ row }">
          <span v-if="row.stats" :style="{ color: row.stats.success_rate >= 0.9 ? '#67c23a' : row.stats.success_rate >= 0.7 ? '#e6a23c' : '#f56c6c' }">
            {{ (row.stats.success_rate * 100).toFixed(0) }}%
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="平均耗时" width="90" align="center">
        <template #default="{ row }">{{ row.stats?.avg_duration_ms ? (row.stats.avg_duration_ms / 1000).toFixed(1) + 's' : '-' }}</template>
      </el-table-column>
      <el-table-column label="失败" width="60" align="center">
        <template #default="{ row }">
          <span :style="{ color: (row.stats?.failed || 0) > 0 ? '#f56c6c' : '#909399' }">{{ row.stats?.failed ?? '-' }}</span>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="mergedTools.length === 0 && !loading" class="health-empty">
      暂无工具数据
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { fetchToolsHealth, fetchToolStats } from '@/api/comic-agent'
import type { ToolHealthItem, ToolStatsItem } from '@/api/comic-agent'

const loading = ref(false)
const viewMode = ref<'卡片' | '表格'>('卡片')
const healthList = ref<ToolHealthItem[]>([])
const statsList = ref<ToolStatsItem[]>([])

interface MergedTool extends ToolHealthItem {
  health: 'available' | 'degraded' | 'unavailable'
  stats: ToolStatsItem | null
}

const mergedTools = computed<MergedTool[]>(() => {
  const statsMap = new Map(statsList.value.map(s => [s.tool_name, s]))
  return healthList.value.map(h => ({
    ...h,
    health: h.status,
    stats: statsMap.get(h.name) || null,
  }))
})

function healthTagType(status: string) {
  if (status === 'available') return 'success'
  if (status === 'degraded') return 'warning'
  return 'danger'
}

function healthLabel(status: string) {
  if (status === 'available') return '正常'
  if (status === 'degraded') return '降级'
  return '不可用'
}

async function refresh() {
  loading.value = true
  try {
    const [h, s] = await Promise.all([fetchToolsHealth(), fetchToolStats()])
    healthList.value = h.tools
    statsList.value = s.stats
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<style scoped lang="scss">
.tool-health-panel {
  .health-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .health-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
  }

  .health-card {
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px;
    background: #f8fafc;
    transition: box-shadow 0.2s;
    &:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.06); }

    &.health-card--available { border-left: 3px solid #67c23a; }
    &.health-card--degraded { border-left: 3px solid #e6a23c; }
    &.health-card--unavailable { border-left: 3px solid #f56c6c; }
  }

  .health-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .health-card-name {
    font-weight: 600;
    font-size: 13px;
    color: #303133;
  }

  .health-card-meta {
    display: flex;
    gap: 8px;
    font-size: 11px;
    color: #909399;
    margin-bottom: 10px;
  }

  .health-card-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
    text-align: center;

    &.health-card-stats--empty {
      display: flex;
      justify-content: center;
      color: #c0c4cc;
      font-size: 12px;
      padding: 8px 0;
    }
  }

  .stat-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .stat-value {
    font-size: 16px;
    font-weight: 700;
    color: #303133;
  }

  .stat-label {
    font-size: 11px;
    color: #909399;
  }

  .health-empty {
    text-align: center;
    color: #c0c4cc;
    padding: 32px 0;
    font-size: 13px;
  }
}
</style>
