<template>
  <div class="chat-page">
    <!-- 左侧会话列表 -->
    <div class="session-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">💬 对话列表</span>
        <el-button type="primary" :icon="Plus" circle size="small" @click="handleNewSession" />
      </div>

      <div class="session-list" v-loading="sessionsLoading">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: currentSession?.id === s.id }"
          @click="selectSession(s.id)"
        >
          <div class="session-item-content">
            <div class="session-name">{{ s.title }}</div>
            <div class="session-time">{{ formatTime(s.updated_at) }}</div>
          </div>
          <el-popconfirm title="确定删除此对话？" @confirm="handleDeleteSession(s.id)">
            <template #reference>
              <el-button
                class="delete-btn"
                text
                :icon="Delete"
                size="small"
                @click.stop
              />
            </template>
          </el-popconfirm>
        </div>
        <div v-if="!sessionsLoading && sessions.length === 0" class="empty-sessions">
          暂无对话，点击 + 开始
        </div>
      </div>
    </div>

    <!-- 右侧聊天区 -->
    <div class="chat-main">
      <div v-if="!currentSession" class="chat-empty">
        <div class="empty-icon">🤖</div>
        <p>选择或创建一个对话开始聊天</p>
        <el-button type="primary" :icon="Plus" @click="handleNewSession">新建对话</el-button>
      </div>

      <template v-else>
        <!-- 顶部标题栏 -->
        <div class="chat-header">
          <div class="chat-title">
            <span v-if="!editingTitle" @dblclick="editingTitle = true">{{ currentSession.title }}</span>
            <el-input
              v-else
              v-model="titleInput"
              size="small"
              style="width: 200px"
              @blur="saveTitle"
              @keyup.enter="saveTitle"
              @keyup.esc="editingTitle = false"
              ref="titleInputRef"
            />
          </div>
          <div class="chat-actions">
            <el-tooltip content="设置系统提示词">
              <el-button text :icon="Setting" @click="showSystemPrompt = true" />
            </el-tooltip>
            <el-tooltip content="清空当前对话消息">
              <el-button text :icon="RefreshLeft" @click="clearMessages" />
            </el-tooltip>
          </div>
        </div>

        <!-- 消息区域 -->
        <div class="messages-area" ref="messagesRef">
          <div v-if="currentSession.messages.length === 0" class="messages-empty">
            <p>发送消息开始对话 ✨</p>
          </div>

          <div
            v-for="msg in currentSession.messages"
            :key="msg.id"
            class="message-row"
            :class="msg.role"
          >
            <div class="avatar">
              <span v-if="msg.role === 'user'">👤</span>
              <span v-else>🤖</span>
            </div>
            <div class="bubble">
              <div class="bubble-content" v-html="renderMarkdown(msg.content)" />
              <div class="bubble-footer">
                <div class="bubble-time">{{ formatTime(msg.created_at) }}</div>
                <button
                  v-if="msg.role === 'assistant' && messageAudio.get(msg.id)"
                  class="replay-btn"
                  :class="{ playing: playingMsgId === msg.id }"
                  @click="replayMessage(msg.id)"
                  :title="playingMsgId === msg.id ? '播放中…' : '回放语音'"
                >
                  {{ playingMsgId === msg.id ? '■' : '🔊' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 流式回复中的临时消息 -->
          <div v-if="streamingContent" class="message-row assistant">
            <div class="avatar"><span>🤖</span></div>
            <div class="bubble">
              <div class="bubble-content streaming" v-html="renderMarkdown(streamingContent)" />
              <span class="cursor-blink">▋</span>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-toolbar">
            <el-tooltip :content="recording ? '点击停止录音' : '语音输入（点击开始录音）'">
              <el-button
                text :icon="Microphone" size="small"
                @click="startVoiceInput"
                :type="recording ? 'danger' : 'default'"
                :loading="asrLoading"
              >
                <span v-if="recording" style="font-size:11px;color:#f56c6c;">录音中…</span>
              </el-button>
            </el-tooltip>
            <el-tooltip content="使用 TTS 朗读 AI 回复">
              <el-switch v-model="ttsEnabled" size="small" active-text="TTS 朗读" />
            </el-tooltip>
            <el-select
              v-if="ttsEnabled"
              v-model="selectedVoiceId"
              placeholder="选择数字音色"
              clearable
              size="small"
              style="width: 160px"
            >
              <el-option
                v-for="v in voiceModels"
                :key="v.id"
                :label="v.title"
                :value="v.id"
              />
            </el-select>
            <audio ref="ttsAudioRef" style="display:none" />
            <span v-if="lastPerf" class="perf-badge">
              TTFT {{ lastPerf.ttft_ms }}ms · {{ lastPerf.tokens }}T · {{ lastPerf.tps }}t/s
            </span>
          </div>
          <div class="input-row">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="3"
              placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
              resize="none"
              @keydown.enter.exact.prevent="sendMessage"
              :disabled="sending"
            />
            <el-button
              type="primary"
              :icon="sending ? Loading : Promotion"
              :loading="sending"
              :disabled="!inputText.trim()"
              class="send-btn"
              @click="sendMessage"
            >
              发送
            </el-button>
          </div>
        </div>
      </template>
    </div>

    <!-- 系统提示词弹窗 -->
    <el-dialog v-model="showSystemPrompt" title="系统提示词" width="500px">
      <el-input
        v-model="systemPromptInput"
        type="textarea"
        :rows="6"
        placeholder="设置 AI 的角色和行为，例如：你是一个专业的语音技术顾问..."
      />
      <template #footer>
        <el-button @click="showSystemPrompt = false">取消</el-button>
        <el-button type="primary" @click="saveSystemPrompt">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete, Setting, RefreshLeft, Microphone, Promotion, Loading } from '@element-plus/icons-vue'
import {
  getSessions, createSession, getSession,
  updateSession, deleteSession,
} from '@/api/chat'
import { getModels } from '@/api/voice'
import { synthesize, getTask } from '@/api/tts'
import { recognize, getTask as getAsrTask } from '@/api/asr'
import type { ChatSessionSchema, ChatSessionListItem, VoiceModel } from '@/types/api'

const sessions = ref<ChatSessionListItem[]>([])
const currentSession = ref<ChatSessionSchema | null>(null)
const sessionsLoading = ref(false)
const sending = ref(false)
const inputText = ref('')
const streamingContent = ref('')
const ttsEnabled = ref(false)
const recording = ref(false)
const editingTitle = ref(false)
const titleInput = ref('')
const titleInputRef = ref()
const showSystemPrompt = ref(false)
const systemPromptInput = ref('')
const messagesRef = ref<HTMLElement>()
const ttsAudioRef = ref<HTMLAudioElement>()
const voiceModels = ref<VoiceModel[]>([])
const selectedVoiceId = ref<number | undefined>(undefined)
const asrLoading = ref(false)
const lastPerf = ref<{ ttft_ms: number; total_ms: number; tokens: number; tps: number } | null>(null)
const messageAudio = ref<Map<number, string>>(new Map())
const playingMsgId = ref<number | null>(null)
let mediaRecorder: MediaRecorder | null = null
let audioChunks: Blob[] = []

// 分句实时 TTS 队列
let ttsQueue: string[] = []
let ttsProcessing = false
let ttsStreamBuf = ''
const SENTENCE_END = /[^\u3002\uff01\uff1f\u2026\n;!?]*[\u3002\uff01\uff1f\u2026\n;!?]+/

function formatTime(dateStr: string) {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function renderMarkdown(text: string): string {
  return text
    .replace(/\[[^\]]{1,40}\]/g, '')
    .replace(/\([a-zA-Z][a-zA-Z\s]{0,30}\)/g, '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    sessions.value = await getSessions()
  } finally {
    sessionsLoading.value = false
  }
}

async function selectSession(id: number) {
  currentSession.value = await getSession(id)
  streamingContent.value = ''
  scrollToBottom()
}

async function handleNewSession() {
  const s = await createSession({ title: '新对话' })
  await loadSessions()
  currentSession.value = await getSession(s.id)
  streamingContent.value = ''
}

async function handleDeleteSession(id: number) {
  await deleteSession(id)
  if (currentSession.value?.id === id) currentSession.value = null
  await loadSessions()
  ElMessage.success('已删除')
}

async function sendMessage() {
  if (!inputText.value.trim() || !currentSession.value || sending.value) return

  const msg = inputText.value.trim()
  inputText.value = ''
  sending.value = true
  streamingContent.value = ''
  ttsQueue = []
  ttsStreamBuf = ''
  ttsProcessing = false

  currentSession.value.messages.push({
    id: Date.now(),
    role: 'user',
    content: msg,
    tts_audio_url: null,
    created_at: new Date().toISOString(),
  })
  scrollToBottom()

  try {
    const token = localStorage.getItem('access_token') || ''
    const baseUrl = '/api/v1/chat/stream'

    const response = await fetch(baseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ session_id: currentSession.value.id, message: msg }),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let fullContent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value)
      const lines = text.split('\n')
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim()
        try {
          const parsed = JSON.parse(data)
          if (parsed.token) {
            fullContent += parsed.token
            streamingContent.value = fullContent
            scrollToBottom()
            // 分句实时 TTS
            if (ttsEnabled.value) {
              ttsStreamBuf += parsed.token
              let m: RegExpExecArray | null
              while ((m = SENTENCE_END.exec(ttsStreamBuf)) !== null) {
                enqueueTTS(m[0].trim())
                ttsStreamBuf = ttsStreamBuf.slice(m.index + m[0].length)
              }
            }
          } else if (parsed.done) {
            streamingContent.value = ''
            const assistantContent = parsed.content
            if (parsed.perf) lastPerf.value = parsed.perf
            const newMsgId = Date.now() + 1
            currentSession.value!.messages.push({
              id: newMsgId,
              role: 'assistant',
              content: assistantContent,
              tts_audio_url: null,
              created_at: new Date().toISOString(),
            })
            scrollToBottom()
            await loadSessions()
            // TTS：刷入流式未完成的剩余句子，再整体兜底
            if (ttsEnabled.value) {
              if (ttsStreamBuf.trim()) enqueueTTS(ttsStreamBuf.trim())
              ttsStreamBuf = ''
            } else {
              speakWithTTS(assistantContent)
            }
            // 后台合成完整音频用于回放按钮
            synthesizeForReplay(newMsgId, assistantContent)
          }
        } catch {}
      }
    }
  } catch (e: unknown) {
    ElMessage.error('发送失败：' + (e instanceof Error ? e.message : '网络错误'))
    streamingContent.value = ''
  } finally {
    sending.value = false
  }
}

