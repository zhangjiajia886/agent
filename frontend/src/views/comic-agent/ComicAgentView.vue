<template>
  <div class="agent-page">
    <!-- 顶部标题 -->
    <div class="agent-header">
      <div class="agent-header-left">
        <span class="agent-icon">🤖</span>
        <span class="agent-title">漫剧 Agent 对话创作</span>
        <el-tag size="small" :type="selectedModel ? 'success' : 'warning'" effect="plain">{{ selectedModel ? '专业执行模式' : '智能助手模式' }}</el-tag>
      </div>
      <div class="agent-header-right">
        <el-button text size="small" :icon="Setting" @click="drawerVisible = true">
          设置
        </el-button>
        <el-button text size="small" :icon="Delete" @click="clearChat" :disabled="messages.length === 0">
          清空对话
        </el-button>
      </div>
    </div>

    <!-- ══════════ 设置抽屉：工具 / 模型 / 工作流 ══════════ -->
    <el-drawer v-model="drawerVisible" title="Agent 配置管理" size="520px" direction="rtl">
      <el-tabs v-model="drawerTab" class="drawer-tabs">

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

    <!-- 消息区域 -->
    <div class="messages-area" ref="messagesRef">
      <!-- 空状态 -->
      <div v-if="messages.length === 0 && !activeTask" class="empty-state">
        <div class="empty-icon">🎨</div>
        <h3>漫剧 Agent 对话创作</h3>
        <p>描述你的创作目标后，我将完成需求解析、分镜规划与逐步生成。</p>
        <div class="quick-prompts">
          <div class="quick-prompt-title">试试这些：</div>
          <el-button
            v-for="q in quickPrompts"
            :key="q.label"
            size="default"
            round
            class="quick-btn"
            @click="sendQuickPrompt(q.text)"
          >
            {{ q.icon }} {{ q.label }}
          </el-button>
        </div>
      </div>

      <section v-if="activeTask" class="agent-workspace agent-workspace--narrative">
        <section class="narrative-block narrative-block--primary">
          <div class="block-marker">01</div>
          <div class="block-main">
            <div class="block-head">
              <div>
                <span class="section-kicker">Requirement Understanding</span>
                <h2>需求理解</h2>
              </div>
              <el-tag :type="taskStatusType(activeTask.status)" effect="dark">
                {{ taskStatusLabel(activeTask.status) }}
              </el-tag>
            </div>
            <div class="requirement-card">
              <div class="requirement-label">用户需求</div>
              <div class="requirement-text">{{ activeTask.userRequest }}</div>
            </div>
            <div class="understanding-grid">
              <div>
                <span>识别类型</span>
                <strong>{{ activeTask.intent }}</strong>
              </div>
              <div>
                <span>目标摘要</span>
                <strong>{{ activeTask.analysis }}</strong>
              </div>
              <div>
                <span>当前状态</span>
                <strong>{{ activeTask.currentStage }}</strong>
              </div>
            </div>
          </div>
        </section>

        <section v-if="showPlanBlock" class="narrative-block">
          <div class="block-marker">02</div>
          <div class="block-main">
            <div class="block-head">
              <div>
                <span class="section-kicker">Plan</span>
                <h2>执行规划</h2>
              </div>
              <span class="progress-text">{{ completedStepCount }}/{{ activeTask.steps.length }} 已完成</span>
            </div>
            <div class="plan-list">
              <div v-for="(step, index) in visiblePlanSteps" :key="step.id" :class="['plan-row', `plan-row--${step.status}`]">
                <span class="plan-index">{{ index + 1 }}</span>
                <div class="plan-copy">
                  <strong>{{ step.title }}</strong>
                  <p>{{ step.description }}</p>
                </div>
                <el-tag size="small" :type="stepStatusType(step.status)">{{ stepStatusLabel(step.status) }}</el-tag>
              </div>
            </div>
          </div>
        </section>

        <section v-if="showExecutionBlock" class="narrative-block">
          <div class="block-marker">03</div>
          <div class="block-main">
            <div class="block-head">
              <div>
                <span class="section-kicker">Execution</span>
                <h2>执行过程</h2>
              </div>
            </div>
            <div class="execution-flow">
              <article
                v-for="(step, index) in executableSteps"
                :key="step.id"
                :class="['execution-card', `execution-card--${step.status}`]"
              >
                <div class="execution-card-head">
                  <div>
                    <span>Step {{ index + 1 }}</span>
                    <h3>{{ step.title }}</h3>
                  </div>
                  <el-tag size="small" :type="stepStatusType(step.status)">{{ stepStatusLabel(step.status) }}</el-tag>
                </div>
                <p>{{ step.description }}</p>
                <div v-if="step.startedAt || step.finishedAt" class="step-meta">
                  <span v-if="step.startedAt">开始 {{ formatTime(step.startedAt) }}</span>
                  <span v-if="step.finishedAt">完成 {{ formatTime(step.finishedAt) }}</span>
                </div>
                <div v-if="step.status === 'awaiting_approval'" class="inline-approval">
                  <el-button type="primary" size="small" @click="approveTaskStep(step, 'approve')">确认执行</el-button>
                  <el-button type="danger" size="small" plain @click="approveTaskStep(step, 'reject')">取消操作</el-button>
                </div>
                <el-collapse v-if="stepLogs(step).length" class="compact-tool-collapse">
                  <el-collapse-item>
                    <template #title>
                      <span>工具调用明细已压缩 · {{ stepLogs(step).length }} 条</span>
                    </template>
                    <div class="compact-log-list">
                      <div v-for="log in stepLogs(step)" :key="log.id" class="compact-log-item">
                        <div class="compact-log-title">
                          <span>{{ log.title }}</span>
                          <em>{{ formatTime(log.timestamp) }}</em>
                        </div>
                        <pre>{{ compactLogContent(log.content) }}</pre>
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </article>
            </div>
          </div>
        </section>

        <section v-if="showResultBlock" class="narrative-block">
          <div class="block-marker">04</div>
          <div class="block-main">
            <div class="block-head">
              <div>
                <span class="section-kicker">Result Analysis</span>
                <h2>结果分析</h2>
              </div>
            </div>
            <div class="result-strip">
              <div v-for="item in activeTask.artifacts" :key="item.id" class="result-card">
                <el-image
                  v-if="item.type === 'image'"
                  :src="item.url"
                  fit="cover"
                  class="result-preview"
                  :preview-src-list="allImageUrls"
                  :initial-index="allImageUrls.indexOf(item.url)"
                />
                <video v-else-if="item.type === 'video'" :src="item.url" controls class="result-video"></video>
                <div v-else class="result-file">{{ item.type === 'audio' ? '音频产物' : '文件产物' }}</div>
                <div class="result-copy">
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.fromStep }}</span>
                </div>
              </div>
            </div>
            <div class="analysis-panel">
              {{ resultAnalysisText }}
            </div>
          </div>
        </section>

        <section v-if="showFinalBlock" class="narrative-block narrative-block--final">
          <div class="block-marker">05</div>
          <div class="block-main">
            <div class="block-head">
              <div>
                <span class="section-kicker">Final Report</span>
                <h2>总结报告</h2>
              </div>
            </div>
            <div class="final-report" v-html="renderMarkdown(finalReportText)"></div>
            <div v-if="visibleAssistantMessages.length" class="assistant-final-messages">
              <div v-for="msg in visibleAssistantMessages" :key="msg.id" class="summary-message">
                <div v-if="msg.content" v-html="renderMarkdown(msg.content || '')"></div>
              </div>
            </div>
          </div>
        </section>
      </section>

      <!-- 消息列表 -->
      <div
        v-for="msg in timelineMessages"
        :key="msg.id"
        class="message-row"
        :class="msg.type"
      >
        <!-- 用户消息 -->
        <template v-if="msg.type === 'user'">
          <div class="msg-bubble user-bubble">
            <div class="msg-content">{{ msg.content }}</div>
            <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
          </div>
          <div class="msg-avatar user-avatar">👤</div>
        </template>

        <!-- Agent 文字回复 + 内联图片/视频 -->
        <template v-else-if="msg.type === 'assistant'">
          <div class="msg-avatar bot-avatar">🤖</div>
          <div class="msg-bubble bot-bubble">
            <div v-if="msg.content" class="msg-content" v-html="renderMarkdown(msg.content || '')"></div>
            <!-- 内联图片网格 -->
            <div v-if="msg.images?.length" class="inline-images">
              <el-image
                v-for="(url, i) in msg.images"
                :key="i"
                :src="url"
                fit="cover"
                class="inline-img"
                :preview-src-list="allImageUrls"
                :initial-index="allImageUrls.indexOf(url)"
                lazy
              >
                <template #placeholder>
                  <div class="img-loading"><el-icon class="is-loading"><Loading /></el-icon></div>
                </template>
              </el-image>
            </div>
            <!-- 内联视频 -->
            <div v-if="msg.videos?.length" class="inline-videos">
              <video v-for="(url, i) in msg.videos" :key="i" :src="url" controls class="inline-video" />
            </div>
            <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
          </div>
        </template>

        <!-- 思考过程（始终可折叠显示） -->
        <template v-else-if="msg.type === 'thinking'">
          <div class="msg-avatar bot-avatar" style="opacity:0.5">🤔</div>
          <div :class="['thinking-bubble', { 'thinking-done': msg.isFinished }]">
            <!-- 可折叠头部 -->
            <div class="thinking-collapse-header" @click="msg.expanded = !msg.expanded">
              <template v-if="!msg.isFinished">
                <span class="thinking-dot"></span>
                <span class="thinking-dot"></span>
                <span class="thinking-dot"></span>
                <span style="margin-left:6px;font-size:11px;color:#909399">思考中...</span>
              </template>
              <template v-else>
                <span style="color:#67C23A;font-size:12px">已完成分析</span>
                <span style="margin-left:6px;font-size:11px;color:#909399">共 {{ (msg.content||'').split('\n').length }} 行</span>
              </template>
              <span style="margin-left:auto;font-size:11px;color:#c0c4cc">{{ msg.expanded ? '▲ 收起详情' : '▼ 查看详情' }}</span>
            </div>
            <div v-show="msg.expanded" class="thinking-content">{{ msg.content }}</div>
          </div>
        </template>

        <!-- 工具开始执行 -->
        <template v-else-if="msg.type === 'tool_start'">
          <div class="msg-avatar bot-avatar">🤖</div>
          <div class="tool-card tool-card--running">
            <div class="tool-card-header">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span class="tool-name">{{ toolDisplayName(msg.tool) }}</span>
              <el-tag size="small" type="warning">处理中</el-tag>
              <span class="tool-elapsed">{{ toolElapsed(msg.timestamp) }}</span>
            </div>
            <div class="tool-action-desc" v-if="msg.description">{{ msg.description }}</div>
            <div class="tool-hint" v-if="!msg.description && toolHint(msg.tool)">{{ toolHint(msg.tool) }}</div>
            <div class="tool-params" v-if="msg.toolInput">
              <div v-for="(val, key) in compactParams(msg.toolInput)" :key="key" class="tool-param-row">
                <span class="tool-param-key">{{ key }}:</span>
                <span class="tool-param-val">{{ val }}</span>
              </div>
            </div>
          </div>
        </template>

        <!-- 工具确认请求 -->
        <template v-else-if="msg.type === 'tool_confirm'">
          <div class="msg-avatar bot-avatar">🤖</div>
          <div class="tool-card tool-card--confirm">
            <div class="tool-card-header">
              <el-icon color="#E6A23C"><Warning /></el-icon>
              <span class="tool-name">{{ toolDisplayName(msg.tool) }}</span>
              <el-tag size="small" type="warning">待你确认</el-tag>
            </div>
            <div class="tool-action-desc" v-if="msg.description">{{ msg.description }}</div>
            <div class="tool-params" v-if="msg.toolInput">
              <div v-for="(val, key) in compactParams(msg.toolInput)" :key="key" class="tool-param-row">
                <span class="tool-param-key">{{ key }}:</span>
                <span class="tool-param-val">{{ val }}</span>
              </div>
            </div>
            <div class="tool-confirm-actions" v-if="!msg.confirmed">
              <el-button type="primary" size="small" @click="handleToolApproval(msg, 'approve')">
                确认执行
              </el-button>
              <el-button type="danger" size="small" plain @click="handleToolApproval(msg, 'reject')">
                取消本次操作
              </el-button>
            </div>
            <div v-else class="tool-confirm-result">
              <el-tag :type="msg.confirmed === 'approve' ? 'success' : 'danger'" size="small">
                {{ msg.confirmed === 'approve' ? '已确认执行' : '已取消' }}
              </el-tag>
            </div>
          </div>
        </template>

        <!-- 工具执行完成 -->
        <template v-else-if="msg.type === 'tool_done'">
          <div class="msg-avatar bot-avatar">🤖</div>
          <div class="tool-card tool-card--done">
            <div class="tool-card-header">
              <el-icon color="#67C23A"><CircleCheck /></el-icon>
              <span class="tool-name">{{ toolDisplayName(msg.tool) }}</span>
              <el-tag size="small" type="success">已完成</el-tag>
              <span v-if="msg.duration" class="tool-duration">{{ msg.duration.toFixed(1) }}s</span>
            </div>
            <!-- 图片预览 -->
            <div v-if="msg.imageUrl" class="tool-image-wrap">
              <el-image
                :src="msg.imageUrl"
                fit="cover"
                class="tool-image"
                :preview-src-list="allImageUrls"
                :initial-index="allImageUrls.indexOf(msg.imageUrl)"
                lazy
              >
                <template #placeholder>
                  <div class="img-loading"><el-icon class="is-loading"><Loading /></el-icon></div>
                </template>
              </el-image>
            </div>
            <!-- 视频预览 -->
            <div v-if="msg.videoUrl" class="tool-video-wrap">
              <video :src="msg.videoUrl" controls class="tool-video"></video>
            </div>
            <!-- 文字结果 -->
            <div v-if="msg.toolResult && !msg.imageUrl && !msg.videoUrl" class="tool-result-text">
              {{ msg.toolResult }}
            </div>
          </div>
        </template>

        <!-- 错误 -->
        <template v-else-if="msg.type === 'error'">
          <div class="msg-avatar bot-avatar">🤖</div>
          <el-alert :title="msg.content || '未知错误'" type="error" show-icon :closable="false" class="error-alert" />
        </template>
      </div>

      <!-- 流式打字中 -->
      <div v-if="streamingText" class="message-row assistant">
        <div class="msg-avatar bot-avatar">🤖</div>
        <div class="msg-bubble bot-bubble">
          <div class="msg-content" v-html="renderMarkdown(streamingText)"></div>
          <span class="cursor-blink">▋</span>
        </div>
      </div>
    </div>

    <!-- 生成的图片汇总（底部浮动条） -->
    <div v-if="allImageUrls.length > 0" class="gallery-bar">
      <div class="gallery-bar-inner">
        <span class="gallery-label">🖼️ 已生成 {{ allImageUrls.length }} 张</span>
        <div class="gallery-thumbs">
          <el-image
            v-for="(url, i) in allImageUrls"
            :key="i"
            :src="url"
            fit="cover"
            class="gallery-thumb"
            :preview-src-list="allImageUrls"
            :initial-index="i"
          />
        </div>
        <el-button size="small" type="primary" :icon="Download" @click="downloadAllImages">
          下载全部结果
        </el-button>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <div class="input-toolbar">
        <el-select v-model="selectedModel" size="small" placeholder="执行模型" style="width:170px">
          <el-option
            v-for="m in enabledAgentModels"
            :key="m.model_id"
            :label="m.name"
            :value="m.model_id"
          >
            <span>{{ m.name }}</span>
            <el-tag v-if="m.is_default" size="small" type="success" style="margin-left:4px;transform:scale(0.85)">默认</el-tag>
          </el-option>
        </el-select>
        <el-select v-model="selectedStyle" size="small" placeholder="创作风格" style="width:100px">
          <el-option label="自动识别" value="auto" />
          <el-option label="⚔️ 仙侠" value="xianxia" />
          <el-option label="🖌️ 水墨" value="ink" />
          <el-option label="🎁 盲盒" value="blindbox" />
          <el-option label="🌸 动漫" value="anime" />
          <el-option label="📷 写实" value="realistic" />
        </el-select>
        <el-select v-model="selectedFrames" size="small" placeholder="分镜数" style="width:90px">
          <el-option :label="'2 格'" :value="2" />
          <el-option :label="'4 格'" :value="4" />
          <el-option :label="'6 格'" :value="6" />
        </el-select>
        <div class="toolbar-divider"></div>
        <el-tooltip content="开启后 Agent 回复将自动语音播报">
          <div class="toolbar-switch">
            <el-switch v-model="ttsEnabled" size="small" />
            <span class="toolbar-switch-label">🔊 语音播报</span>
          </div>
        </el-tooltip>
        <el-tooltip content="开启后每格图片自动生成动态视频">
          <div class="toolbar-switch">
            <el-switch v-model="autoVideo" size="small" />
            <span class="toolbar-switch-label">🎬 动态化</span>
          </div>
        </el-tooltip>
        <el-tooltip content="新消息的思考过程自动展开">
          <div class="toolbar-switch">
            <el-switch v-model="showThinking" size="small" />
            <span class="toolbar-switch-label">🤔 展开分析</span>
          </div>
        </el-tooltip>
        <el-tooltip content="开启后创作类工具（生图/视频/TTS）无需逐个审批">
          <div class="toolbar-switch">
            <el-switch v-model="autoExec" size="small" active-color="#67C23A" />
            <span class="toolbar-switch-label">⚡ 自动审批</span>
          </div>
        </el-tooltip>
      </div>
      <!-- 图片附件预览 -->
      <div v-if="attachedImages.length" class="attached-images">
        <div v-for="(img, idx) in attachedImages" :key="idx" class="attached-image-item">
          <img :src="img.previewUrl" class="attached-thumb" />
          <div v-if="img.uploading" class="attached-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
          </div>
          <button class="attached-remove" @click="removeAttachedImage(idx)">×</button>
        </div>
      </div>
      <div class="input-row">
        <input
          ref="fileInputRef"
          type="file"
          accept="image/*"
          multiple
          style="display: none"
          @change="handleImageSelect"
        />
        <el-tooltip content="上传参考图片（最多4张）">
          <el-button
            :icon="PictureFilled"
            circle
            size="small"
            @click="triggerImageUpload"
            :disabled="sending || attachedImages.length >= MAX_IMAGES"
            class="upload-btn"
          />
        </el-tooltip>
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          :placeholder="sending ? '系统正在处理中...' : '请输入你的创作需求，按 Enter 发送...'"
          resize="none"
          @keydown.enter.exact.prevent="handleSend"
          :disabled="sending"
          class="input-textarea"
        />
        <div class="input-actions">
          <el-button
            type="primary"
            :icon="sending ? Loading : Promotion"
            :loading="sending"
            :disabled="!inputText.trim() || sending"
            circle
            size="large"
            @click="handleSend"
          />
        </div>
      </div>
      <div class="input-hint">
        Enter 发送 · Shift+Enter 换行 · 模型：{{ selectedModel }} · 风格：{{ selectedStyle === 'auto' ? '自动识别' : selectedStyle }} · 分镜：{{ selectedFrames }} 格
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Loading, Promotion, CircleCheck, Download, Setting, Warning, PictureFilled } from '@element-plus/icons-vue'
import {
  ComicAgentWS,
  fetchModels, updateModel,
  fetchTools, updateTool,
  fetchWorkflows, updateWorkflow,
  fetchPrompts, updatePrompt,
  uploadAgentImage,
  type AgentMessage, type AgentEvent,
  type ModelConfigItem, type ToolRegistryItem, type WorkflowTemplateItem,
  type AgentPromptItem,
} from '@/api/comic-agent'
import type { TaskStep, AttachedImage } from './types'
import {
  useTask,
  toolDisplayName, toolHint,
  taskStatusLabel, taskStatusType,
  stepStatusLabel, stepStatusType,
  mapServerTaskStatus,
} from './composables'

