<template>
  <el-drawer v-model="visible" title="Agent 配置管理" size="520px" direction="rtl">
    <el-tabs v-model="activeTab" class="drawer-tabs">

      <!-- ─── Tab 1: 工具列表 ─── -->
      <el-tab-pane label="🔧 工具列表" name="tools">
        <div class="panel-desc">Agent 大脑可调用的 8 大工具能力，每个工具背后对应若干 ComfyUI 工作流（共 {{ workflowList.length }} 个）。</div>
        <el-table :data="toolList" stripe size="small" class="config-table">
          <el-table-column prop="display_name" label="工具" min-width="110" />
          <el-table-column prop="name" label="标识名" min-width="130">
            <template #default="{ row }">
              <code class="code-tag">{{ row.name }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="executor_type" label="执行器" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="executorTagType(row.executor_type)">{{ row.executor_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="60" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.is_enabled" size="small" @change="(val: boolean) => handleToolToggle(row.id, val)" />
            </template>
          </el-table-column>
        </el-table>
        <div class="panel-summary">
          共 {{ toolList.length }} 个 Agent 工具，已启用 {{ toolList.filter(t => t.is_enabled).length }} 个 · 底层 {{ workflowList.length }} 个 ComfyUI 工作流
        </div>
      </el-tab-pane>

      <!-- ─── Tab 2: 模型 / 服务 ─── -->
      <el-tab-pane label="🧠 服务配置" name="models">
        <div class="panel-desc">Agent 依赖的外部服务（LLM / ComfyUI GPU）。</div>
        <el-table :data="modelList" stripe size="small" class="config-table">
          <el-table-column prop="name" label="服务" min-width="160">
            <template #default="{ row }">
              <div>
                <strong>{{ row.name }}</strong>
                <el-tag v-if="row.is_default" size="small" type="success" style="margin-left:4px">默认</el-tag>
              </div>
              <div style="font-size:11px;color:#909399;margin-top:2px">{{ row.model_id }}</div>
              <div v-if="row.base_url" style="font-size:10px;color:#c0c4cc;margin-top:1px;word-break:break-all">{{ row.base_url }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="用途" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="categoryTagType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="参数" width="70" align="center">
            <template #default="{ row }">
              <el-popover v-if="['agent_brain', 'l1_llm'].includes(row.category)" trigger="click" width="340" placement="left">
                <template #reference>
                  <el-button size="small" link type="primary">编辑</el-button>
                </template>
                <div style="font-size:13px;margin-bottom:8px;font-weight:600">模型参数</div>
                <el-form size="small" label-width="120px" label-position="left">
                  <el-form-item label="max_tokens">
                    <el-input-number v-model="(row.model_params = row.model_params || {}).max_tokens"
                      :min="256" :max="200000" :step="512" size="small" style="width:100%" controls-position="right" />
                  </el-form-item>
                  <el-form-item label="temperature">
                    <el-slider v-model="(row.model_params = row.model_params || {}).temperature"
                      :min="0" :max="2" :step="0.1" show-input size="small" />
                  </el-form-item>
                  <el-form-item label="top_p">
                    <el-slider v-model="(row.model_params = row.model_params || {}).top_p"
                      :min="0" :max="1" :step="0.05" show-input size="small" />
                  </el-form-item>
                  <el-form-item label="freq_penalty">
                    <el-slider v-model="(row.model_params = row.model_params || {}).frequency_penalty"
                      :min="-2" :max="2" :step="0.1" show-input size="small" />
                  </el-form-item>
                  <el-form-item label="pres_penalty">
                    <el-slider v-model="(row.model_params = row.model_params || {}).presence_penalty"
                      :min="-2" :max="2" :step="0.1" show-input size="small" />
                  </el-form-item>
                </el-form>
                <el-button size="small" type="primary" style="width:100%" @click="handleSaveModelParams(row)">保存</el-button>
              </el-popover>
              <span v-else style="color:#c0c4cc">-</span>
            </template>
          </el-table-column>
          <el-table-column label="配置" width="70" align="center">
            <template #default="{ row }">
              <el-popover trigger="click" width="400" placement="left">
                <template #reference>
                  <el-button size="small" link type="warning">配置</el-button>
                </template>
                <div style="font-size:13px;margin-bottom:8px;font-weight:600">服务连接配置</div>
                <el-form size="small" label-width="80px" label-position="left">
                  <el-form-item label="Base URL">
                    <el-input v-model="row.base_url" placeholder="https://..." clearable />
                  </el-form-item>
                  <el-form-item label="API Key">
                    <el-input v-model="row.api_key" placeholder="sk-..." show-password clearable />
                  </el-form-item>
                  <el-form-item label="Model ID">
                    <el-input v-model="row.model_id" placeholder="模型标识符" clearable />
                  </el-form-item>
                </el-form>
                <el-button size="small" type="primary" style="width:100%" @click="handleSaveModelConnection(row)">保存</el-button>
              </el-popover>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="60" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.is_enabled" size="small" @change="(val: boolean) => handleModelToggle(row.id, val)" />
            </template>
          </el-table-column>
        </el-table>
        <div class="panel-summary">
          共 {{ modelList.length }} 个服务，已启用 {{ modelList.filter(m => m.is_enabled).length }} 个
        </div>
      </el-tab-pane>

      <!-- ─── Tab 3: 工作流模板 ─── -->
      <el-tab-pane label="📋 工作流模板" name="workflows">
        <div class="panel-desc">ComfyUI 工作流模板，Agent 的工具层根据参数自动匹配合适的工作流。</div>
        <el-table :data="workflowList" stripe size="small" class="config-table">
          <el-table-column prop="display_name" label="工作流" min-width="130">
            <template #default="{ row }">
              <div><strong>{{ row.display_name }}</strong></div>
              <div style="font-size:11px;color:#909399;margin-top:2px">
                <code class="code-tag">{{ row.name }}</code>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="类型" width="75">
            <template #default="{ row }">
              <el-tag size="small" :type="wfCategoryTagType(row.category)">{{ wfCategoryLabel(row.category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="style_tag" label="风格" width="70">
            <template #default="{ row }">
              <span v-if="row.style_tag">{{ row.style_tag }}</span>
              <span v-else style="color:#c0c4cc">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="test_time" label="测试耗时" width="80" align="right">
            <template #default="{ row }">
              <span style="font-family:monospace;font-size:12px">{{ row.test_time ? (row.test_time / 10).toFixed(1) : '—' }}s</span>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="60" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.is_enabled" size="small" @change="(val: boolean) => handleWorkflowToggle(row.id, val)" />
            </template>
          </el-table-column>
        </el-table>
        <div class="panel-summary">
          共 {{ workflowList.length }} 个工作流，已启用 {{ workflowList.filter(w => w.is_enabled).length }} 个
        </div>
      </el-tab-pane>

      <!-- ─── Tab 4: Prompt 管理 ─── -->
      <el-tab-pane label="📝 Prompt 管理" name="prompts">
        <div class="panel-desc">各节点的 System / User 模板 Prompt。点击内容区域可编辑。</div>
        <div v-for="p in promptList" :key="p.id" class="prompt-card">
          <div class="prompt-card-header">
            <div class="prompt-card-title">
              <strong>{{ p.display_name }}</strong>
              <el-tag size="small" :type="p.prompt_type === 'system' ? 'danger' : 'warning'" style="margin-left:6px">
                {{ p.prompt_type === 'system' ? 'System' : 'User 模板' }}
              </el-tag>
              <el-tag size="small" type="info" style="margin-left:4px">
                {{ p.node_name }}
              </el-tag>
            </div>
            <el-switch v-model="p.is_enabled" size="small" @change="(val: boolean) => handlePromptToggle(p.id, val)" />
          </div>
          <div v-if="p.description" class="prompt-card-desc">{{ p.description }}</div>
          <el-input
            v-model="p.content"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 15 }"
            class="prompt-textarea"
            @blur="handlePromptSave(p)"
          />
        </div>
        <div class="panel-summary">
          共 {{ promptList.length }} 个 Prompt，已启用 {{ promptList.filter(p => p.is_enabled).length }} 个
        </div>
      </el-tab-pane>

    </el-tabs>
  </el-drawer>
</template>

<script setup lang="ts">
import { useConfig } from '../composables'

const visible = defineModel<boolean>({ required: true })
const activeTab = defineModel<string>('tab', { default: 'tools' })

const {
  toolList, modelList, workflowList, promptList,
  handleToolToggle, handleModelToggle,
  handleSaveModelParams, handleSaveModelConnection,
  handleWorkflowToggle, handlePromptToggle, handlePromptSave,
  executorTagType, categoryTagType, categoryLabel,
  wfCategoryTagType, wfCategoryLabel,
} = useConfig()
</script>

<style lang="scss">
@import '../styles/drawer';
</style>
