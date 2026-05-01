<template>
  <div class="singing-page">
    <div class="page-header">
      <h1>🎵 AI 歌声合成</h1>
      <p>歌声合成 (SVS) 和歌声转换 (SVC)，支持音色克隆</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- ===== SVS 标签页 ===== -->
      <el-tab-pane label="歌声合成 SVS" name="svs">
        <el-form label-position="top">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="参考歌手音频（目标音色，max 30s）">
                <div style="display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap">
                  <el-upload :auto-upload="false" :limit="1" accept="audio/*"
                    :on-change="(f: any) => { svsForm.prompt_audio = f.raw; delete recordedAudios['svs_prompt'] }"
                    :on-remove="() => { svsForm.prompt_audio = null; delete recordedAudios['svs_prompt'] }">
                    <el-button type="primary" plain>选择音频</el-button>
                  </el-upload>
                  <el-button v-if="recordingTarget !== 'svs_prompt'" :icon="Microphone" circle
                    title="麦克风录音" @click="startRecording('svs_prompt')" />
                  <template v-else>
                    <el-button type="danger" :icon="VideoPause" circle @click="stopRecording" />
                    <span style="color:#f56c6c;font-size:13px;line-height:32px">{{ formatRecordTime(recordingDuration) }}</span>
                  </template>
                </div>
                <audio v-if="recordedAudios['svs_prompt']" :src="recordedAudios['svs_prompt']" controls
                  style="width:100%;height:36px;margin-top:6px" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="旋律/歌词来源音频（max 60s）">
                <div style="display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap">
                  <el-upload :auto-upload="false" :limit="1" accept="audio/*"
                    :on-change="(f: any) => { svsForm.target_audio = f.raw; delete recordedAudios['svs_target'] }"
                    :on-remove="() => { svsForm.target_audio = null; delete recordedAudios['svs_target'] }">
                    <el-button type="primary" plain>选择音频</el-button>
                  </el-upload>
                  <el-button v-if="recordingTarget !== 'svs_target'" :icon="Microphone" circle
                    title="麦克风录音" @click="startRecording('svs_target')" />
                  <template v-else>
                    <el-button type="danger" :icon="VideoPause" circle @click="stopRecording" />
                    <span style="color:#f56c6c;font-size:13px;line-height:32px">{{ formatRecordTime(recordingDuration) }}</span>
                  </template>
                </div>
                <audio v-if="recordedAudios['svs_target']" :src="recordedAudios['svs_target']" controls
                  style="width:100%;height:36px;margin-top:6px" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-collapse>
            <el-collapse-item title="高级参数">
              <el-row :gutter="16">
                <el-col :span="8">
                  <el-form-item label="控制模式">
                    <el-radio-group v-model="svsForm.control">
                      <el-radio value="melody">Melody</el-radio>
                      <el-radio value="score">Score</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="自动音高偏移">
                    <el-switch v-model="svsForm.auto_shift" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="手动音高偏移">
                    <el-input-number v-model="svsForm.pitch_shift" :min="-36" :max="36" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="8">
                  <el-form-item label="随机种子">
                    <el-input-number v-model="svsForm.seed" :min="0" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="Prompt 歌词语言">
                    <el-select v-model="svsForm.prompt_lyric_lang" style="width: 100%">
                      <el-option label="Mandarin" value="Mandarin" />
                      <el-option label="Cantonese" value="Cantonese" />
                      <el-option label="English" value="English" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="Target 歌词语言">
                    <el-select v-model="svsForm.target_lyric_lang" style="width: 100%">
                      <el-option label="Mandarin" value="Mandarin" />
                      <el-option label="Cantonese" value="Cantonese" />
                      <el-option label="English" value="English" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="8">
                  <el-form-item label="Prompt 声伴分离">
                    <el-switch v-model="svsForm.prompt_vocal_sep" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="Target 声伴分离">
                    <el-switch v-model="svsForm.target_vocal_sep" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="Prompt Metadata（可选 JSON）">
                    <el-upload :auto-upload="false" :limit="1" accept=".json"
                      :on-change="(f: any) => svsForm.prompt_metadata = f.raw"
                      :on-remove="() => svsForm.prompt_metadata = null">
                      <el-button plain size="small">上传 JSON</el-button>
                    </el-upload>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="Target Metadata（可选 JSON）">
                    <el-upload :auto-upload="false" :limit="1" accept=".json"
                      :on-change="(f: any) => svsForm.target_metadata = f.raw"
                      :on-remove="() => svsForm.target_metadata = null">
                      <el-button plain size="small">上传 JSON</el-button>
                    </el-upload>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-collapse-item>
          </el-collapse>

          <div style="margin-top: 16px; display: flex; gap: 12px">
            <el-button type="primary" :loading="svsSubmitting" @click="handleSvsSubmit" style="flex: 1">
              开始合成
            </el-button>
            <el-button :loading="transcribing" @click="handleTranscribe" style="flex: 1">
              转写歌词
            </el-button>
            <el-button @click="openMidiEditor">MIDI Editor</el-button>
          </div>
        </el-form>
      </el-tab-pane>

      <!-- ===== SVC 标签页 ===== -->
      <el-tab-pane label="歌声转换 SVC" name="svc">
        <el-form label-position="top">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="目标音色参考音频">
                <div style="display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap">
                  <el-upload :auto-upload="false" :limit="1" accept="audio/*"
                    :on-change="(f: any) => { svcForm.prompt_audio = f.raw; delete recordedAudios['svc_prompt'] }"
                    :on-remove="() => { svcForm.prompt_audio = null; delete recordedAudios['svc_prompt'] }">
                    <el-button type="primary" plain>选择音频</el-button>
                  </el-upload>
                  <el-button v-if="recordingTarget !== 'svc_prompt'" :icon="Microphone" circle
                    title="麦克风录音" @click="startRecording('svc_prompt')" />
                  <template v-else>
                    <el-button type="danger" :icon="VideoPause" circle @click="stopRecording" />
                    <span style="color:#f56c6c;font-size:13px;line-height:32px">{{ formatRecordTime(recordingDuration) }}</span>
                  </template>
                </div>
                <audio v-if="recordedAudios['svc_prompt']" :src="recordedAudios['svc_prompt']" controls
                  style="width:100%;height:36px;margin-top:6px" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="待转换的源歌曲音频">
                <div style="display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap">
                  <el-upload :auto-upload="false" :limit="1" accept="audio/*"
                    :on-change="(f: any) => { svcForm.target_audio = f.raw; delete recordedAudios['svc_target'] }"
                    :on-remove="() => { svcForm.target_audio = null; delete recordedAudios['svc_target'] }">
                    <el-button type="primary" plain>选择音频</el-button>
                  </el-upload>
                  <el-button v-if="recordingTarget !== 'svc_target'" :icon="Microphone" circle
                    title="麦克风录音" @click="startRecording('svc_target')" />
                  <template v-else>
                    <el-button type="danger" :icon="VideoPause" circle @click="stopRecording" />
                    <span style="color:#f56c6c;font-size:13px;line-height:32px">{{ formatRecordTime(recordingDuration) }}</span>
                  </template>
                </div>
                <audio v-if="recordedAudios['svc_target']" :src="recordedAudios['svc_target']" controls
                  style="width:100%;height:36px;margin-top:6px" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-collapse>
            <el-collapse-item title="高级参数">
              <el-row :gutter="16">
                <el-col :span="6">
                  <el-form-item label="声伴分离(Prompt)">
                    <el-switch v-model="svcForm.prompt_vocal_sep" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="声伴分离(Target)">
                    <el-switch v-model="svcForm.target_vocal_sep" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="自动音高偏移">
                    <el-switch v-model="svcForm.auto_shift" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="自动混合伴奏">
                    <el-switch v-model="svcForm.auto_mix_acc" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="6">
                  <el-form-item label="手动音高偏移">
                    <el-input-number v-model="svcForm.pitch_shift" :min="-36" :max="36" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="扩散步数">
                    <el-input-number v-model="svcForm.n_step" :min="1" :max="200" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="CFG Scale">
                    <el-input-number v-model="svcForm.cfg" :min="0" :max="10" :step="0.1" :precision="1" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="随机种子">
                    <el-input-number v-model="svcForm.seed" :min="0" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="FP16 推理">
                <el-switch v-model="svcForm.use_fp16" />
              </el-form-item>
            </el-collapse-item>
          </el-collapse>

          <el-button type="primary" size="large" :loading="svcSubmitting" @click="handleSvcSubmit" style="width: 100%; margin-top: 16px">
            开始转换
          </el-button>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <!-- 结果区域 -->
    <el-card v-if="currentTask" shadow="hover" style="margin-top: 20px">
      <template #header>
        <div style="font-weight: 600">🎧 处理结果</div>
      </template>
      <div v-if="currentTask.status === 'completed' && currentTask.output_url" style="text-align: center">
        <audio :src="currentTask.output_url" controls style="width: 100%" />
        <el-button type="primary" plain @click="downloadFile(currentTask.output_url)" style="margin-top: 12px">
          下载音频
        </el-button>
      </div>
      <div v-else-if="currentTask.status === 'failed'" style="text-align: center">
        <el-alert type="error" :title="currentTask.error_message || '处理失败'" show-icon :closable="false" />
      </div>
      <div v-else style="text-align: center; display: flex; align-items: center; justify-content: center; gap: 8px; color: #e6a23c; padding: 16px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <span>{{ currentTask.status === 'processing' ? '处理中...' : '排队中...' }}</span>
      </div>
    </el-card>

    <!-- 转写结果 -->
    <el-card v-if="transcribeResult" shadow="hover" style="margin-top: 20px">
      <template #header>
        <div style="font-weight: 600">📝 转写结果</div>
      </template>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-button v-if="transcribeResult.prompt_metadata" @click="downloadBase64('prompt_metadata.json', transcribeResult.prompt_metadata)">
            下载 Prompt Metadata
          </el-button>
          <span v-else style="color: #909399">无 Prompt Metadata</span>
        </el-col>
        <el-col :span="12">
          <el-button v-if="transcribeResult.target_metadata" @click="downloadBase64('target_metadata.json', transcribeResult.target_metadata)">
            下载 Target Metadata
          </el-button>
          <span v-else style="color: #909399">无 Target Metadata</span>
        </el-col>
      </el-row>
    </el-card>

    <!-- 历史任务 -->
    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <div style="font-weight: 600">📋 历史任务</div>
      </template>
      <el-table :data="tasks" stripe size="small" max-height="350">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">{{ row.task_type === 'singing_svs' ? 'SVS' : 'SVC' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button v-if="row.status === 'completed' && row.output_url" text type="primary" size="small" @click="downloadFile(row.output_url)">
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Loading, Microphone, VideoPause } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { singingSvs, singingSvc, singingTranscribe, getSoulTasks, getSoulTask } from '@/api/soul'
import type { SoulTaskDetail, TranscribeResult } from '@/types/api'

