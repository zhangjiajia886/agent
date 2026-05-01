<template>
  <div class="tts-page">
    <div class="page-header">
      <h1>🎙️ 语音合成 TTS</h1>
      <p>将文字转换为自然流畅的语音，支持多种声音和格式</p>
    </div>

    <el-row :gutter="20">
      <!-- 左侧：合成配置 -->
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover" class="compose-card">
          <template #header>
            <div class="card-header-title">✏️ 文本输入</div>
          </template>

          <el-form :model="form" label-position="top">
            <el-form-item label="合成文本">
              <el-input
                v-model="form.text"
                type="textarea"
                :rows="8"
                placeholder="请输入要转换为语音的文字内容..."
                maxlength="5000"
                show-word-limit
                resize="none"
              />
            </el-form-item>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="声音模型">
                  <el-select v-model="form.voice_model_id" placeholder="使用默认声音" clearable style="width: 100%">
                    <el-option
                      v-for="m in voiceModels"
                      :key="m.id"
                      :label="m.title"
                      :value="m.id"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="音频格式">
                  <el-select v-model="form.format" style="width: 100%">
                    <el-option label="WAV（无损，推荐）" value="wav" />
                    <el-option label="MP3（压缩）" value="mp3" />
                    <el-option label="OPUS（小体积）" value="opus" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="延迟模式">
                  <el-select v-model="form.latency" style="width: 100%">
                    <el-option label="🏆 高质量（3~5s）" value="normal" />
                    <el-option label="⚡ 均衡（1~2s）推荐" value="balanced" />
                    <el-option label="🚀 极速（&lt;1s）" value="low" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12" v-if="form.format === 'mp3'">
                <el-form-item label="MP3 码率">
                  <el-select v-model="form.mp3_bitrate" style="width: 100%">
                    <el-option label="64 kbps" :value="64" />
                    <el-option label="128 kbps（推荐）" :value="128" />
                    <el-option label="192 kbps（高质量）" :value="192" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="TTS 引擎">
                  <el-select v-model="form.tts_model" style="width: 100%">
                    <el-option label="S2-Pro — 情感标记 [xxx]（推荐）" value="s2-pro" />
                    <el-option label="S2 — 标准" value="s2" />
                    <el-option label="S1 — 情感标记 (xxx)" value="s1" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Normalize 音量均衡">
                  <el-switch v-model="form.normalize" active-text="开" inactive-text="关" />
                  <div style="font-size:12px;color:#909399;margin-top:4px">自动调整输出音量到标准电平</div>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="语气提示词">
              <el-input
                v-model="form.style_prompt"
                placeholder="例如：speaking calmly and evenly, gentle tone, soft start（留空则不生效）"
                clearable
              />
              <div style="font-size:12px;color:#909399;margin-top:4px">
                用英文描述说话风格，会作为 S2-Pro 指令拼到文本头部，例如 <code>speaking slowly and gently</code>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="synthesizing"
                :disabled="!form.text.trim()"
                :icon="Microphone"
                @click="handleSynthesize"
              >
                {{ synthesizing ? '合成中...' : '开始合成' }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：播放器与结果 -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="hover" class="player-card" v-if="currentTask">
          <template #header>
            <div class="card-header-title">🔊 合成结果</div>
          </template>

          <div class="result-status">
            <el-tag :type="statusTagType(currentTask.status)" size="large">
              {{ statusLabel(currentTask.status) }}
            </el-tag>
            <span v-if="currentTask.duration" class="duration">{{ currentTask.duration.toFixed(1) }}s</span>
          </div>

          <div v-if="currentTask.status === 'completed' && currentTask.audio_url" class="audio-section">
            <div class="audio-player-wrapper">
              <div class="audio-info">
                <el-icon :size="32"><Headset /></el-icon>
                <div>
                  <div class="audio-title">合成音频</div>
                  <div class="audio-meta">{{ currentTask.format }} · {{ currentTask.duration?.toFixed(1) }}s</div>
                </div>
              </div>
              <audio
                ref="audioRef"
                :src="currentTask.audio_url"
                controls
                style="width: 100%; margin-top: 12px;"
              />
            </div>
            <el-button type="success" :icon="Download" @click="downloadAudio" style="margin-top: 12px; width: 100%">
              下载音频
            </el-button>
          </div>

          <div v-if="currentTask.status === 'failed'" class="error-section">
            <el-alert type="error" :description="currentTask.error_message || '合成失败'" show-icon :closable="false" />
          </div>

          <div v-if="currentTask.status === 'processing' || currentTask.status === 'pending'" class="processing-section">
            <el-progress :percentage="progressPercent" :striped="true" :striped-flow="true" :duration="10" />
            <p style="color: #909399; font-size: 13px; margin-top: 8px; text-align: center;">正在合成，请稍候...</p>
          </div>
        </el-card>

        <el-card shadow="hover" v-else class="hint-card">
          <div class="hint-content">
            <img src="https://api.dicebear.com/7.x/icons/svg?seed=microphone&icon=mic" alt="mic" width="80" style="opacity: 0.3;" />
            <p>在左侧输入文字，点击「开始合成」生成语音</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 情感标记调试测试 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header-title">🧪 情感标记测试（调试用）</div>
      </template>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="14">
          <el-form-item label="测试文本">
            <el-input
              v-model="emotionTestForm.text"
              type="textarea"
              :rows="4"
              placeholder="输入带情感标记的文本"
            />
          </el-form-item>
        </el-col>

        <el-col :xs="24" :lg="10">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="TTS 模型">
                <el-select v-model="emotionTestForm.model" style="width:100%">
                  <el-option label="S2-Pro（方括号 [xxx]）" value="s2-pro" />
                  <el-option label="S1（圆括号 (xxx)）" value="s1" />
                  <el-option label="S2（平衡）" value="s2" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="音色模型">
                <el-select v-model="emotionTestForm.reference_id" placeholder="默认音色" clearable style="width:100%">
                  <el-option
                    v-for="m in voiceModels"
                    :key="m.fish_model_id"
                    :label="m.title"
                    :value="m.fish_model_id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="延迟模式">
                <el-select v-model="emotionTestForm.latency" style="width:100%">
                  <el-option label="高质量" value="normal" />
                  <el-option label="均衡（推荐）" value="balanced" />
                  <el-option label="极速" value="low" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Normalize">
                <el-switch v-model="emotionTestForm.normalize" active-text="开" inactive-text="关" />
              </el-form-item>
            </el-col>
          </el-row>

          <div style="font-size:12px;color:#909399;margin-bottom:8px">
            S2-Pro：<code>[laugh]</code> <code>[sigh]</code> <code>[exhale]</code> <code>[whisper]</code><br/>
            S1：<code>(laughing)</code> <code>(sighing)</code> <code>(sad)</code>
          </div>
          <el-button type="primary" :loading="emotionTesting" @click="handleEmotionTest" style="width:100%">
            ▶ 播放测试
          </el-button>
        </el-col>
      </el-row>

      <div v-if="emotionAudioUrl" style="margin-top:12px">
        <audio :src="emotionAudioUrl" controls autoplay style="width:100%" />
      </div>
      <el-alert v-if="emotionTestError" :description="emotionTestError" type="error" show-icon :closable="false" style="margin-top:10px" />
    </el-card>

    <!-- 历史记录 -->
    <el-card shadow="hover" class="history-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header-title">📋 合成历史</div>
      </template>
      <el-table :data="tasks" stripe size="small" v-loading="tasksLoading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="text" label="文本内容" show-overflow-tooltip min-width="200" />
        <el-table-column prop="format" label="格式" width="70" />
        <el-table-column prop="latency" label="模式" width="80" />
        <el-table-column label="时长" width="70">
          <template #default="{ row }">
            {{ row.duration ? row.duration.toFixed(1) + 's' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.audio_url" text type="primary" size="small" @click="playHistoryAudio(row)">
              播放
            </el-button>
            <el-button text type="success" size="small" @click="reuseTask(row)">复用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Microphone, Headset, Download } from '@element-plus/icons-vue'
import { synthesize, getTasks, getTask, testEmotion } from '@/api/tts'
import { getModels } from '@/api/voice'
import type { TTSTask, VoiceModel } from '@/types/api'

const route = useRoute()
const audioRef = ref<HTMLAudioElement>()
const synthesizing = ref(false)
const tasksLoading = ref(false)
const tasks = ref<TTSTask[]>([])
const voiceModels = ref<VoiceModel[]>([])
const currentTask = ref<TTSTask | null>(null)
const progressPercent = ref(30)
let pollTimer: ReturnType<typeof setInterval> | null = null

const form = reactive({
  text: '',
  voice_model_id: undefined as number | undefined,
  format: 'wav' as 'mp3' | 'wav' | 'pcm' | 'opus',
  latency: 'balanced' as 'normal' | 'balanced' | 'low',
  mp3_bitrate: 128,
  tts_model: 's2-pro' as 's1' | 's2' | 's2-pro',
  normalize: true,
  style_prompt: '',
})

function statusTagType(status: string) {
  const map: Record<string, string> = { completed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = { completed: '已完成', failed: '失败', processing: '合成中', pending: '等待中' }
  return map[status] || status
}

async function handleSynthesize() {
  if (!form.text.trim()) return
  synthesizing.value = true
  progressPercent.value = 20

  try {
    const res = await synthesize({
      text: form.text,
      voice_model_id: form.voice_model_id,
      format: form.format,
      latency: form.latency,
      mp3_bitrate: form.mp3_bitrate,
      tts_model: form.tts_model,
      normalize: form.normalize,
      style_prompt: form.style_prompt || undefined,
    })

    currentTask.value = { id: res.task_id, status: res.status as TTSTask['status'], text: form.text, format: form.format, latency: form.latency, streaming: false, audio_url: null, audio_size: null, duration: null, error_message: null, cost_credits: null, created_at: new Date().toISOString(), completed_at: null }
    startPolling(res.task_id)
    await loadTasks()
  } catch {
    ElMessage.error('合成请求失败')
  } finally {
    synthesizing.value = false
  }
}

function startPolling(taskId: number) {
  progressPercent.value = 30
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const task = await getTask(taskId)
      currentTask.value = task
      if (progressPercent.value < 90) progressPercent.value += 10
      if (task.status === 'completed' || task.status === 'failed') {
        clearInterval(pollTimer!)
        progressPercent.value = 100
        await loadTasks()
        if (task.status === 'completed') ElMessage.success('语音合成成功！')
        else ElMessage.error('合成失败：' + (task.error_message || '未知错误'))
      }
    } catch {
      clearInterval(pollTimer!)
    }
  }, 2000)
}

