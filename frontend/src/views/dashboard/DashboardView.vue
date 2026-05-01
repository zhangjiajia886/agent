<template>
  <div class="dashboard">
    <div class="page-header">
      <h1>仪表盘</h1>
      <p>欢迎使用 TTS 语音平台，快速开始语音合成与识别</p>
    </div>

    <el-row :gutter="20" class="stat-cards">
      <el-col :xs="24" :sm="12" :lg="6" v-for="stat in stats" :key="stat.label">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: stat.bg }">
              <el-icon :size="24" :color="stat.color">
                <component :is="stat.icon" />
              </el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="quick-actions">
      <el-col :xs="24" :sm="12">
        <el-card shadow="hover" class="action-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#667eea"><Microphone /></el-icon>
              <span>快速合成语音</span>
            </div>
          </template>
          <el-input
            v-model="quickText"
            type="textarea"
            :rows="4"
            placeholder="输入要合成的文字，快速体验 TTS 功能..."
            maxlength="500"
            show-word-limit
          />
          <div style="margin-top: 12px; display: flex; gap: 12px;">
            <el-button type="primary" :icon="VideoPlay" @click="$router.push('/tts')">前往合成页面</el-button>
            <el-button :icon="ArrowRight" plain @click="goToTTSWithText">快速合成</el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12">
        <el-card shadow="hover" class="action-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#67C23A"><Headset /></el-icon>
              <span>快速识别语音</span>
            </div>
          </template>
          <div class="upload-area" @click="$router.push('/asr')">
            <el-icon :size="48" color="#c0c4cc"><UploadFilled /></el-icon>
            <p>点击上传音频文件进行识别</p>
            <p class="sub">支持 MP3、WAV、M4A 等格式</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="recent-tasks">
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近 TTS 任务</span>
              <el-button text size="small" @click="$router.push('/tts')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentTTSTasks" size="small" stripe>
            <el-table-column prop="text" label="文本" show-overflow-tooltip />
            <el-table-column prop="format" label="格式" width="60" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!recentTTSTasks.length" class="empty-tip">暂无任务记录</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近 ASR 任务</span>
              <el-button text size="small" @click="$router.push('/asr')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentASRTasks" size="small" stripe>
            <el-table-column prop="recognized_text" label="识别结果" show-overflow-tooltip />
            <el-table-column prop="language" label="语言" width="60" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!recentASRTasks.length" class="empty-tip">暂无任务记录</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { Microphone, Headset, UploadFilled, VideoPlay, ArrowRight, User } from '@element-plus/icons-vue'
import { getTasks as getTTSTasks } from '@/api/tts'
import { getTasks as getASRTasks } from '@/api/asr'
import type { TTSTask, ASRTask } from '@/types/api'

const router = useRouter()
const quickText = ref('')
const recentTTSTasks = ref<TTSTask[]>([])
const recentASRTasks = ref<ASRTask[]>([])

const stats = ref([
  { label: 'TTS 合成次数', value: '0', icon: markRaw(Microphone), color: '#667eea', bg: 'rgba(102,126,234,0.1)' },
  { label: 'ASR 识别次数', value: '0', icon: markRaw(Headset), color: '#67C23A', bg: 'rgba(103,194,58,0.1)' },
  { label: '声音模型数', value: '0', icon: markRaw(User), color: '#E6A23C', bg: 'rgba(230,162,60,0.1)' },
  { label: '今日使用次数', value: '0', icon: markRaw(Microphone), color: '#F56C6C', bg: 'rgba(245,108,108,0.1)' },
])

function statusTagType(status: string) {
  const map: Record<string, string> = { completed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = { completed: '完成', failed: '失败', processing: '处理中', pending: '等待' }
  return map[status] || status
}

function goToTTSWithText() {
  router.push({ path: '/tts', query: { text: quickText.value } })
}

onMounted(async () => {
  try {
    const ttsTasks = await getTTSTasks(0, 5)
    recentTTSTasks.value = ttsTasks
    stats.value[0].value = String(ttsTasks.length > 0 ? ttsTasks.length : 0)
  } catch {}

  try {
    const asrTasks = await getASRTasks(0, 5)
    recentASRTasks.value = asrTasks
    stats.value[1].value = String(asrTasks.length > 0 ? asrTasks.length : 0)
  } catch {}
})
</script>

<style scoped lang="scss">
.dashboard {
  .stat-cards { margin-bottom: 20px; }

  .stat-card {
    .stat-content {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .stat-icon {
      width: 52px;
      height: 52px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .stat-value {
      font-size: 28px;
      font-weight: 700;
      color: #303133;
      line-height: 1;
    }
    .stat-label {
      font-size: 13px;
      color: #909399;
      margin-top: 4px;
    }
  }

  .quick-actions { margin-bottom: 20px; }

  .action-card {
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-size: 15px;
      font-weight: 600;
    }
    .upload-area {
      border: 2px dashed #dcdfe6;
      border-radius: 8px;
      padding: 32px;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s;

      &:hover { border-color: #409EFF; }

      p { color: #606266; margin-top: 12px; font-size: 14px; }
      p.sub { font-size: 12px; color: #c0c4cc; margin-top: 4px; }
    }
  }

  .recent-tasks {
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 15px;
      font-weight: 600;
    }
    .empty-tip {
      text-align: center;
      color: #c0c4cc;
      padding: 24px 0;
      font-size: 14px;
    }
  }
}
</style>