const MIDI_EDITOR_URL = 'https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor'

const activeTab = ref('svs')
const currentTask = ref<SoulTaskDetail | null>(null)
const tasks = ref<SoulTaskDetail[]>([])
const transcribeResult = ref<TranscribeResult | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const svsForm = reactive({
  prompt_audio: null as File | null,
  target_audio: null as File | null,
  control: 'melody',
  auto_shift: true,
  pitch_shift: 0,
  seed: 12306,
  prompt_lyric_lang: 'Mandarin',
  target_lyric_lang: 'Mandarin',
  prompt_vocal_sep: false,
  target_vocal_sep: true,
  prompt_metadata: null as File | null,
  target_metadata: null as File | null,
})

const svcForm = reactive({
  prompt_audio: null as File | null,
  target_audio: null as File | null,
  prompt_vocal_sep: false,
  target_vocal_sep: true,
  auto_shift: true,
  auto_mix_acc: true,
  pitch_shift: 0,
  n_step: 32,
  cfg: 1.0,
  use_fp16: true,
  seed: 42,
})

const svsSubmitting = ref(false)
const svcSubmitting = ref(false)
const transcribing = ref(false)

const recordingTarget = ref<string | null>(null)
const recordingDuration = ref(0)
const recordedAudios = reactive<Record<string, string>>({})
let mediaRecorder: MediaRecorder | null = null
let recordedChunks: BlobPart[] = []
let recordTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => { loadTasks() })
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (recordTimer) clearInterval(recordTimer)
  Object.values(recordedAudios).forEach(url => URL.revokeObjectURL(url))
})

