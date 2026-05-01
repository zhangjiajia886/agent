<template>
  <div v-if="budget" class="budget-summary">
    <div class="budget-header">
      <span class="budget-icon">📊</span>
      <span class="budget-title">本次任务消耗</span>
    </div>

    <div class="budget-grid">
      <div class="budget-stat">
        <span class="budget-stat-value">{{ formatTokens(budget.input_tokens) }}</span>
        <span class="budget-stat-label">输入 Token</span>
      </div>
      <div class="budget-stat">
        <span class="budget-stat-value">{{ formatTokens(budget.output_tokens) }}</span>
        <span class="budget-stat-label">输出 Token</span>
      </div>
      <div class="budget-stat">
        <span class="budget-stat-value">{{ budget.tool_calls || 0 }}</span>
        <span class="budget-stat-label">工具调用</span>
      </div>
      <div class="budget-stat" v-if="budget.estimated_cost != null">
        <span class="budget-stat-value budget-stat-value--cost">¥{{ budget.estimated_cost.toFixed(3) }}</span>
        <span class="budget-stat-label">预估成本</span>
      </div>
    </div>

    <div v-if="toolEntries.length > 0" class="budget-tools">
      <div v-for="[name, count] in toolEntries" :key="name" class="budget-tool-row">
        <span class="budget-tool-name">{{ name }}</span>
        <span class="budget-tool-count">× {{ count }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface BudgetUsage {
  input_tokens?: number
  output_tokens?: number
  tool_calls?: number
  calls_per_tool?: Record<string, number>
  estimated_cost?: number
}

const props = defineProps<{ budget: BudgetUsage | null | undefined }>()

const toolEntries = computed(() => {
  if (!props.budget?.calls_per_tool) return []
  return Object.entries(props.budget.calls_per_tool).sort((a, b) => b[1] - a[1])
})

function formatTokens(n?: number): string {
  if (n == null) return '-'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}
</script>

<style scoped lang="scss">
.budget-summary {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #fafbff 0%, #f8fef9 100%);
}

.budget-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  .budget-icon { font-size: 16px; }
  .budget-title { font-size: 14px; font-weight: 600; color: #303133; }
}

.budget-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.budget-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px;
  border-radius: 10px;
  background: rgba(255,255,255,0.8);
  border: 1px solid #e5e7eb;
}

.budget-stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
  &.budget-stat-value--cost { color: #e6a23c; }
}

.budget-stat-label {
  font-size: 11px;
  color: #909399;
}

.budget-tools {
  border-top: 1px dashed #e2e8f0;
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.budget-tool-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 6px;
  &:hover { background: rgba(0,0,0,0.02); }
}

.budget-tool-name { color: #606266; }
.budget-tool-count { color: #909399; font-family: monospace; }
</style>