// ──────────── 状态 ────────────
const messages = ref<AgentMessage[]>([])
const inputText = ref('')
const sending = ref(false)
const streamingText = ref('')
const messagesRef = ref<HTMLElement>()
let msgIdCounter = 0

// ──────────── 任务管理 (composable) ────────────
const {
  activeTask,
  createTask,
  addTaskLog,
  stepLogs,
  compactLogContent,
  findTaskStepByTool,
  ensureToolStep,
  addArtifact,
  upsertServerStep,
  upsertServerArtifact,
} = useTask()

// ──────────── 抽屉状态 ────────────
const drawerVisible = ref(false)
const drawerTab = ref('tools')

// ──────────── 输入工具栏状态 ────────────
const selectedModel = ref('claude-sonnet-4-6')
const selectedStyle = ref('auto')
const selectedFrames = ref(4)
const ttsEnabled = ref(false)
const autoVideo = ref(false)
const showThinking = ref(false)
const autoExec = ref(false)  // 自动执行模式（创作类工具无需审批）

// ──────────── 图片附件状态 ────────────
const attachedImages = ref<AttachedImage[]>([])
const fileInputRef = ref<HTMLInputElement>()
const MAX_IMAGES = 4

// ──────────── 工具列表（从后端加载） ────────────
const toolList = ref<ToolRegistryItem[]>([])

