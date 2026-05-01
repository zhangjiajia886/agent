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

    <!-- ══════════ 设置抽屉 ══════════ -->
    <SettingsDrawer v-model="drawerVisible" v-model:tab="drawerTab" />

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

      <TaskWorkspace
        :active-task="activeTask"
        :show-plan-block="showPlanBlock"
        :show-execution-block="showExecutionBlock"
        :show-result-block="showResultBlock"
        :show-final-block="showFinalBlock"
        :completed-step-count="completedStepCount"
        :visible-plan-steps="visiblePlanSteps"
        :executable-steps="executableSteps"
        :all-image-urls="allImageUrls"
        :result-analysis-text="resultAnalysisText"
        :final-report-text="finalReportText"
        :visible-assistant-messages="visibleAssistantMessages"
        :step-logs="stepLogs"
        :compact-log-content="compactLogContent"
        @approve-step="approveTaskStep"
      />

      <ChatMessageList
        :timeline-messages="timelineMessages"
        :streaming-text="streamingText"
        :all-image-urls="allImageUrls"
        :tool-elapsed="toolElapsed"
        @tool-approval="handleToolApproval"
      />
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

    <ChatInputBar
      v-model:model="selectedModel"
      v-model:style="selectedStyle"
      v-model:frames="selectedFrames"
      v-model:tts="ttsEnabled"
      v-model:video="autoVideo"
      v-model:thinking="showThinking"
      v-model:exec="autoExec"
      v-model:text="inputText"
      :sending="sending"
      :attached-images="attachedImages"
      :max-images="MAX_IMAGES"
      :enabled-agent-models="enabledAgentModels"
      @send="handleSend"
      @image-select="handleImageSelect"
      @remove-image="removeAttachedImage"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Download, Setting } from '@element-plus/icons-vue'
import { uploadAgentImage } from '@/api/comic-agent'
import type { AttachedImage } from './types'
import { useTask, useElapsed, useConfig, useChat } from './composables'
import SettingsDrawer from './components/SettingsDrawer.vue'
import TaskWorkspace from './components/TaskWorkspace.vue'
import ChatMessageList from './components/ChatMessageList.vue'
import ChatInputBar from './components/ChatInputBar.vue'

// ──────────── 任务管理 (composable) ────────────
const task = useTask()
const { activeTask, stepLogs, compactLogContent } = task

// ──────────── 配置管理 (composable) ────────────
const { selectedModel, enabledAgentModels } = useConfig()

// ──────────── 耗时计时器 (composable) ────────────
const elapsed = useElapsed()
const { toolElapsed } = elapsed

// ──────────── 输入工具栏状态 ────────────
const drawerVisible = ref(false)
const drawerTab = ref('tools')
const selectedStyle = ref('auto')
const selectedFrames = ref(4)
const ttsEnabled = ref(false)
const autoVideo = ref(false)
const showThinking = ref(false)
const autoExec = ref(false)

// ──────────── 图片附件状态 ────────────
const attachedImages = ref<AttachedImage[]>([])
const MAX_IMAGES = 4
const messagesRef = ref<HTMLElement>()

// ──────────── 消息管理 (composable) ────────────
const {
  messages, inputText, sending, streamingText,
  allImageUrls, timelineMessages, visibleAssistantMessages,
  completedStepCount, hasAgentProgress,
  visiblePlanSteps, executableSteps,
  showPlanBlock, showExecutionBlock, showResultBlock, showFinalBlock,
  resultAnalysisText, finalReportText,
  approveTaskStep, handleToolApproval,
  handleSend: _handleSend,
  sendQuickPrompt: _sendQuickPrompt,
  clearChat, downloadAllImages, disconnect,
} = useChat({ task, elapsed, showThinking, messagesRef })

// ──────────── 快捷提示 ────────────
const quickPrompts = [
  { icon: '⚔️', label: '仙侠 4 格漫剧', text: '仙侠风格4格漫剧，一位白衣女侠初次踏入云雾缭绕的神秘仙山，满怀期待与好奇' },
  { icon: '🖌️', label: '水墨 4 格漫剧', text: '水墨国画风格4格漫剧，一位书生在溪边垂钓，忽遇神秘少女翩然而至' },
  { icon: '🎁', label: '盲盒 Q 版漫剧', text: '盲盒Q版风格4格漫剧，超可爱小女生第一次打开神秘礼盒，惊喜连连' },
  { icon: '🌸', label: '动漫风格漫剧', text: '动漫风格4格漫剧，樱花树下的浪漫邂逅，阳光少女与文静男生的初遇' },
]

// ──────────── 发送包装 ────────────
const sendParams = { selectedStyle, selectedFrames, selectedModel, ttsEnabled, autoVideo, autoExec, attachedImages }
function handleSend() { _handleSend(sendParams) }
function sendQuickPrompt(text: string) { _sendQuickPrompt(text, sendParams) }

// ──────────── 图片附件操作 ────────────
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

onUnmounted(() => disconnect())
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