async function startRecording(target: string) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    recordedChunks = []
    recordingTarget.value = target
    recordingDuration.value = 0
    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm'
      : MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/ogg'
    const ext = mimeType.includes('webm') ? 'webm' : mimeType.includes('mp4') ? 'm4a' : 'ogg'
    mediaRecorder = new MediaRecorder(stream, { mimeType })
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordedChunks.push(e.data) }
    mediaRecorder.onstop = () => {
      const blob = new Blob(recordedChunks, { type: mimeType })
      const file = new File([blob], `录音_${Date.now()}.${ext}`, { type: mimeType })
      if (target === 'svs_prompt') svsForm.prompt_audio = file
      else if (target === 'svs_target') svsForm.target_audio = file
      else if (target === 'svc_prompt') svcForm.prompt_audio = file
      else if (target === 'svc_target') svcForm.target_audio = file
      const prev = recordedAudios[target]
      if (prev) URL.revokeObjectURL(prev)
      recordedAudios[target] = URL.createObjectURL(blob)
      stream.getTracks().forEach(t => t.stop())
      recordingTarget.value = null
      if (recordTimer) { clearInterval(recordTimer); recordTimer = null }
    }
    mediaRecorder.start(100)
    recordTimer = setInterval(() => { recordingDuration.value++ }, 1000)
  } catch {
    ElMessage.error('无法访问麦克风，请检查浏览器权限')
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop()
}

