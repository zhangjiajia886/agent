<template>
  <div class="asr-page">
    <div class="page-header">
      <h1>🎤 语音识别 ASR</h1>
      <p>上传音频文件，自动识别转换为文字，支持时间戳输出</p>
    </div>

    <el-row :gutter="20">
      <!-- 左侧：上传区域 -->
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-title">📂 上传音频</div>
          </template>

          <el-upload
            class="audio-upload"
            drag
            :auto-upload="false"
            :multiple="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            accept="audio/*"
          >
            <el-icon :size="48" color="#c0c4cc"><UploadFilled /></el-icon>
            <div class="upload-text">将音频拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="upload-tip">支持 MP3、WAV、M4A、FLAC、OGG 等格式，文件大小不超过 100MB</div>
            </template>
          </el-upload>

          <div v-if="selectedFile" class="selected-file">
            <el-icon color="#409EFF"><DocumentChecked /></el-icon>
            <span>{{ selectedFile.name }}</span>
            <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
          </div>

          <el-divider />

          <el-form label-width="80px">
            <el-form-item label="识别语言">
              <el-radio-group v-model="language">
                <el-radio-button value="zh">中文</el-radio-button>
                <el-radio-button value="en">英文</el-radio-button>
                <el-radio-button value="auto">自动</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <el-button
            type="primary"
            size="large"
            :loading="recognizing"
            :disabled="!selectedFile"
            :icon="Headset"
            style="width: 100%"
            @click="handleRecognize"
          >
            {{ recognizing ? '识别中...' : '开始识别' }}
          </el-button>
        </el-card>
      </el-col>

      <!-- 右侧：识别结果 -->
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover" class="result-card">
          <template #header>
            <div class="card-title-row">
              <span class="card-title">📝 识别结果</span>
              <el-button
                v-if="currentTask?.recognized_text"
                text
                :icon="CopyDocument"
                size="small"
                @click="copyText"
              >
                复制
              </el-button>
            </div>
          </template>

          <div v-if="!currentTask" class="empty-result">
            <el-icon :size="60" color="#e0e0e0"><ChatSquare /></el-icon>
            <p>识别结果将显示在这里</p>
          </div>

          <div v-else>
            <div class="result-meta">
              <el-tag :type="statusTagType(currentTask.status)" size="small">{{ statusLabel(currentTask.status) }}</el-tag>
              <span v-if="currentTask.duration" class="meta-item">时长：{{ currentTask.duration.toFixed(1) }}s</span>
              <span class="meta-item">语言：{{ currentTask.language }}</span>
            </div>

            <div v-if="currentTask.status === 'processing' || currentTask.status === 'pending'" class="processing">
              <el-progress :percentage="progress" striped striped-flow :duration="8" />
              <p>正在识别，请稍候...</p>
            </div>

            <div v-if="currentTask.recognized_text" class="recognized-text">
              {{ currentTask.recognized_text }}
            </div>

            <div v-if="currentTask.segments?.length" class="segments">
              <el-divider>时间轴</el-divider>
              <div v-for="(seg, i) in currentTask.segments" :key="i" class="segment-item">
                <span class="seg-time">[{{ seg.start.toFixed(1) }}s - {{ seg.end.toFixed(1) }}s]</span>
                <span class="seg-text">{{ seg.text }}</span>
              </div>
            </div>

            <el-alert
              v-if="currentTask.status === 'failed'"
              type="error"
              :description="currentTask.error_message || '识别失败'"
              show-icon
              :closable="false"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 历史记录 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-title">📋 识别历史</div>
      </template>
      <el-table :data="tasks" stripe size="small" v-loading="tasksLoading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="recognized_text" label="识别结果" show-overflow-tooltip min-width="200" />
        <el-table-column prop="language" label="语言" width="60" />
        <el-table-column label="时长" width="70">
          <template #default="{ row }">{{ row.duration ? row.duration.toFixed(1) + 's' : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewTask(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Headset, DocumentChecked, CopyDocument, ChatSquare } from '@element-plus/icons-vue'
import { recognize, getTasks, getTask } from '@/api/asr'
import type { ASRTask } from '@/types/api'

const recognizing = ref(false)
const tasksLoading = ref(false)
const selectedFile = ref<File | null>(null)
const fileList = ref([])
const language = ref('zh')
const tasks = ref<ASRTask[]>([])
const currentTask = ref<ASRTask | null>(null)
const progress = ref(30)
let pollTimer: ReturnType<typeof setInterval> | null = null

function handleFileChange(file: { raw: File }) {
  selectedFile.value = file.raw
}

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

function statusTagType(status: string) {
  const map: Record<string, string> = { completed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = { completed: '已完成', failed: '失败', processing: '识别中', pending: '等待中' }
  return map[status] || status
}

async function handleRecognize() {
  if (!selectedFile.value) return
  recognizing.value = true
  progress.value = 20
  try {
    const res = await recognize(selectedFile.value, language.value)
    currentTask.value = { id: res.task_id, audio_url: '', language: language.value, recognized_text: null, duration: null, segments: null, status: 'pending', error_message: null, cost_credits: null, created_at: new Date().toISOString(), completed_at: null }
    startPolling(res.task_id)
    await loadTasks()
  } catch {
    ElMessage.error('识别请求失败')
  } finally {
    recognizing.value = false
  }
}

function startPolling(taskId: number) {
  progress.value = 30
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const task = await getTask(taskId)
      currentTask.value = task
      if (progress.value < 90) progress.value += 15
      if (task.status === 'completed' || task.status === 'failed') {
        clearInterval(pollTimer!)
        progress.value = 100
        await loadTasks()
        if (task.status === 'completed') ElMessage.success('识别完成！')
        else ElMessage.error('识别失败：' + (task.error_message || '未知错误'))
      }
    } catch {
      clearInterval(pollTimer!)
    }
  }, 2000)
}

function copyText() {
  if (!currentTask.value?.recognized_text) return
  navigator.clipboard.writeText(currentTask.value.recognized_text)
  ElMessage.success('已复制到剪贴板')
}

function viewTask(task: ASRTask) {
  currentTask.value = task
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    tasks.value = await getTasks(0, 20)
  } finally {
    tasksLoading.value = false
  }
}

onMounted(loadTasks)
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped lang="scss">
.asr-page {
  .card-title {
    font-size: 15px;
    font-weight: 600;
  }

  .card-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .audio-upload {
    width: 100%;
    :deep(.el-upload-dragger) {
      width: 100%;
      padding: 40px 20px;
    }
    .upload-text {
      font-size: 14px;
      color: #606266;
      margin-top: 12px;
      em { color: #409EFF; font-style: normal; }
    }
    .upload-tip {
      font-size: 12px;
      color: #909399;
      text-align: center;
      margin-top: 8px;
    }
  }

  .selected-file {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: #f0f9ff;
    border-radius: 6px;
    margin-top: 12px;
    font-size: 14px;
    color: #409EFF;

    .file-size {
      margin-left: auto;
      color: #909399;
      font-size: 12px;
    }
  }

  .empty-result {
    text-align: center;
    padding: 60px 20px;
    color: #c0c4cc;
    p { margin-top: 16px; font-size: 14px; }
  }

  .result-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;

    .meta-item {
      font-size: 13px;
      color: #909399;
    }
  }

  .processing {
    p { text-align: center; color: #909399; font-size: 13px; margin-top: 8px; }
  }

  .recognized-text {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 16px;
    font-size: 15px;
    line-height: 1.8;
    color: #303133;
    min-height: 80px;
    border: 1px solid #ebeef5;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .segments {
    .segment-item {
      display: flex;
      gap: 12px;
      padding: 6px 0;
      font-size: 13px;
      border-bottom: 1px solid #f5f5f5;

      .seg-time {
        color: #909399;
        white-space: nowrap;
        min-width: 140px;
      }
      .seg-text { color: #303133; }
    }
  }
}
</style>