// ──────────── 模型列表（从后端加载） ────────────
const modelList = ref<ModelConfigItem[]>([])

// ──────────── 工作流列表（从后端加载） ────────────
const workflowList = ref<WorkflowTemplateItem[]>([])

// ──────────── Prompt 列表（从后端加载） ────────────
const promptList = ref<AgentPromptItem[]>([])

// ──────────── WebSocket 实例 ────────────
const agentWS = new ComicAgentWS()

// ──────────── 可用 Agent 模型（从模型列表中筛选） ────────────
const enabledAgentModels = computed(() =>
  modelList.value.filter(m => m.is_enabled && (m.category === 'agent_brain' || m.category === 'l1_llm'))
)

function executorTagType(type: string): string {
  return { comfyui: 'primary', tts: 'success', local: 'info', http: 'warning' }[type] || 'info'
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

// ──────────── 快捷提示 ────────────
const quickPrompts = [
  { icon: '⚔️', label: '仙侠 4 格漫剧', text: '仙侠风格4格漫剧，一位白衣女侠初次踏入云雾缭绕的神秘仙山，满怀期待与好奇' },
  { icon: '🖌️', label: '水墨 4 格漫剧', text: '水墨国画风格4格漫剧，一位书生在溪边垂钓，忽遇神秘少女翩然而至' },
  { icon: '🎁', label: '盲盒 Q 版漫剧', text: '盲盒Q版风格4格漫剧，超可爱小女生第一次打开神秘礼盒，惊喜连连' },
  { icon: '🌸', label: '动漫风格漫剧', text: '动漫风格4格漫剧，樱花树下的浪漫邂逅，阳光少女与文静男生的初遇' },
]

// ──────────── 计算属性 ────────────
const allImageUrls = computed(() => {
  const urls: string[] = []
  for (const m of messages.value) {
    if (m.type === 'assistant' && m.images?.length) urls.push(...m.images)
    if (m.type === 'tool_done' && m.imageUrl) urls.push(m.imageUrl)
  }
  activeTask.value?.artifacts
    .filter(item => item.type === 'image')
    .forEach(item => {
      if (!urls.includes(item.url)) urls.push(item.url)
    })
  return urls
})

const timelineMessages = computed(() => {
  if (!activeTask.value) return messages.value
  return messages.value.filter(m => m.type === 'error')
})

const visibleAssistantMessages = computed(() =>
  messages.value.filter(m => m.type === 'assistant' && ((m.content || '').trim() || m.images?.length || m.videos?.length))
)

const completedStepCount = computed(() =>
  activeTask.value?.steps.filter(s => s.status === 'completed').length || 0
)

const hasAgentProgress = computed(() =>
  !!activeTask.value && (
    activeTask.value.logs.length > 0 ||
    activeTask.value.artifacts.length > 0 ||
    activeTask.value.steps.some(step => !step.id.startsWith('analysis-') && step.status !== 'pending')
  )
)

const visiblePlanSteps = computed(() =>
  hasAgentProgress.value ? activeTask.value?.steps.filter(step => !step.id.startsWith('analysis-')) || [] : []
)

const executableSteps = computed(() =>
  activeTask.value?.steps.filter(s =>
    !s.id.startsWith('analysis-') && (s.status !== 'pending' || !!s.startedAt || !!s.finishedAt || !!stepLogs(s).length)
  ) || []
)

const showPlanBlock = computed(() =>
  visiblePlanSteps.value.length > 0
)

const showExecutionBlock = computed(() =>
  executableSteps.value.length > 0
)

const showResultBlock = computed(() =>
  !!activeTask.value?.artifacts.length
)

const showFinalBlock = computed(() =>
  !!activeTask.value && ['completed', 'failed', 'canceled'].includes(activeTask.value.status)
)

const resultAnalysisText = computed(() => {
  if (!activeTask.value) return ''
  if (!activeTask.value.artifacts.length) return '当前还没有可分析的产物。结果生成后，将在这里对产物类型、来源步骤和后续可执行动作进行汇总分析。'
  const imageCount = activeTask.value.artifacts.filter(a => a.type === 'image').length
  const videoCount = activeTask.value.artifacts.filter(a => a.type === 'video').length
  const audioCount = activeTask.value.artifacts.filter(a => a.type === 'audio').length
  const parts = [
    imageCount ? `图像产物 ${imageCount} 项` : '',
    videoCount ? `视频产物 ${videoCount} 项` : '',
    audioCount ? `音频产物 ${audioCount} 项` : '',
  ].filter(Boolean).join('、')
  return `已完成产物汇总：${parts || '暂无媒体产物'}。系统将基于当前结果继续判断是否需要下一轮规划、编辑、动态化或最终收尾。`
})

const finalReportText = computed(() => {
  if (!activeTask.value) return ''
  const status = taskStatusLabel(activeTask.value.status)
  const completed = completedStepCount.value
  const total = activeTask.value.steps.length
  if (activeTask.value.status !== 'completed' && activeTask.value.status !== 'failed' && activeTask.value.status !== 'canceled') {
    return `**任务状态**：${status}\n\n**当前进度**：${completed}/${total} 个规划节点已完成。\n\n最终总结会在没有新的工具调用后生成，并固定停留在页面最下方。`
  }
  return `**任务状态**：${status}\n\n**需求理解**：${activeTask.value.analysis}\n\n**执行结果**：完成 ${completed}/${total} 个规划节点，产出 ${activeTask.value.artifacts.length} 项结果。\n\n**总结**：本轮任务已经结束，工具调用已停止，结果与执行记录已归档在上方对应模块。`
})

function approveTaskStep(step: TaskStep, action: 'approve' | 'reject') {
  step.status = action === 'approve' ? 'running' : 'canceled'
  if (action === 'reject' && activeTask.value) activeTask.value.status = 'canceled'
  agentWS.sendRaw({ action, tool_call_id: step.toolCallId })
}

// 工具执行耗时计时器
const elapsedTick = ref(0)
let elapsedTimer: ReturnType<typeof setInterval> | null = null

function startElapsedTimer() {
  if (elapsedTimer) return
  elapsedTimer = setInterval(() => { elapsedTick.value++ }, 1000)
}
function stopElapsedTimer() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

function toolElapsed(timestamp?: string): string {
  if (!timestamp) return ''
  // 触发响应式更新
  void elapsedTick.value
  const sec = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
  if (sec < 1) return ''
  return sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}m${sec % 60}s`
}

// ──────────── 参数精简展示 ────────────
function compactParams(input: Record<string, any>): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [k, v] of Object.entries(input)) {
    if (v === undefined || v === null || v === '') continue
    const str = typeof v === 'string' ? v : JSON.stringify(v)
    result[k] = str.length > 80 ? str.slice(0, 77) + '...' : str
  }
  return result
}

// ──────────── 渲染 ────────────
function renderMarkdown(raw: string): string {
  // 1. HTML 沙箱：```html ... ``` 渲染为 iframe srcdoc
  const blocks: string[] = []
  let text = raw.replace(/```(?:html|HTML)\n([\s\S]*?)\n```/g, (_, html) => {
    const srcdoc = html.trim()
      .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    const idx = blocks.length
    blocks.push(`<div class="html-sandbox-wrap"><iframe class="html-sandbox" srcdoc="${srcdoc}" sandbox="allow-scripts allow-same-origin" frameborder="0"></iframe></div>`)
    return `\x00BLOCK${idx}\x00`
  })

  // 2. 转义普通 HTML 字符
  text = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // 3. 表格  | col | col |
  text = text.replace(/((?:\|[^\n]+\|\n?)+)/g, (table) => {
    const rows = table.trim().split('\n').filter(r => !r.match(/^\|[-:\s|]+\|$/))
    const html = rows.map((r, i) => {
      const cells = r.split('|').slice(1, -1).map(c => c.trim())
      const tag = i === 0 ? 'th' : 'td'
      return '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>'
    }).join('')
    return `<table class="md-table"><tbody>${html}</tbody></table>`
  })

  // 4. 内联样式
  text = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^#{3}\s+(.+)$/gm, '<h3>$1</h3>')
    .replace(/^#{2}\s+(.+)$/gm, '<h2>$1</h2>')
    .replace(/^#\s+(.+)$/gm, '<h1>$1</h1>')
    .replace(/^-\s+(.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br/>')

  // 5. 还原 HTML 沙箱占位符
  text = text.replace(/\x00BLOCK(\d+)\x00/g, (_, i) => blocks[Number(i)])
  return text
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// ──────────── 工具审批 ────────────
function handleToolApproval(msg: AgentMessage, action: 'approve' | 'reject') {
  msg.confirmed = action
  const step = findTaskStepByTool(msg.tool, msg.toolCallId)
  if (step) {
    step.status = action === 'approve' ? 'running' : 'canceled'
    if (action === 'reject' && activeTask.value) activeTask.value.status = 'canceled'
  }
  agentWS.sendRaw({ action, tool_call_id: msg.toolCallId })
}

// ──────────── 图片附件操作 ────────────
function triggerImageUpload() {
  fileInputRef.value?.click()
}

async function handleImageSelect(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files) return
  for (const file of Array.from(files)) {
    if (attachedImages.value.length >= MAX_IMAGES) {
      ElMessage.warning(`最多上传 ${MAX_IMAGES} 张图片`)
      break
    }
    if (!file.type.startsWith('image/')) {
      ElMessage.warning(`${file.name} 不是图片文件`)
      continue
    }
    if (file.size > 20 * 1024 * 1024) {
      ElMessage.warning(`${file.name} 超过 20MB`)
      continue
    }
    const item: AttachedImage = {
      file,
      previewUrl: URL.createObjectURL(file),
      uploading: true,
    }
    attachedImages.value.push(item)
    try {
      item.uploaded = await uploadAgentImage(file)
      item.uploading = false
    } catch (err) {
      ElMessage.error(`上传失败: ${file.name}`)
      attachedImages.value = attachedImages.value.filter(i => i !== item)
      URL.revokeObjectURL(item.previewUrl)
    }
  }
  input.value = ''
}

function removeAttachedImage(index: number) {
  const item = attachedImages.value[index]
  URL.revokeObjectURL(item.previewUrl)
  attachedImages.value.splice(index, 1)
}

// ──────────── 发送消息 ────────────
function handleSend() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  inputText.value = ''
  sendToAgent(text)
}

function sendQuickPrompt(text: string) {
  if (sending.value) return
  sendToAgent(text)
}

async function sendToAgent(text: string) {
  createTask(text)
  // 添加用户消息
  messages.value.push({
    id: ++msgIdCounter,
    type: 'user',
    content: text,
    timestamp: new Date().toISOString(),
  })
  scrollToBottom()

  sending.value = true

  try {
    // 确保 WebSocket 已连接
    if (!agentWS.connected) {
      await agentWS.connect(
        (event: AgentEvent) => handleAgentEvent(event),
        () => {
          sending.value = false
          messages.value.forEach(m => {
            if (m.type === 'thinking' || m.type === 'assistant') m.isFinished = true
          })
          scrollToBottom()
        },
      )
    }

    // 收集已上传图片的服务端路径
    const imagePaths = attachedImages.value
      .filter(img => img.uploaded)
      .map(img => img.uploaded!.file_path)

    // 发送消息（带参数）
    agentWS.send(text, {
      style: selectedStyle.value,
      frames: selectedFrames.value,
      model: selectedModel.value,
      tts: ttsEnabled.value,
      autoVideo: autoVideo.value,
      auto_mode: autoExec.value,
      image_paths: imagePaths.length > 0 ? imagePaths : undefined,
    })

    // 发送后清空图片附件
    attachedImages.value.forEach(img => URL.revokeObjectURL(img.previewUrl))
    attachedImages.value = []
  } catch (e) {
    messages.value.push({
      id: ++msgIdCounter,
      type: 'error',
      content: '连接失败: ' + (e instanceof Error ? e.message : '未知错误'),
      timestamp: new Date().toISOString(),
    })
    sending.value = false
    scrollToBottom()
  }
}

function _lastAssistantMsg() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].type === 'assistant') return messages.value[i]
    if (messages.value[i].type === 'user') return null
  }
  return null
}

function _lastThinkingMsg() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].type === 'thinking') return messages.value[i]
    if (messages.value[i].type === 'assistant') return null
  }
  return null
}

function handleAgentEvent(event: AgentEvent) {
  const now = new Date().toISOString()

  switch (event.type) {
    case 'task_created':
      if (activeTask.value) {
        activeTask.value.taskUid = event.task_uid
        activeTask.value.status = mapServerTaskStatus(event.task?.status as string | undefined)
        activeTask.value.currentStage = '后端任务图已创建。'
        activeTask.value.steps = []
        ;(event.steps || []).forEach(step => upsertServerStep(step))
        addTaskLog('任务图创建', `后端已创建 ${event.steps?.length || 0} 个步骤。`)
      }
      break

    case 'task_update':
      if (activeTask.value) {
        activeTask.value.status = mapServerTaskStatus(event.status)
        activeTask.value.currentStage = event.content || (event as any).message || event.status || '任务状态已更新。'
        addTaskLog('任务状态更新', activeTask.value.currentStage)
      }
      break

    case 'step_update':
      if (event.step) {
        upsertServerStep(event.step)
        addTaskLog('步骤状态更新', `${event.step.title || event.step_uid}: ${event.step.status || ''}`, event.step_uid)
      }
      break

    case 'artifact_created':
      if (event.artifact) {
        upsertServerArtifact(event.artifact, event.step_uid)
        addTaskLog('产物已登记', event.artifact.url || event.artifact.title || '后端已登记产物。', event.step_uid)
      }
      break

    case 'thinking': {
      addTaskLog('Agent 分析', event.content)
      if (activeTask.value && event.content) {
        activeTask.value.currentStage = event.content.length > 80 ? `${event.content.slice(0, 80)}...` : event.content
      }
      const last = _lastThinkingMsg()
      if (!activeTask.value && last && !last.isFinished) {
        // 流式追加：不加多余换行
        last.content = (last.content || '') + (event.content || '')
      } else if (!activeTask.value) {
        messages.value.push({
          id: ++msgIdCounter, type: 'thinking',
          content: event.content, timestamp: now,
          expanded: showThinking.value,
        })
      }
      break
    }

    case 'delta': {
      const last = _lastAssistantMsg()
      if (last && !last.isFinished) {
        last.content = (last.content || '') + (event.content || '')
      } else {
        messages.value.push({
          id: ++msgIdCounter, type: 'assistant',
          content: event.content || '', images: [], videos: [], timestamp: now,
        })
      }
      break
    }

    case 'text':
      messages.value.push({
        id: ++msgIdCounter, type: 'assistant',
        content: event.content, images: [], videos: [], timestamp: now,
      })
      break

    case 'done': {
      const last = _lastAssistantMsg()
      if (last) last.isFinished = true
      const lastThinking = _lastThinkingMsg()
      if (lastThinking) lastThinking.isFinished = true
      sending.value = false
      if (activeTask.value && event.final_report) {
        activeTask.value.finalReport = event.final_report
        activeTask.value.status = mapServerTaskStatus(event.status || event.final_report.status as string | undefined)
        activeTask.value.currentStage = event.final_report.summary as string || '后端最终报告已生成。'
        ;((event.final_report.artifacts as Record<string, any>[] | undefined) || []).forEach(item => upsertServerArtifact(item))
        addTaskLog('最终报告', activeTask.value.currentStage)
        break
      }
      if (activeTask.value && !['failed', 'canceled'].includes(activeTask.value.status)) {
        const hasCompletedWork = activeTask.value.steps.some(s => s.status === 'completed') || activeTask.value.artifacts.length > 0
        const hasRunningWork = activeTask.value.steps.some(s => s.status === 'running' || s.status === 'awaiting_approval')
        const assistantText = visibleAssistantMessages.value.map(m => m.content || '').join('\n')
        const hasIncompleteText = /(剩余\s*TODO|尚未完成|未完成|还需要|需要继续|先执行第?\s*[1-9一二三四五六]?步)/.test(assistantText)
        if (hasCompletedWork || !hasRunningWork) {
          activeTask.value.status = hasCompletedWork && !hasIncompleteText ? 'completed' : 'failed'
          activeTask.value.currentStage = hasCompletedWork
            ? (hasIncompleteText ? '任务未完成：模型列出了剩余 TODO，但没有继续调用工具。' : '任务已完成，结果与过程记录已汇总。')
            : '本轮没有检测到实际工具执行，请重新发送并明确要求调用工具。'
          if (hasCompletedWork && !hasIncompleteText) {
            activeTask.value.steps
              .filter(s => s.status === 'running' || s.status === 'awaiting_approval')
              .forEach(s => {
                s.status = 'completed'
                s.finishedAt = s.finishedAt || now
              })
          }
        }
      }
      break
    }

    case 'incomplete':
      sending.value = false
      if (activeTask.value) {
        activeTask.value.status = 'failed'
        activeTask.value.currentStage = event.content || '任务未完成：仍有 TODO 未执行。'
        addTaskLog('任务未完成', event.content || '仍有 TODO 未执行。')
      }
      messages.value.push({
        id: ++msgIdCounter, type: 'error',
        content: event.content || '任务未完成：仍有 TODO 未执行。', timestamp: now,
      })
      break

    case 'tool_confirm':
      // 结束之前的 thinking 消息
      { const lastTh = _lastThinkingMsg(); if (lastTh) lastTh.isFinished = true }
      if (activeTask.value) {
        const step = ensureToolStep(event.tool, event.description, event.tool_call_id)
        if (step) {
          step.status = 'awaiting_approval'
          step.startedAt = step.startedAt || now
        }
        activeTask.value.status = 'awaiting_approval'
        activeTask.value.currentStage = `等待确认：${step?.title || toolDisplayName(event.tool)}`
        addTaskLog('等待用户确认', event.description || toolDisplayName(event.tool), step?.id)
      }
      messages.value.push({
        id: ++msgIdCounter, type: 'tool_confirm',
        tool: event.tool, toolInput: event.input,
        description: event.description,
        toolCallId: event.tool_call_id,
        timestamp: now,
      })
      break

    case 'tool_start':
      if (activeTask.value) {
        const step = ensureToolStep(event.tool, event.description, event.tool_call_id)
        if (step) {
          step.status = 'running'
          step.startedAt = step.startedAt || now
        }
        activeTask.value.status = 'running'
        activeTask.value.currentStage = `正在执行：${step?.title || toolDisplayName(event.tool)}`
        addTaskLog('开始执行工具', event.description || toolDisplayName(event.tool), step?.id)
      }
      messages.value.push({
        id: ++msgIdCounter, type: 'tool_start',
        tool: event.tool, toolInput: event.input, description: event.description, timestamp: now,
      })
      startElapsedTimer()
      break

    case 'tool_done': {
      stopElapsedTimer()
      // 解析 frame 索引用于精确匹配并行模式的 tool_start
      let frameIdx: number | undefined
      try { frameIdx = event.result ? JSON.parse(event.result).frame : undefined } catch { /* ignore */ }

      let startIdx = -1
      if (frameIdx !== undefined) {
        // 精确匹配：tool + frame
        for (let i = messages.value.length - 1; i >= 0; i--) {
          const m = messages.value[i]
          if (m.type === 'tool_start' && m.tool === event.tool && m.toolInput?.frame === frameIdx) {
            startIdx = i; break
          }
        }
      }
      if (startIdx < 0) {
        // fallback：仅按 tool 名匹配
        for (let i = messages.value.length - 1; i >= 0; i--) {
          if (messages.value[i].type === 'tool_start' && messages.value[i].tool === event.tool) {
            startIdx = i; break
          }
        }
      }
      if (startIdx >= 0) messages.value.splice(startIdx, 1)

      const imageUrl = event.image_url
        || (event.result || '').match(/(\/uploads\/\S+\.(?:png|jpg|jpeg|webp))/i)?.[1]
        || (event.result || '').match(/(https?:\/\/\S+\.(?:png|jpg|jpeg|webp))/i)?.[1]
      const videoUrl = event.video_url
        || (event.result || '').match(/(\/uploads\/\S+\.(?:mp4|webm))/i)?.[1]
      const audioUrl = event.audio_url
        || (event.result || '').match(/(\/uploads\/\S+\.(?:mp3|wav))/i)?.[1]

      if (activeTask.value) {
        const step = findTaskStepByTool(event.tool)
        if (event.step_uid && event.standard_result?.artifacts) {
          ;(event.standard_result.artifacts as Record<string, any>[]).forEach(item => upsertServerArtifact(item, event.step_uid))
        }
        if (step) {
          const failed = !!(event.result || '').match(/"error"|"status":\s*"failed"|用户拒绝执行/)
          step.status = failed ? 'failed' : 'completed'
          step.finishedAt = now
          activeTask.value.status = failed ? 'failed' : 'running'
          activeTask.value.currentStage = failed ? `${step.title} 执行失败` : `${step.title} 已完成`
          addTaskLog(failed ? '工具执行失败' : '工具执行完成', event.result || step.title, step.id)
          if (imageUrl) addArtifact('image', imageUrl, step.title)
          if (videoUrl) addArtifact('video', videoUrl, step.title)
          if (audioUrl) addArtifact('audio', audioUrl, step.title)
        }
      }

      if (imageUrl) {
        const aMsg = _lastAssistantMsg()
        if (aMsg) {
          if (!aMsg.images) aMsg.images = []
          aMsg.images.push(imageUrl)
        } else {
          messages.value.push({
            id: ++msgIdCounter, type: 'assistant',
            content: '', images: [imageUrl], timestamp: now,
          })
        }
      } else if (videoUrl) {
        const aMsg = _lastAssistantMsg()
        if (aMsg) {
          if (!aMsg.videos) aMsg.videos = []
          aMsg.videos.push(videoUrl)
        }
      } else if (audioUrl) {
        messages.value.push({
          id: ++msgIdCounter, type: 'assistant',
          content: `🔊 语音已生成：[播放](${audioUrl})`, timestamp: now,
        })
      } else {
        messages.value.push({
          id: ++msgIdCounter, type: 'tool_done',
          tool: event.tool, toolResult: event.result,
          duration: event.duration, timestamp: now,
        })
      }
      break
    }

    case 'error':
      if (activeTask.value) {
        activeTask.value.status = 'failed'
        activeTask.value.currentStage = event.content || '执行过程中发生错误。'
        addTaskLog('执行错误', event.content)
      }
      messages.value.push({
        id: ++msgIdCounter, type: 'error',
        content: event.content, timestamp: now,
      })
      break
  }
  scrollToBottom()
}

// ──────────── 操作 ────────────
function clearChat() {
  agentWS.disconnect()
  messages.value = []
  activeTask.value = null
  streamingText.value = ''
  sending.value = false
  msgIdCounter = 0
}

async function downloadAllImages() {
  for (let i = 0; i < allImageUrls.value.length; i++) {
    const url = allImageUrls.value[i]
    try {
      const resp = await fetch(url)
      const blob = await resp.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `comic_frame_${i + 1}.png`
      a.click()
      URL.revokeObjectURL(a.href)
      await new Promise(r => setTimeout(r, 300))
    } catch {
      ElMessage.error(`下载第 ${i + 1} 张失败`)
    }
  }
}

// ──────────── 初始化：从后端加载配置数据 ────────────
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

  // 如果模型列表非空，自动选中默认 agent 模型
  const defaultAgent = modelList.value.find(m => m.is_enabled && m.is_default && m.category === 'agent_brain')
  if (defaultAgent) selectedModel.value = defaultAgent.model_id
}

onMounted(() => {
  loadConfigData()
})

// ──────────── 配置 toggle 处理 ────────────
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

onUnmounted(() => {
  agentWS.disconnect()
  sending.value = false
})
</script>

<style scoped lang="scss">
.agent-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px - 48px);
  margin: -24px;
  background: #f8f9fb;
}

// ──────────── 顶部 ────────────
.agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: white;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;

  .agent-header-left {
    display: flex;
    align-items: center;
    gap: 8px;

    .agent-icon { font-size: 22px; }
    .agent-title {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
  }
}

// ──────────── 消息区域 ────────────
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #606266;

  .empty-icon { font-size: 64px; margin-bottom: 12px; }
  h3 { font-size: 20px; margin: 0 0 8px; color: #303133; }
  p { font-size: 14px; color: #909399; margin: 0 0 24px; }

  .quick-prompts {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: center;
    max-width: 600px;

    .quick-prompt-title {
      width: 100%;
      text-align: center;
      font-size: 13px;
      color: #c0c4cc;
      margin-bottom: 4px;
    }
  }

  .quick-btn {
    font-size: 13px;
    padding: 8px 16px;
  }
}

.agent-workspace {
  width: min(980px, 100%);
  margin: 0 auto;
}

.agent-workspace--narrative {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.narrative-block {
  display: grid;
  grid-template-columns: 54px 1fr;
  gap: 14px;
  position: relative;

  &:not(:last-child)::before {
    content: '';
    position: absolute;
    left: 26px;
    top: 52px;
    bottom: -4px;
    width: 2px;
    background: #e5e7eb;
  }

  .block-marker {
    width: 54px;
    height: 54px;
    border-radius: 16px;
    background: #111827;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 14px;
    box-shadow: 0 10px 24px rgba(17, 24, 39, 0.16);
    z-index: 1;
  }

  .block-main {
    margin-bottom: 18px;
    padding: 18px 20px;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
    box-shadow: 0 8px 28px rgba(15, 23, 42, 0.05);
  }

  &.narrative-block--primary .block-main {
    border-color: #c7d2fe;
    background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
  }

  &.narrative-block--final .block-main {
    border-color: #bbf7d0;
    background: linear-gradient(180deg, #ffffff 0%, #f7fef9 100%);
  }
}

.block-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;

  h2 {
    margin: 4px 0 0;
    color: #111827;
    font-size: 19px;
    font-weight: 750;
    letter-spacing: -0.02em;
  }
}

.section-kicker {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #94a3b8;
  font-weight: 700;
}

.progress-text {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.requirement-card {
  padding: 14px 16px;
  border-radius: 14px;
  background: #0f172a;
  color: #fff;
  margin-bottom: 12px;

  .requirement-label {
    color: #94a3b8;
    font-size: 12px;
    margin-bottom: 6px;
  }

  .requirement-text {
    line-height: 1.7;
    font-size: 14px;
  }
}

.understanding-grid {
  display: grid;
  grid-template-columns: 0.8fr 1.35fr 1.1fr;
  gap: 10px;

  > div {
    padding: 12px 14px;
    border-radius: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
  }

  span {
    display: block;
    color: #94a3b8;
    font-size: 12px;
    margin-bottom: 6px;
  }

  strong {
    color: #1f2937;
    font-size: 13px;
    line-height: 1.55;
  }
}

.plan-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.plan-row {
  display: grid;
  grid-template-columns: 30px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;

  .plan-index {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #e5e7eb;
    color: #475569;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 12px;
  }

  .plan-copy {
    min-width: 0;

    strong {
      display: block;
      color: #111827;
      font-size: 14px;
    }
    p {
      margin: 3px 0 0;
      color: #64748b;
      font-size: 12px;
      line-height: 1.5;
    }
  }

  &.plan-row--running,
  &.plan-row--awaiting_approval {
    border-color: #bfdbfe;
    background: #eff6ff;
  }

  &.plan-row--completed {
    border-color: #bbf7d0;
    background: #f0fdf4;
  }
}

.execution-flow {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.execution-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;

  .step-meta {
    display: flex;
    gap: 12px;
    margin-top: 8px;
    color: #94a3b8;
    font-size: 12px;
  }

  > p {
    margin: 8px 0 0;
    color: #64748b;
    line-height: 1.6;
    font-size: 13px;
  }

  &.execution-card--running,
  &.execution-card--awaiting_approval {
    border-color: #93c5fd;
    background: #eff6ff;
  }

  &.execution-card--completed {
    border-color: #86efac;
    background: #f0fdf4;
  }
}

.execution-card-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;

  span {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h3 {
    margin: 3px 0 0;
    color: #111827;
    font-size: 15px;
  }
}

.inline-approval {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.compact-tool-collapse {
  margin-top: 12px;

  :deep(.el-collapse-item__header) {
    height: 36px;
    border-radius: 10px;
    padding: 0 12px;
    background: rgba(255, 255, 255, 0.72);
    color: #64748b;
    font-size: 12px;
    border: 1px solid #e2e8f0;
  }

  :deep(.el-collapse-item__wrap) {
    background: transparent;
    border-bottom: none;
  }
}

.compact-log-list {
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.compact-log-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;

  .compact-log-title {
    display: flex;
    justify-content: space-between;
    padding: 8px 10px;
    background: #f8fafc;
    color: #334155;
    font-size: 12px;
    font-weight: 600;

    em {
      font-style: normal;
      color: #94a3b8;
      font-weight: 400;
    }
  }

  pre {
    margin: 0;
    padding: 8px 10px;
    color: #64748b;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 12px;
    line-height: 1.55;
    font-family: 'SF Mono', Consolas, monospace;
  }
}

.empty-artifacts {
  min-height: 96px;
  border: 1px dashed #cbd5e1;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
  background: #f8fafc;
}

.result-strip {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.result-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  overflow: hidden;
  background: #f8fafc;

  .result-preview,
  .result-video {
    width: 100%;
    height: 158px;
    object-fit: cover;
    display: block;
  }

  .result-file {
    height: 158px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #64748b;
  }

  .result-copy {
    padding: 10px;

    strong,
    span {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    strong { color: #111827; font-size: 13px; }
    span { margin-top: 4px; color: #94a3b8; font-size: 12px; }
  }
}

.analysis-panel,
.final-report {
  padding: 14px 16px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
  line-height: 1.75;
  font-size: 14px;
}

.assistant-final-messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.summary-message {
  padding: 12px 14px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #dcfce7;
  color: #334155;
  line-height: 1.7;
}

.task-log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 0;
}

.task-log-item {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;

  .task-log-head {
    display: flex;
    justify-content: space-between;
    padding: 10px 12px;
    background: #f8fafc;
    color: #334155;
    font-size: 13px;
    font-weight: 600;

    em {
      font-style: normal;
      color: #94a3b8;
      font-weight: 400;
    }
  }

  pre {
    margin: 0;
    padding: 12px;
    white-space: pre-wrap;
    word-break: break-word;
    color: #64748b;
    font-size: 12px;
    line-height: 1.65;
    font-family: 'SF Mono', Consolas, monospace;
  }
}

// ──────────── 消息行 ────────────
.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  max-width: 800px;
  width: 100%;
  margin: 0 auto;

  &.user {
    justify-content: flex-end;
  }
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;

  &.user-avatar { background: #ecf5ff; }
  &.bot-avatar { background: #f0f9eb; }
}

.msg-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  position: relative;

  .msg-content {
    font-size: 14px;
    line-height: 1.7;
    word-break: break-word;

    :deep(strong) { color: #303133; }
    :deep(code) {
      background: rgba(0,0,0,0.06);
      padding: 1px 5px;
      border-radius: 4px;
      font-family: 'SF Mono', monospace;
      font-size: 13px;
    }
  }

  .msg-time {
    font-size: 11px;
    color: #c0c4cc;
    margin-top: 6px;
    text-align: right;
  }
}

.user-bubble {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border-radius: 16px 4px 16px 16px;

  .msg-time { color: rgba(255,255,255,0.6); }
}

.bot-bubble {
  background: white;
  border-radius: 4px 16px 16px 16px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.08);
  color: #303133;
}

// ──────────── 工具卡片 ────────────
.tool-card {
  max-width: 500px;
  border-radius: 12px;
  padding: 14px 16px;
  border: 1px solid;

  &.tool-card--running {
    background: #f0f5ff;
    border-color: #b3d4ff;
  }

  &.tool-card--done {
    background: #f6ffed;
    border-color: #b7eb8f;
  }

  &.tool-card--confirm {
    background: #fffbe6;
    border-color: #ffe58f;
  }

  .tool-confirm-actions {
    display: flex;
    gap: 8px;
    margin-top: 10px;
  }

  .tool-confirm-result {
    margin-top: 8px;
  }

  .tool-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 500;

    .tool-name { color: #303133; }
    .tool-elapsed {
      margin-left: auto;
      font-size: 12px;
      color: #e6a23c;
      font-family: monospace;
      font-weight: 600;
    }
    .tool-duration {
      margin-left: auto;
      font-size: 12px;
      color: #909399;
      font-family: monospace;
    }
  }

  .tool-action-desc {
    font-size: 13px;
    color: #606266;
    margin-top: 6px;
    padding: 4px 8px;
    background: #f0f7ff;
    border-radius: 4px;
    border-left: 3px solid #409EFF;
  }

  .tool-hint {
    font-size: 12px;
    color: #909399;
    margin-top: 6px;
    padding: 4px 0;
  }

  .tool-params {
    margin-top: 10px;
    padding: 8px 10px;
    background: rgba(0,0,0,0.03);
    border-radius: 6px;
    font-size: 12px;
    font-family: 'SF Mono', Consolas, monospace;

    .tool-param-row {
      display: flex;
      gap: 6px;
      line-height: 1.6;

      .tool-param-key {
        color: #909399;
        flex-shrink: 0;
      }
      .tool-param-val {
        color: #606266;
        word-break: break-all;
      }
    }
  }

  .tool-image-wrap {
    margin-top: 10px;

    .tool-image {
      width: 280px;
      height: 280px;
      border-radius: 8px;
      cursor: pointer;
      overflow: hidden;
    }

    .img-loading {
      width: 280px;
      height: 280px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f5f7fa;
      border-radius: 8px;
    }
  }

  .tool-video-wrap {
    margin-top: 10px;

    .tool-video {
      width: 100%;
      max-width: 400px;
      border-radius: 8px;
    }
  }

  .tool-result-text {
    margin-top: 8px;
    font-size: 13px;
    color: #606266;
  }
}

// ──────────── 错误 ────────────
.error-alert {
  max-width: 500px;
}

// ──────────── 流式打字 ────────────
.cursor-blink {
  animation: blink 1s step-end infinite;
  font-size: 16px;
  color: #667eea;
}

@keyframes blink {
  50% { opacity: 0; }
}

// ──────────── 图片汇总条 ────────────
.gallery-bar {
  flex-shrink: 0;
  background: white;
  border-top: 1px solid #ebeef5;
  padding: 8px 20px;

  .gallery-bar-inner {
    max-width: 800px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .gallery-label {
    font-size: 13px;
    color: #606266;
    font-weight: 500;
    white-space: nowrap;
  }

  .gallery-thumbs {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    flex: 1;

    .gallery-thumb {
      width: 48px;
      height: 48px;
      border-radius: 6px;
      cursor: pointer;
      flex-shrink: 0;
    }
  }
}

// ──────────── 抽屉内样式 ────────────
.drawer-tabs {
  :deep(.el-tabs__header) {
    padding: 0 4px;
  }
}

.panel-desc {
  font-size: 13px;
  color: #909399;
  margin-bottom: 12px;
  line-height: 1.6;
}

.config-table {
  :deep(.el-table__header th) {
    background: #f5f7fa;
    font-size: 12px;
  }
  :deep(.el-table__body td) {
    font-size: 13px;
  }
}

.code-tag {
  background: #f5f7fa;
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
  color: #606266;
}

.panel-summary {
  margin-top: 12px;
  font-size: 12px;
  color: #909399;
  text-align: right;
}

// ──────────── Prompt 卡片 ────────────
.prompt-card {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;

  .prompt-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .prompt-card-title {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;

    strong { font-size: 13px; color: #303133; }
  }

  .prompt-card-desc {
    font-size: 12px;
    color: #909399;
    margin-bottom: 8px;
    line-height: 1.5;
  }

  .prompt-textarea {
    :deep(.el-textarea__inner) {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 12px;
      line-height: 1.6;
      background: #fff;
      border-color: #dcdfe6;
      &:focus { border-color: #409eff; }
    }
  }
}

// ──────────── 输入区域 ────────────
.input-area {
  flex-shrink: 0;
  background: white;
  border-top: 1px solid #ebeef5;
  padding: 8px 20px 6px;

  .input-toolbar {
    max-width: 800px;
    margin: 0 auto 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;

    .toolbar-divider {
      width: 1px;
      height: 20px;
      background: #e4e7ed;
      margin: 0 2px;
    }

    .toolbar-switch {
      display: flex;
      align-items: center;
      gap: 4px;

      .toolbar-switch-label {
        font-size: 12px;
        color: #606266;
        white-space: nowrap;
        user-select: none;
      }
    }
  }

  .attached-images {
    max-width: 800px;
    margin: 0 auto 8px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;

    .attached-image-item {
      position: relative;
      width: 64px;
      height: 64px;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid #dcdfe6;

      .attached-thumb {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .attached-loading {
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 18px;
      }

      .attached-remove {
        position: absolute;
        top: 2px;
        right: 2px;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: rgba(0, 0, 0, 0.5);
        color: white;
        border: none;
        cursor: pointer;
        font-size: 12px;
        line-height: 18px;
        text-align: center;
        padding: 0;
        display: none;
        &:hover { background: rgba(0, 0, 0, 0.7); }
      }

      &:hover .attached-remove { display: block; }
    }
  }

  .input-row {
    max-width: 800px;
    margin: 0 auto;
    display: flex;
    gap: 10px;
    align-items: flex-end;

    .upload-btn {
      flex-shrink: 0;
      margin-bottom: 4px;
    }

    .input-textarea { flex: 1; }
  }

  .input-hint {
    max-width: 800px;
    margin: 4px auto 0;
    font-size: 11px;
    color: #c0c4cc;
    text-align: center;
  }
}

// ──────────── 思考气泡 ────────────
.thinking-bubble {
  max-width: 560px;
  background: linear-gradient(135deg, #f0f4ff 0%, #f5f0ff 100%);
  border: 1px solid #d0d7ff;
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 12px;

  .thinking-collapse-header {
    display: flex;
    align-items: center;
    gap: 3px;
    cursor: pointer;
    user-select: none;
    padding: 2px 0;
    &:hover { opacity: 0.8; }
  }

  .thinking-dot {
    width: 5px;
    height: 5px;
    background: #a0aff0;
    border-radius: 50%;
    animation: thinking-blink 1.2s infinite;
    &:nth-child(2) { animation-delay: 0.3s; }
    &:nth-child(3) { animation-delay: 0.6s; }
  }

  .thinking-content {
    white-space: pre-wrap;
    word-break: break-word;
    color: #606699;
    font-size: 11.5px;
    line-height: 1.7;
    font-family: 'SF Mono', Consolas, monospace;
    margin: 6px 0 0;
    background: transparent;
    border: none;
    border-top: 1px dashed #d0d7ff;
    padding: 6px 0 0;
  }
}

@keyframes thinking-blink {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

.thinking-done {
  background: #f6ffed;
  border-color: #b7eb8f;
}


// ──────────── 内联图片网格 ────────────
.inline-images {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  margin-top: 10px;

  .inline-img {
    width: 100%;
    height: 150px;
    border-radius: 8px;
    cursor: pointer;
    transition: transform 0.2s;
    overflow: hidden;
    display: block;
    &:hover { transform: scale(1.03); }
    :deep(img) {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    :deep(.el-image__inner) {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }
}

.inline-videos {
  margin-top: 10px;
  .inline-video {
    width: 100%;
    max-width: 480px;
    border-radius: 8px;
  }
}

// ──────────── HTML 沙箱 ────────────
.html-sandbox-wrap {
  margin: 12px 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #dcdfe6;
  background: #fff;

  .html-sandbox {
    width: 100%;
    min-height: 320px;
    border: none;
    display: block;
  }
}

// ──────────── Markdown 表格 ────────────
:deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;

  th, td {
    border: 1px solid #e4e7ed;
    padding: 6px 10px;
    text-align: left;
    line-height: 1.5;
  }

  th {
    background: #f5f7fa;
    font-weight: 600;
    color: #303133;
  }

  tr:nth-child(even) td {
    background: #fafafa;
  }
}
</style>