function formatRecordTime(s: number) {
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`
}

async function loadTasks() {
  try { tasks.value = await getSoulTasks('singing') } catch {}
}

async function handleSvsSubmit() {
  if (!svsForm.prompt_audio || !svsForm.target_audio) return ElMessage.warning('请上传两段音频')
  svsSubmitting.value = true
  try {
    const fd = new FormData()
    fd.append('prompt_audio', svsForm.prompt_audio)
    fd.append('target_audio', svsForm.target_audio)
    fd.append('control', svsForm.control)
    fd.append('auto_shift', String(svsForm.auto_shift))
    fd.append('pitch_shift', String(svsForm.pitch_shift))
    fd.append('seed', String(svsForm.seed))
    fd.append('prompt_lyric_lang', svsForm.prompt_lyric_lang)
    fd.append('target_lyric_lang', svsForm.target_lyric_lang)
    fd.append('prompt_vocal_sep', String(svsForm.prompt_vocal_sep))
    fd.append('target_vocal_sep', String(svsForm.target_vocal_sep))
    if (svsForm.prompt_metadata) fd.append('prompt_metadata', svsForm.prompt_metadata)
    if (svsForm.target_metadata) fd.append('target_metadata', svsForm.target_metadata)

    const res = await singingSvs(fd)
    ElMessage.success('SVS 任务已提交')
    startPolling(res.task_id)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally { svsSubmitting.value = false }
}

async function handleSvcSubmit() {
  if (!svcForm.prompt_audio || !svcForm.target_audio) return ElMessage.warning('请上传两段音频')
  svcSubmitting.value = true
  try {
    const fd = new FormData()
    fd.append('prompt_audio', svcForm.prompt_audio)
    fd.append('target_audio', svcForm.target_audio)
    fd.append('prompt_vocal_sep', String(svcForm.prompt_vocal_sep))
    fd.append('target_vocal_sep', String(svcForm.target_vocal_sep))
    fd.append('auto_shift', String(svcForm.auto_shift))
    fd.append('auto_mix_acc', String(svcForm.auto_mix_acc))
    fd.append('pitch_shift', String(svcForm.pitch_shift))
    fd.append('n_step', String(svcForm.n_step))
    fd.append('cfg', String(svcForm.cfg))
    fd.append('use_fp16', String(svcForm.use_fp16))
    fd.append('seed', String(svcForm.seed))

    const res = await singingSvc(fd)
    ElMessage.success('SVC 任务已提交')
    startPolling(res.task_id)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally { svcSubmitting.value = false }
}

async function handleTranscribe() {
  if (!svsForm.prompt_audio || !svsForm.target_audio) return ElMessage.warning('请先上传两段音频')
  transcribing.value = true
  transcribeResult.value = null
  try {
    const fd = new FormData()
    fd.append('prompt_audio', svsForm.prompt_audio)
    fd.append('target_audio', svsForm.target_audio)
    fd.append('prompt_lyric_lang', svsForm.prompt_lyric_lang)
    fd.append('target_lyric_lang', svsForm.target_lyric_lang)
    fd.append('prompt_vocal_sep', String(svsForm.prompt_vocal_sep))
    fd.append('target_vocal_sep', String(svsForm.target_vocal_sep))

    transcribeResult.value = await singingTranscribe(fd)
    ElMessage.success('转写完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '转写失败')
  } finally { transcribing.value = false }
}

function startPolling(taskId: number) {
  if (pollTimer) clearInterval(pollTimer)
  currentTask.value = { id: taskId, status: 'pending' } as SoulTaskDetail
  pollTimer = setInterval(async () => {
    try {
      const t = await getSoulTask('singing', taskId)
      currentTask.value = t
      if (t.status === 'completed' || t.status === 'failed') {
        clearInterval(pollTimer!)
        pollTimer = null
        loadTasks()
      }
    } catch {}
  }, 2000)
}

function openMidiEditor() { window.open(MIDI_EDITOR_URL, '_blank') }

function downloadFile(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  a.click()
}

function downloadBase64(filename: string, b64: string) {
  const raw = atob(b64)
  const arr = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i)
  const blob = new Blob([arr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function statusType(s: string) {
  return { completed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }[s] as any || 'info'
}
function statusText(s: string) {
  return { completed: '完成', failed: '失败', processing: '处理中', pending: '排队中' }[s] || s
}
function formatTime(t: string) {
  return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped lang="scss">
.singing-page {
  .page-header {
    margin-bottom: 24px;
    h1 { margin: 0 0 8px; font-size: 24px; }
    p { margin: 0; color: #909399; }
  }
}
</style>