async function saveTitle() {
  if (!currentSession.value || !titleInput.value.trim()) {
    editingTitle.value = false
    return
  }
  await updateSession(currentSession.value.id, { title: titleInput.value })
  currentSession.value.title = titleInput.value
  editingTitle.value = false
  await loadSessions()
}

async function saveSystemPrompt() {
  if (!currentSession.value) return
  await updateSession(currentSession.value.id, { system_prompt: systemPromptInput.value })
  currentSession.value.system_prompt = systemPromptInput.value
  showSystemPrompt.value = false
  ElMessage.success('系统提示词已保存')
}

function clearMessages() {
  if (currentSession.value) currentSession.value.messages = []
}

async function startVoiceInput() {
  if (recording.value) {
    mediaRecorder?.stop()
    return
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioChunks = []
    const mimeType = ['audio/webm', 'audio/mp4', 'audio/ogg'].find(t => MediaRecorder.isTypeSupported(t)) ?? ''
    mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
    const actualMime = mediaRecorder.mimeType || 'audio/webm'
    const ext = actualMime.split('/')[1]?.split(';')[0] ?? 'webm'
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data) }
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop())
      recording.value = false
      asrLoading.value = true
      try {
        const blob = new Blob(audioChunks, { type: actualMime })
        const file = new File([blob], `recording.${ext}`, { type: actualMime })
        const res = await recognize(file, 'zh')
        for (let i = 0; i < 20; i++) {
          await new Promise(r => setTimeout(r, 1000))
          const task = await getAsrTask(res.task_id)
          if (task.status === 'completed' && task.recognized_text) {
            inputText.value = task.recognized_text
            break
          }
          if (task.status === 'failed') { ElMessage.error('语音识别失败'); break }
        }
      } catch { ElMessage.error('语音识别出错') } finally {
        asrLoading.value = false
        if (inputText.value.trim()) sendMessage()
      }
    }
    mediaRecorder.start()
    recording.value = true
  } catch {
    ElMessage.error('无法访问麦克风，请检查系统权限')
  }
}

