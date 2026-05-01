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
</style>
