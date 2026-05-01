<template>
  <div class="podcast-page">
    <div class="page-header">
      <h1>🎙️ 播客语音合成</h1>
      <p>多说话人对话语音合成，支持方言和声音克隆</p>
    </div>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover" class="compose-card">
          <template #header>
            <div class="card-header-title">✏️ 对话文本</div>
          </template>

          <el-form label-position="top">
            <el-form-item label="对话内容">
              <el-input
                v-model="form.target_text"
                type="textarea"
                :rows="6"
                placeholder="[S1]你好，欢迎来到我们的播客节目！&#10;[S2]谢谢邀请，很高兴来到这里。&#10;[S1]今天我们聊聊AI技术的最新发展..."
                maxlength="10000"
                show-word-limit
                resize="vertical"
              />
            </el-form-item>

            <!-- 说话人1 -->
            <el-divider content-position="left">说话人 1（必填）</el-divider>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="参考音频">
                  <el-upload
                    :auto-upload="false"
                    :limit="1"
                    accept="audio/*"
                    :on-change="(f: any) => form.spk1_audio = f.raw"
                    :on-remove="() => form.spk1_audio = null"
                  >
                    <el-button type="primary" plain>选择音频</el-button>
                  </el-upload>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="参考文本">
                  <el-input v-model="form.spk1_prompt_text" placeholder="对应参考音频的文字内容" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="方言提示（可选）">
              <el-input v-model="form.spk1_dialect" placeholder='如 "<|Sichuan|>四川话内容"，留空则使用普通话' />
            </el-form-item>

            <!-- 说话人2 -->
            <el-divider content-position="left">说话人 2（可选，独白可不填）</el-divider>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="参考音频">
                  <el-upload
                    :auto-upload="false"
                    :limit="1"
                    accept="audio/*"
                    :on-change="(f: any) => form.spk2_audio = f.raw"
                    :on-remove="() => form.spk2_audio = null"
                  >
                    <el-button plain>选择音频</el-button>
                  </el-upload>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="参考文本">
                  <el-input v-model="form.spk2_prompt_text" placeholder="说话人2 参考文本" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="方言提示（可选）">
              <el-input v-model="form.spk2_dialect" placeholder="说话人2 方言提示" />
            </el-form-item>

            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="随机种子">
                  <el-input-number v-model="form.seed" :min="0" :max="999999" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="16" style="display: flex; align-items: flex-end; padding-bottom: 18px">
                <el-button type="primary" size="large" :loading="submitting" @click="handleSubmit" style="width: 100%">
                  开始合成
                </el-button>
              </el-col>
            </el-row>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：结果 + 历史 -->
      <el-col :xs="24" :lg="10">
        <!-- 当前任务 -->
        <el-card v-if="currentTask" shadow="hover" class="result-card">
          <template #header>
            <div class="card-header-title">🎧 合成结果</div>
          </template>
          <div v-if="currentTask.status === 'completed' && currentTask.output_url" class="result-area">
            <audio :src="currentTask.output_url" controls style="width: 100%" />
            <el-button type="primary" plain @click="downloadFile(currentTask.output_url)" style="margin-top: 12px">
              下载音频
            </el-button>
          </div>
          <div v-else-if="currentTask.status === 'failed'" class="result-area">
            <el-alert type="error" :title="currentTask.error_message || '合成失败'" show-icon :closable="false" />
          </div>
          <div v-else class="result-area polling-status">
            <el-icon class="is-loading" :size="24"><Loading /></el-icon>
            <span>{{ currentTask.status === 'processing' ? '合成中...' : '排队中...' }}</span>
          </div>
        </el-card>

        <!-- 历史任务 -->
        <el-card shadow="hover" style="margin-top: 16px">
          <template #header>
            <div class="card-header-title">📋 历史任务</div>
          </template>
          <el-table :data="tasks" stripe size="small" max-height="400">
            <el-table-column prop="id" label="ID" width="60" />
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
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { podcastSynthesize, getSoulTasks, getSoulTask } from '@/api/soul'
import type { SoulTaskDetail } from '@/types/api'

const form = reactive({
  target_text: '',
  spk1_audio: null as File | null,
  spk1_prompt_text: '',
  spk1_dialect: '',
  spk2_audio: null as File | null,
  spk2_prompt_text: '',
  spk2_dialect: '',
  seed: 1988,
})

const submitting = ref(false)
const currentTask = ref<SoulTaskDetail | null>(null)
const tasks = ref<SoulTaskDetail[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => { loadTasks() })
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

async function loadTasks() {
  try { tasks.value = await getSoulTasks('podcast') } catch {}
}

async function handleSubmit() {
  if (!form.target_text.trim()) return ElMessage.warning('请输入对话文本')
  if (!form.spk1_audio) return ElMessage.warning('请上传说话人1参考音频')

  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('target_text', form.target_text)
    fd.append('spk1_prompt_audio', form.spk1_audio)
    fd.append('spk1_prompt_text', form.spk1_prompt_text)
    fd.append('spk1_dialect_prompt_text', form.spk1_dialect)
    if (form.spk2_audio) {
      fd.append('spk2_prompt_audio', form.spk2_audio)
      fd.append('spk2_prompt_text', form.spk2_prompt_text)
      fd.append('spk2_dialect_prompt_text', form.spk2_dialect)
    }
    fd.append('seed', String(form.seed))

    const res = await podcastSynthesize(fd)
    ElMessage.success('任务已提交')
    startPolling(res.task_id)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

function startPolling(taskId: number) {
  if (pollTimer) clearInterval(pollTimer)
  currentTask.value = { id: taskId, status: 'pending' } as SoulTaskDetail
  pollTimer = setInterval(async () => {
    try {
      const t = await getSoulTask('podcast', taskId)
      currentTask.value = t
      if (t.status === 'completed' || t.status === 'failed') {
        clearInterval(pollTimer!)
        pollTimer = null
        loadTasks()
      }
    } catch {}
  }, 2000)
}

function downloadFile(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  a.click()
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
.podcast-page {
  .page-header {
    margin-bottom: 24px;
    h1 { margin: 0 0 8px; font-size: 24px; }
    p { margin: 0; color: #909399; }
  }
  .card-header-title { font-weight: 600; font-size: 15px; }
  .result-area { text-align: center; padding: 16px 0; }
  .polling-status { display: flex; align-items: center; justify-content: center; gap: 8px; color: #e6a23c; font-size: 15px; }
}
</style>