function downloadAudio() {
  if (!currentTask.value?.audio_url) return
  const a = document.createElement('a')
  a.href = currentTask.value.audio_url
  a.download = `tts_${currentTask.value.id}.${currentTask.value.format}`
  a.click()
}

function playHistoryAudio(task: TTSTask) {
  currentTask.value = task
}

function reuseTask(task: TTSTask) {
  form.text = task.text
  form.format = task.format as typeof form.format
  form.latency = task.latency as typeof form.latency
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    tasks.value = await getTasks(0, 20)
  } finally {
    tasksLoading.value = false
  }
}

const emotionTestForm = reactive({
  text: '[laugh] 哈哈哈，真的好笑！[sigh] 唉，算了。',
  model: 's2-pro',
  reference_id: '',
  latency: 'balanced',
  normalize: true,
})
const emotionTesting = ref(false)
const emotionAudioUrl = ref('')
const emotionTestError = ref('')

async function handleEmotionTest() {
  if (!emotionTestForm.text.trim()) return
  emotionTesting.value = true
  emotionTestError.value = ''
  if (emotionAudioUrl.value) URL.revokeObjectURL(emotionAudioUrl.value)
  emotionAudioUrl.value = ''
  try {
    const buf = await testEmotion({
      text: emotionTestForm.text,
      model: emotionTestForm.model,
      reference_id: emotionTestForm.reference_id || undefined,
      latency: emotionTestForm.latency,
      normalize: emotionTestForm.normalize,
    })
    const blob = new Blob([buf], { type: 'audio/mpeg' })
    emotionAudioUrl.value = URL.createObjectURL(blob)
  } catch (e: any) {
    emotionTestError.value = e?.message || '请求失败'
  } finally {
    emotionTesting.value = false
  }
}

onMounted(async () => {
  if (route.query.text) form.text = route.query.text as string
  await loadTasks()
  try {
    const res = await getModels(0, 100)
    voiceModels.value = res.items
  } catch {}
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped lang="scss">
.tts-page {
  .compose-card, .player-card { margin-bottom: 0; }

  .card-header-title {
    font-size: 15px;
    font-weight: 600;
  }

  .result-status {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    .duration {
      font-size: 13px;
      color: #909399;
    }
  }

  .audio-player-wrapper {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    padding: 20px;
    color: white;

    .audio-info {
      display: flex;
      align-items: center;
      gap: 12px;

      .audio-title { font-size: 15px; font-weight: 600; }
      .audio-meta { font-size: 12px; opacity: 0.8; margin-top: 2px; }
    }
  }

  .hint-card {
    .hint-content {
      text-align: center;
      padding: 40px 20px;
      color: #909399;

      p { margin-top: 16px; font-size: 14px; }
    }
  }
}
</style>