function enqueueTTS(text: string) {
  if (!ttsEnabled.value || !text.trim()) return
  ttsQueue.push(text)
  if (!ttsProcessing) drainTTSQueue()
}

async function drainTTSQueue() {
  ttsProcessing = true
  while (ttsQueue.length > 0) {
    const text = ttsQueue.shift()!
    await speakWithTTS(text)
  }
  ttsProcessing = false
}

async function synthesizeForReplay(msgId: number, text: string) {
  try {
    const res = await synthesize({ text, voice_model_id: selectedVoiceId.value, format: 'wav', latency: 'balanced' })
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const task = await getTask(res.task_id)
      if (task.status === 'completed' && task.audio_url) {
        messageAudio.value = new Map(messageAudio.value).set(msgId, task.audio_url)
        return
      }
      if (task.status === 'failed') return
    }
  } catch {}
}

function replayMessage(msgId: number) {
  const url = messageAudio.value.get(msgId)
  if (!url || !ttsAudioRef.value) return
  if (playingMsgId.value === msgId) {
    ttsAudioRef.value.pause()
    playingMsgId.value = null
    return
  }
  playingMsgId.value = msgId
  ttsAudioRef.value.src = url
  ttsAudioRef.value.onended = () => { playingMsgId.value = null }
  ttsAudioRef.value.play().catch(() => { playingMsgId.value = null })
}

