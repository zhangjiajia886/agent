<template>
  <div class="dh-page">
    <div class="page-header">
      <h1>👤 数字人视频生成</h1>
      <p>上传人脸图片和驱动音频，生成口型同步的数字人视频</p>
    </div>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header>
            <div style="font-weight: 600">📤 输入配置</div>
          </template>

          <el-form label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="参考人脸图片">
                  <el-upload
                    :auto-upload="false"
                    :limit="1"
                    accept="image/*"
                    list-type="picture-card"
                    :on-change="handleImageChange"
                    :on-remove="() => { form.image = null; imagePreview = '' }"
                  >
                    <el-icon :size="28"><Plus /></el-icon>
                  </el-upload>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="驱动音频">
                  <el-upload
                    :auto-upload="false"
                    :limit="1"
                    accept="audio/*"
                    :on-change="(f: any) => form.audio = f.raw"
                    :on-remove="() => form.audio = null"
                  >
                    <el-button type="primary" plain>选择音频</el-button>
                  </el-upload>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="模型类型">
                  <el-radio-group v-model="form.model_type">
                    <el-radio value="lite">Lite（快速）</el-radio>
                    <el-radio value="pro">Pro（高质量）</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="随机种子">
                  <el-input-number v-model="form.seed" :min="0" :max="999999" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="自动裁剪人脸">
                  <el-switch v-model="form.use_face_crop" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-button type="primary" size="large" :loading="submitting" @click="handleSubmit" style="width: 100%">
              生成视频
            </el-button>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <!-- 当前任务结果 -->
        <el-card v-if="currentTask" shadow="hover">
          <template #header>
            <div style="font-weight: 600">🎬 生成结果</div>
          </template>
          <div v-if="currentTask.status === 'completed' && currentTask.output_url" style="text-align: center">
            <video :src="currentTask.output_url" controls style="width: 100%; max-height: 400px; border-radius: 8px" />
            <el-button type="primary" plain @click="downloadFile(currentTask.output_url)" style="margin-top: 12px">
              下载视频
            </el-button>
          </div>
          <div v-else-if="currentTask.status === 'failed'" style="text-align: center; padding: 20px">
            <el-alert type="error" :title="currentTask.error_message || '生成失败'" show-icon :closable="false" />
          </div>
          <div v-else style="text-align: center; display: flex; align-items: center; justify-content: center; gap: 8px; color: #e6a23c; padding: 40px">
            <el-icon class="is-loading" :size="24"><Loading /></el-icon>
            <span>{{ currentTask.status === 'processing' ? '视频生成中（可能需要数分钟）...' : '排队中...' }}</span>
          </div>
        </el-card>

        <!-- 历史任务 -->
        <el-card shadow="hover" :style="{ marginTop: currentTask ? '16px' : '0' }">
          <template #header>
            <div style="font-weight: 600">📋 历史任务</div>
          </template>
          <el-table :data="tasks" stripe size="small" max-height="350">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="格式" width="60">
              <template #default="{ row }">{{ row.output_format || '-' }}</template>
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
import { Loading, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { digitalHumanGenerate, getSoulTasks, getSoulTask } from '@/api/soul'
import type { SoulTaskDetail } from '@/types/api'

const form = reactive({
  image: null as File | null,
  audio: null as File | null,
  model_type: 'lite',
  seed: 9999,
  use_face_crop: false,
})

const imagePreview = ref('')
const submitting = ref(false)
const currentTask = ref<SoulTaskDetail | null>(null)
const tasks = ref<SoulTaskDetail[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => { loadTasks() })
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

async function loadTasks() {
  try { tasks.value = await getSoulTasks('digital-human') } catch {}
}

function handleImageChange(f: any) {
  form.image = f.raw
  imagePreview.value = URL.createObjectURL(f.raw)
}

async function handleSubmit() {
  if (!form.image) return ElMessage.warning('请上传人脸图片')
  if (!form.audio) return ElMessage.warning('请上传驱动音频')

  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('image', form.image)
    fd.append('audio', form.audio)
    fd.append('model_type', form.model_type)
    fd.append('seed', String(form.seed))
    fd.append('use_face_crop', String(form.use_face_crop))

    const res = await digitalHumanGenerate(fd)
    ElMessage.success('任务已提交')
    startPolling(res.task_id)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally { submitting.value = false }
}

function startPolling(taskId: number) {
  if (pollTimer) clearInterval(pollTimer)
  currentTask.value = { id: taskId, status: 'pending' } as SoulTaskDetail
  pollTimer = setInterval(async () => {
    try {
      const t = await getSoulTask('digital-human', taskId)
      currentTask.value = t
      if (t.status === 'completed' || t.status === 'failed') {
        clearInterval(pollTimer!)
        pollTimer = null
        loadTasks()
      }
    } catch {}
  }, 3000)
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
.dh-page {
  .page-header {
    margin-bottom: 24px;
    h1 { margin: 0 0 8px; font-size: 24px; }
    p { margin: 0; color: #909399; }
  }
}
</style>