async function speakWithTTS(text: string) {
  if (!ttsEnabled.value || !text.trim()) return
  try {
    const res = await synthesize({
      text,
      voice_model_id: selectedVoiceId.value,
      format: 'wav',
      latency: 'balanced',
    })
    let taskId = res.task_id
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const task = await getTask(taskId)
      if (task.status === 'completed' && task.audio_url) {
        if (ttsAudioRef.value) {
          ttsAudioRef.value.src = task.audio_url
          ttsAudioRef.value.play().catch(() => {})
        }
        return
      }
      if (task.status === 'failed') return
    }
  } catch {}
}

watch(editingTitle, (val) => {
  if (val && currentSession.value) {
    titleInput.value = currentSession.value.title
    nextTick(() => titleInputRef.value?.focus())
  }
})

watch(showSystemPrompt, (val) => {
  if (val && currentSession.value) {
    systemPromptInput.value = currentSession.value.system_prompt || ''
  }
})

onMounted(async () => {
  await loadSessions()
  try {
    const res = await getModels()
    voiceModels.value = res.items
  } catch {}
})
</script>

<style scoped lang="scss">
.chat-page {
  display: flex;
  height: calc(100vh - 64px - 48px);
  gap: 0;
  margin: -24px;
  background: #f5f7fa;
}

.session-sidebar {
  width: 260px;
  background: white;
  border-right: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;

  .sidebar-header {
    padding: 16px;
    border-bottom: 1px solid #ebeef5;
    display: flex;
    align-items: center;
    justify-content: space-between;

    .sidebar-title {
      font-weight: 600;
      font-size: 15px;
      color: #303133;
    }
  }

  .session-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .session-item {
    display: flex;
    align-items: center;
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.15s;
    margin-bottom: 2px;

    &:hover { background: #f5f7fa; }
    &.active { background: #ecf5ff; }

    .session-item-content {
      flex: 1;
      min-width: 0;
      .session-name {
        font-size: 13px;
        color: #303133;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .session-time {
        font-size: 11px;
        color: #c0c4cc;
        margin-top: 2px;
      }
    }

    .delete-btn { opacity: 0; transition: opacity 0.15s; }
    &:hover .delete-btn { opacity: 1; }
  }

  .empty-sessions {
    text-align: center;
    color: #c0c4cc;
    font-size: 13px;
    padding: 32px 16px;
  }
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #f8f9fa;

  .chat-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    color: #909399;

    .empty-icon { font-size: 64px; }
    p { font-size: 15px; }
  }
}

.chat-header {
  padding: 12px 20px;
  background: white;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;

  .chat-title {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
    cursor: text;
  }

  .chat-actions { display: flex; gap: 4px; align-items: center; }
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;

  .messages-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #c0c4cc;
    font-size: 14px;
  }
}

.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;

  &.user {
    flex-direction: row-reverse;

    .bubble {
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: white;
      border-radius: 16px 4px 16px 16px;

      .bubble-time { color: rgba(255,255,255,0.7); }
    }
  }

  &.assistant .bubble {
    background: white;
    border-radius: 4px 16px 16px 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }

  .avatar {
    font-size: 24px;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .bubble {
    max-width: 70%;
    padding: 10px 14px;

    .bubble-content {
      font-size: 14px;
      line-height: 1.7;
      word-break: break-word;

      :deep(code) {
        background: rgba(0,0,0,0.08);
        padding: 1px 5px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 13px;
      }
    }

    .bubble-footer {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 6px;
      margin-top: 4px;
    }

    .bubble-time {
      font-size: 11px;
      color: #c0c4cc;
    }

    .replay-btn {
      background: none;
      border: none;
      cursor: pointer;
      font-size: 13px;
      padding: 0 2px;
      color: #909399;
      line-height: 1;
      transition: color 0.15s;
      &:hover { color: #409eff; }
      &.playing { color: #f56c6c; }
    }
  }

  .cursor-blink {
    animation: blink 1s step-end infinite;
    font-size: 16px;
    color: #667eea;
  }
}

@keyframes blink {
  50% { opacity: 0; }
}

.input-area {
  background: white;
  border-top: 1px solid #ebeef5;
  padding: 12px 20px 16px;

  .input-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;

    .perf-badge {
      margin-left: auto;
      font-size: 11px;
      color: #909399;
      background: #f5f7fa;
      border-radius: 4px;
      padding: 2px 8px;
      font-family: monospace;
    }
  }

  .input-row {
    display: flex;
    gap: 10px;
    align-items: flex-end;

    .el-textarea { flex: 1; }

    .send-btn {
      height: 72px;
      padding: 0 20px;
    }
  }
}
</style>
