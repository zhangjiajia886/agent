<template>
  <div class="comic-page">
    <div class="page-header">
      <h1>🎨 漫剧生成</h1>
      <p>用 AI 将你的故事想象变成精美漫剧，支持仙侠、水墨、盲盒、动漫等多种风格</p>
    </div>

    <!-- 首次进入引导弹窗 -->
    <el-dialog
      v-model="guideVisible"
      title="🎨 欢迎来到漫剧工作台"
      width="480px"
      :close-on-click-modal="false"
      align-center
    >
      <div class="guide-steps">
        <div class="guide-step">
          <div class="guide-step-num">1</div>
          <div class="guide-step-body">
            <div class="guide-step-title">描述你的故事</div>
            <div class="guide-step-desc">输入一句话，比如「仙侠风栄4格漫剧，女侠初入仙山」；或点击风格标签自动填充</div>
          </div>
        </div>
        <div class="guide-step">
          <div class="guide-step-num">2</div>
          <div class="guide-step-body">
            <div class="guide-step-title">点击「✨ 生成漫剧」</div>
            <div class="guide-step-desc">AI 自动规划分镜、逐格生成，红46格约 1~3 分钟；可关闭页面等待</div>
          </div>
        </div>
        <div class="guide-step">
          <div class="guide-step-num">3</div>
          <div class="guide-step-body">
            <div class="guide-step-title">下载或继续创作</div>
            <div class="guide-step-desc">下载全部图片，或点击「🎨 去编辑」换背景、换服装，点击「🎬 动态化」生成视频</div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" size="large" @click="closeGuide" style="width:100%">我知道了，开始创作！</el-button>
      </template>
    </el-dialog>

    <!-- 服务不可用提示 -->
    <el-alert
      v-if="!serviceAvailable && serviceChecked"
      title="漫剧生成服务暂时不可用"
      description="ComfyUI 推理服务未启动，请联系管理员或稍后再试"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 20px;"
    />

    <el-tabs v-model="activeTab" class="comic-tabs">

      <!-- ══════════ Tab 1: 漫剧创作 ══════════ -->
      <el-tab-pane label="✏️ 漫剧创作" name="create">
    <el-row :gutter="20">
      <!-- ═══════════ 左侧：创作配置 ═══════════ -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="hover" class="create-card">
          <template #header>
            <div class="card-header-title">✏️ 创作设置</div>
          </template>

          <el-form :model="form" label-position="top">
            <!-- 故事描述 -->
            <el-form-item label="故事描述">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="5"
                placeholder="描述你的漫剧故事，例如：&#10;仙侠风格4格漫剧，一位白衣女侠初次踏入云雾缭绕的神秘仙山，满怀期待与好奇&#10;&#10;你可以指定：风格、人物、情节、格数、是否保留人脸特征"
                maxlength="300"
                show-word-limit
                resize="none"
              />
            </el-form-item>

            <!-- 格数 -->
            <el-form-item label="漫剧格数">
              <el-radio-group v-model="form.num_frames">
                <el-radio-button :value="2">2 格</el-radio-button>
                <el-radio-button :value="4">4 格（推荐）</el-radio-button>
                <el-radio-button :value="6">6 格</el-radio-button>
              </el-radio-group>
              <div class="hint-text">格数越多，生成时间越长（每格约 20~40 秒）</div>
            </el-form-item>

            <!-- 保留我的脸 -->
            <el-form-item>
              <div class="face-toggle-row">
                <el-switch v-model="faceEnabled" active-color="#667eea" />
                <span class="face-toggle-label">
                  📸 <strong>人物形象参考</strong>
                  <span class="face-toggle-sub">上传参考照片，AI 将保持人物面部特征一致</span>
                </span>
              </div>
              <div v-show="faceEnabled" style="margin-top:10px">
                <div
                  class="face-upload-area"
                  :class="{ 'has-image': facePreview }"
                  @click="triggerFaceUpload"
                  @dragover.prevent
                  @drop.prevent="handleFaceDrop"
                >
                  <img v-if="facePreview" :src="facePreview" class="face-preview" />
                  <div v-else class="face-placeholder">
                    <el-icon :size="36" color="#c0c4cc"><Avatar /></el-icon>
                    <p>拖入或点击上传参考照片</p>
                    <p class="sub">建议：正面清晰、光线均匀、无遮挡</p>
                  </div>
                  <el-button
                    v-if="facePreview"
                    class="face-remove-btn"
                    type="danger"
                    :icon="Close"
                    circle size="small"
                    @click.stop="removeFace"
                  />
                </div>
                <input ref="faceInputRef" type="file" accept="image/*" style="display:none" @change="handleFaceSelect" />
              </div>
            </el-form-item>

            <!-- 风格预设快速选择 -->
            <el-form-item label="风格快速填充">
              <div class="style-presets">
                <el-tag
                  v-for="preset in stylePresets"
                  :key="preset.label"
                  class="style-tag"
                  :effect="selectedPreset === preset.label ? 'dark' : 'plain'"
                  :color="selectedPreset === preset.label ? '#667eea' : ''"
                  @click="applyPreset(preset)"
                  style="cursor: pointer;"
                >
                  {{ preset.icon }} {{ preset.label }}
                </el-tag>
              </div>
            </el-form-item>

            <!-- 生成按钮 -->
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="generating"
                :disabled="!form.description.trim() || !serviceAvailable"
                @click="handleGenerate"
                style="width: 100%;"
              >
                <el-icon v-if="!generating"><MagicStick /></el-icon>
                {{ generating ? `生成中... 第 ${currentFrame}/${form.num_frames} 格` : '✨ 生成漫剧' }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- ═══════════ 右侧：生成结果 ═══════════ -->
      <el-col :xs="24" :lg="14">
        <!-- 等待状态 -->
        <el-card v-if="!currentTask" shadow="hover" class="result-placeholder">
          <div class="placeholder-content">
            <div class="placeholder-icon">🎭</div>
            <p>在左侧描述你的漫剧故事</p>
            <p class="sub">AI 将自动规划分镜、生成提示词并逐格渲染</p>
            <div class="feature-tags">
              <el-tag v-for="f in features" :key="f" type="info" size="small" style="margin: 4px;">{{ f }}</el-tag>
            </div>
          </div>
        </el-card>

        <!-- 生成中 / 结果展示 -->
        <el-card v-else shadow="hover" class="result-card">
          <template #header>
            <div class="card-header-flex">
              <div class="card-header-title">
                🖼️ 生成结果
                <el-tag :type="statusTagType(currentTask.status)" size="small" style="margin-left: 8px;">
                  {{ statusLabel(currentTask.status) }}
                </el-tag>
                <el-tag v-if="currentTask.style" type="info" size="small" style="margin-left: 4px;">
                  {{ styleLabel(currentTask.style) }}
                </el-tag>
              </div>
              <el-button text size="small" @click="clearResult">清空</el-button>
            </div>
          </template>

          <!-- 处理中进度 -->
          <div v-if="currentTask.status === 'processing' || currentTask.status === 'pending'" class="progress-section">
            <el-progress
              :percentage="progressPercent"
              :striped="true"
              :striped-flow="true"
              :duration="8"
              status="active"
            />
            <p class="progress-hint">
              {{ currentTask.status === 'pending' ? '⏳ 排队等待中...' : `🖌️ 正在渲染第 ${currentFrame} / ${form.num_frames} 格...` }}
            </p>
            <div v-if="currentTask.storyboard?.length" class="storyboard-preview">
              <div class="storyboard-title">📝 分镜规划</div>
              <div v-for="(s, i) in currentTask.storyboard" :key="i" class="storyboard-item">
                <span class="frame-badge">{{ i + 1 }}</span>
                <span>{{ s }}</span>
              </div>
            </div>
          </div>

          <!-- 失败 -->
          <el-alert
            v-if="currentTask.status === 'failed'"
            type="error"
            :description="currentTask.error_message || '生成失败，请重试'"
            show-icon
            :closable="false"
          />

          <!-- 图片格子（有图就显示，不等全部完成）-->
          <div v-if="currentTask.frame_urls?.length" class="comic-strip">
            <!-- 生成中：已出图的格子 + 剩余格占位 -->
            <div v-if="currentTask.storyboard?.length" class="storyboard-list">
              <div class="storyboard-title">📝 分镜描述</div>
              <div v-for="(s, i) in currentTask.storyboard" :key="i" class="storyboard-item">
                <span class="frame-badge" :style="i < currentTask.frame_urls!.length ? 'background:#67C23A' : ''">{{ i + 1 }}</span>
                <span>{{ s }}</span>
              </div>
            </div>

            <div class="frames-grid" :class="`cols-${gridCols}`">
              <!-- 已生成的格 -->
              <div v-for="(url, i) in currentTask.frame_urls" :key="'done-'+i" class="frame-cell">
                <div class="frame-number">第 {{ i + 1 }} 格 ✓</div>
                <el-image
                  :src="url"
                  :preview-src-list="currentTask.frame_urls"
                  :initial-index="i"
                  fit="cover" class="frame-image" lazy
                >
                  <template #placeholder>
                    <div class="image-loading"><el-icon class="is-loading"><Loading /></el-icon></div>
                  </template>
                </el-image>
              </div>
              <!-- 待生成的占位格 -->
              <div
                v-for="i in (form.num_frames - (currentTask.frame_urls?.length ?? 0))"
                :key="'pending-'+i"
                v-show="currentTask.status === 'processing' || currentTask.status === 'pending'"
                class="frame-cell frame-cell--pending"
              >
                <div class="frame-number">第 {{ (currentTask.frame_urls?.length ?? 0) + i }} 格</div>
                <div class="image-loading">
                  <el-icon class="is-loading" :size="28"><Loading /></el-icon>
                  <p style="font-size:12px;color:#c0c4cc;margin-top:6px">绘制中...</p>
                </div>
              </div>
            </div>

            <!-- 操作按钮：完成后显示 -->
            <div v-if="currentTask.status === 'completed'" class="result-actions">
              <el-button type="primary" :icon="Download" @click="downloadAllFrames">
                下载全部图片（{{ currentTask.frame_urls.length }} 张）
              </el-button>
              <el-button :icon="Refresh" @click="handleGenerate" :disabled="generating">
                重新生成
              </el-button>
              <el-button type="success" @click="transferTo('edit', currentTask.frame_urls![0])">
                🎨 去编辑
              </el-button>
              <el-button type="warning" @click="transferTo('video', currentTask.frame_urls![0])">
                🎬 动态化
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
      </el-tab-pane>

      <!-- ══════════ Tab 2: 图像编辑 ══════════ -->
      <el-tab-pane label="🎨 图像编辑" name="edit">
        <el-row :gutter="20">
          <el-col :xs="24" :lg="11">
            <el-card shadow="hover">
              <template #header><div class="card-header-title">📷 原始图片</div></template>
              <div
                class="face-upload-area"
                :class="{ 'has-image': editSourcePreview }"
                @click="triggerEditUpload"
                @dragover.prevent
                @drop.prevent="handleEditDrop"
              >
                <img v-if="editSourcePreview" :src="editSourcePreview" class="face-preview" />
                <div v-else class="face-placeholder">
                  <el-icon :size="36" color="#c0c4cc"><Picture /></el-icon>
                  <p>上传要编辑的图片</p>
                  <p class="sub">支持拖拽</p>
                </div>
                <el-button v-if="editSourcePreview" class="face-remove-btn" type="danger" :icon="Close" circle size="small" @click.stop="removeEditSource" />
              </div>
              <input ref="editUploadRef" type="file" accept="image/*" style="display:none" @change="handleEditSelect" />
              <el-form :model="editForm" label-position="top" style="margin-top:16px">
                <el-form-item label="编辑指令（用中文描述你想怎么改）">
                  <el-input
                    v-model="editForm.instruction"
                    type="textarea" :rows="3"
                    placeholder="例如：将背景替换为云雾缭绕的仙山，保持人物不变"
                    maxlength="200" show-word-limit
                  />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="editLoading" :disabled="!editSourceFile || !editForm.instruction.trim()" @click="handleEdit" style="width:100%">
                    <el-icon v-if="!editLoading"><MagicStick /></el-icon>
                    {{ editLoading ? '编辑中...' : '✨ 开始编辑' }}
                  </el-button>
                </el-form-item>
              </el-form>

              <!-- 编辑历史面板 -->
              <div v-if="editHistory.length" class="edit-history-panel">
                <div class="storyboard-title">📋 编辑历史 <span style="font-weight:normal;color:#909399">（点击可回退到该步）</span></div>
                <div
                  v-for="(h, i) in editHistory" :key="i"
                  class="edit-history-item"
                  :class="{ 'edit-history-item--active': i === editHistoryCursor }"
                  @click="restoreHistory(i)"
                >
                  <span class="frame-badge" :style="i === editHistoryCursor ? 'background:#67C23A' : ''">{{ i + 1 }}</span>
                  <span>{{ h.instruction }}</span>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :xs="24" :lg="13">
            <el-card shadow="hover" class="result-card">
              <template #header>
                <div class="card-header-flex">
                  <div class="card-header-title">🖼️ 编辑结果</div>
                  <el-button v-if="editResult" text size="small" @click="editResult = null; compareRatio = 50">清空</el-button>
                </div>
              </template>

              <!-- 无结果：占位 + 指令示例 -->
              <div v-if="!editResult" class="placeholder-content" style="min-height:280px">
                <div class="placeholder-icon">🎨</div>
                <p>上传图片并输入指令后点击编辑</p>
                <div style="margin-top:16px;text-align:left;max-width:300px">
                  <div class="storyboard-title">指令示例（点击填充）</div>
                  <div v-for="ex in editExamples" :key="ex" class="storyboard-item" style="cursor:pointer" @click="editForm.instruction = ex">
                    <span class="frame-badge">→</span><span>{{ ex }}</span>
                  </div>
                </div>
              </div>

              <!-- 有结果：对比滑块 -->
              <div
                v-else
                ref="compareRef"
                class="compare-wrap"
                @mousedown="startCompare"
                @mousemove="updateCompare"
                @mouseup="endCompare"
                @mouseleave="endCompare"
              >
                <img :src="editSourcePreview!" class="compare-img" />
                <img :src="editResult" class="compare-img compare-after" :style="`clip-path: inset(0 ${100 - compareRatio}% 0 0)`" />
                <div class="compare-divider" :style="`left: ${compareRatio}%`">
                  <div class="compare-handle">⇔</div>
                </div>
                <span class="compare-label compare-label--left">原图</span>
                <span class="compare-label compare-label--right">编辑后</span>
              </div>

              <div v-if="editResult" class="result-actions">
                <el-button type="primary" :icon="Download" @click="downloadSingle(editResult!, 'edited.png')">下载结果</el-button>
                <el-button type="success" @click="continueEdit">继续编辑</el-button>
                <el-button type="warning" @click="transferTo('video', editResult!)">🎬 动态化</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- ══════════ Tab 3: 动态视频 ══════════ -->
      <el-tab-pane label="🎬 动态视频" name="video">
        <el-alert type="info" show-icon :closable="false" description="使用 Wan 2.1 I2V 模型，将漫剧图片动态化。每段 2 秒视频生成耗时约 3~6 分钟。" style="margin-bottom:16px" />
        <el-row :gutter="20">
          <el-col :xs="24" :lg="11">
            <el-card shadow="hover">
              <template #header><div class="card-header-title">🖼️ 源图片</div></template>
              <div
                class="face-upload-area"
                :class="{ 'has-image': videoSourcePreview }"
                @click="triggerVideoUpload"
                @dragover.prevent
                @drop.prevent="handleVideoDrop"
              >
                <img v-if="videoSourcePreview" :src="videoSourcePreview" class="face-preview" />
                <div v-else class="face-placeholder">
                  <el-icon :size="36" color="#c0c4cc"><VideoCamera /></el-icon>
                  <p>上传漫剧图片进行动态化</p>
                  <p class="sub">或将漫剧创作生成的图片拖入</p>
                </div>
                <el-button v-if="videoSourcePreview" class="face-remove-btn" type="danger" :icon="Close" circle size="small" @click.stop="removeVideoSource" />
              </div>
              <input ref="videoUploadRef" type="file" accept="image/*" style="display:none" @change="handleVideoSelect" />
              <el-form :model="videoForm" label-position="top" style="margin-top:16px">
                <el-form-item label="运动描述（可选）">
                  <el-input v-model="videoForm.motion" placeholder="例如：gentle hair swaying, soft breathing, natural motion" maxlength="100" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="videoLoading" :disabled="!videoSourceFile" @click="handleAnimate" style="width:100%">
                    <el-icon v-if="!videoLoading"><VideoPlay /></el-icon>
                    {{ videoLoading ? '生成中（约 3~6 分钟）...' : '🎬 开始动态化' }}
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>

          <el-col :xs="24" :lg="13">
            <el-card shadow="hover">
              <template #header><div class="card-header-title">🎥 视频结果</div></template>
              <div v-if="!videoResult && !videoLoading" class="placeholder-content" style="min-height:280px">
                <div class="placeholder-icon">🎬</div>
                <p>上传漫剧图片，生成约 2 秒的动态视频</p>
                <p class="sub">由 Wan 2.1 I2V 模型驱动，生成耗时约 3~6 分钟</p>
              </div>
              <div v-if="videoLoading" class="progress-section">
                <el-progress :percentage="videoProgress" :striped="true" :striped-flow="true" :duration="8" status="active" />
                <p class="progress-hint">🎬 Wan I2V 生成中，已等待 {{ videoElapsed }}s...</p>
              </div>
              <div v-if="videoResult">
                <video :src="videoResult" controls autoplay loop style="width:100%;border-radius:8px" />
                <div class="result-actions">
                  <el-button type="primary" :icon="Download" @click="downloadSingle(videoResult!, 'comic_video.mp4')">下载视频</el-button>
                  <el-button type="success" @click="$router.push('/tts')">🔊 加入配音</el-button>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Avatar, Close, MagicStick, Download, Refresh, Loading, Picture, VideoCamera, VideoPlay } from '@element-plus/icons-vue'
import { generateComic, getComicTask, getComicHealth, type ComicTask } from '@/api/comic'

// ─────────── 表单状态 ───────────
const form = ref({
  description: '',
  num_frames: 4,
})
const faceEnabled = ref(false)
const facePreview = ref<string | null>(null)
const faceFile = ref<File | null>(null)
const faceInputRef = ref<HTMLInputElement | null>(null)
const selectedPreset = ref('')

// ─────────── 任务状态 ───────────
const generating = ref(false)
const currentTask = ref<ComicTask | null>(null)
const currentFrame = ref(0)
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)

// ─────────── 服务健康 ───────────
const serviceAvailable = ref(true)
const serviceChecked = ref(false)

// ─────────── 风格预设 ───────────
const stylePresets = [
  { label: '仙侠', icon: '⚔️', text: '仙侠风格4格漫剧，一位白衣女侠初次踏入云雾缭绕的神秘仙山，充满期待与好奇' },
  { label: '水墨', icon: '🖌️', text: '水墨国画风格4格漫剧，一位书生在溪边垂钓，忽遇神秘少女翩然而至' },
  { label: '盲盒', icon: '🎁', text: '盲盒Q版风格4格漫剧，超可爱小女生第一次打开神秘礼盒，惊喜连连' },
  { label: '动漫', icon: '🌸', text: '动漫风格4格漫剧，樱花树下的浪漫邂逅，阳光少女与文静男生的初遇' },
]

const features = ['AI 自动规划分镜', '多种风格可选', '人脸特征保持', '专业提示词生成']

// ─────────── 计算属性 ───────────
const progressPercent = computed(() => {
  if (!currentTask.value) return 0
  if (currentTask.value.status === 'pending') return 5
  if (currentTask.value.status === 'completed') return 100
  if (currentTask.value.status === 'failed') return 100
  const done = currentTask.value.frame_urls?.length ?? 0
  return Math.max(10, Math.round((done / form.value.num_frames) * 90) + 5)
})

const gridCols = computed(() => {
  const n = currentTask.value?.frame_urls?.length ?? 0
  if (n <= 2) return 2
  if (n <= 4) return 2
  return 3
})

// ─────────── 工具函数 ───────────
function statusTagType(status: string) {
  return { completed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }[status] || 'info'
}

function statusLabel(status: string) {
  return { completed: '已完成', failed: '失败', processing: '生成中', pending: '排队中' }[status] || status
}

function styleLabel(style: string) {
  return { xianxia: '仙侠', blindbox: '盲盒', ink: '水墨', anime: '动漫', realistic: '写实' }[style] || style
}

// ─────────── 人脸上传 ───────────
function triggerFaceUpload() {
  faceInputRef.value?.click()
}

function handleFaceSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) setFaceFile(file)
}

function handleFaceDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0]
  if (file && file.type.startsWith('image/')) setFaceFile(file)
}

function setFaceFile(file: File) {
  faceFile.value = file
  facePreview.value = URL.createObjectURL(file)
}

function removeFace() {
  faceFile.value = null
  facePreview.value = null
  if (faceInputRef.value) faceInputRef.value.value = ''
}

// ─────────── 风格预设 ───────────
function applyPreset(preset: typeof stylePresets[0]) {
  form.value.description = preset.text
  selectedPreset.value = preset.label
}

// ─────────── 生成 ───────────
async function handleGenerate() {
  if (!form.value.description.trim()) return
  stopPolling()

  generating.value = true
  currentFrame.value = 0
  currentTask.value = null

  try {
    const res = await generateComic({
      description: form.value.description,
      num_frames: form.value.num_frames,
      include_video: false,
      face_image: faceFile.value,
    })

    currentTask.value = {
      task_id: res.task_id,
      status: res.status as ComicTask['status'],
      description: form.value.description,
      num_frames: form.value.num_frames,
    }

    startPolling(res.task_id)
  } catch {
    generating.value = false
    ElMessage.error('提交任务失败，请检查服务状态')
  }
}

function startPolling(taskId: number) {
  pollTimer.value = setInterval(async () => {
    try {
      const task = await getComicTask(taskId)
      currentTask.value = task
      currentFrame.value = task.frame_urls?.length ?? 0

      if (task.status === 'completed') {
        generating.value = false
        stopPolling()
        ElMessage.success(`漫剧生成完成，共 ${task.frame_urls?.length} 格`)
        notifyCompletion(task.frame_urls?.length ?? 0)
      } else if (task.status === 'failed') {
        generating.value = false
        stopPolling()
        ElMessage.error(task.error_message || '生成失败')
      }
    } catch {
      stopPolling()
      generating.value = false
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function transferTo(tab: 'edit' | 'video', url: string) {
  try {
    const resp = await fetch(url)
    const blob = await resp.blob()
    const file = new File([blob], 'comic_frame.png', { type: 'image/png' })
    if (tab === 'edit') {
      editSourceFile.value = file
      editSourcePreview.value = url
    } else {
      videoSourceFile.value = file
      videoSourcePreview.value = url
    }
    activeTab.value = tab
  } catch {
    ElMessage.error('图片传递失败，请手动上传')
  }
}

function clearResult() {
  stopPolling()
  currentTask.value = null
  generating.value = false
  currentFrame.value = 0
}

// ─────────── 下载 ───────────
async function downloadAllFrames() {
  if (!currentTask.value?.frame_urls) return
  for (let i = 0; i < currentTask.value.frame_urls.length; i++) {
    const url = currentTask.value.frame_urls[i]
    const a = document.createElement('a')
    a.href = url
    a.download = `comic_frame_${i + 1}.png`
    a.click()
    await new Promise(r => setTimeout(r, 300))
  }
}

// ─────────── Tab 2: 图像编辑 ───────────
const editUploadRef = ref<HTMLInputElement | null>(null)
const editSourceFile = ref<File | null>(null)
const editSourcePreview = ref<string | null>(null)
const editForm = ref({ instruction: '' })
const editLoading = ref(false)
const editResult = ref<string | null>(null)

interface EditHistoryItem { instruction: string; sourceUrl: string; resultUrl: string }
const editHistory = ref<EditHistoryItem[]>([])
const editHistoryCursor = ref(-1)

const compareRatio = ref(50)
const isDraggingCompare = ref(false)
const compareRef = ref<HTMLDivElement | null>(null)
const editExamples = [
  '将背景替换为云雾缭绕的仙山',
  '把衣服改为红色汉服',
  '转为水墨画风格',
  '添加日落暖光效果',
  '生成该角色的侧面视图',
]

function triggerEditUpload() { editUploadRef.value?.click() }
function handleEditSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) { editSourceFile.value = file; editSourcePreview.value = URL.createObjectURL(file) }
}
function handleEditDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0]
  if (file?.type.startsWith('image/')) { editSourceFile.value = file; editSourcePreview.value = URL.createObjectURL(file) }
}
function removeEditSource() {
  editSourceFile.value = null; editSourcePreview.value = null
  if (editUploadRef.value) editUploadRef.value.value = ''
}
async function handleEdit() {
  ElMessage.info('图像编辑功能开发中，敬请期待')
}

// ─────────── Tab 3: 动态视频 ───────────
const videoUploadRef = ref<HTMLInputElement | null>(null)
const videoSourceFile = ref<File | null>(null)
const videoSourcePreview = ref<string | null>(null)
const videoForm = ref({ motion: 'gentle breathing, hair swaying, natural motion' })
const videoLoading = ref(false)
const videoResult = ref<string | null>(null)
const videoProgress = ref(0)
const videoElapsed = ref(0)

function triggerVideoUpload() { videoUploadRef.value?.click() }
function handleVideoSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) { videoSourceFile.value = file; videoSourcePreview.value = URL.createObjectURL(file) }
}
function handleVideoDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0]
  if (file?.type.startsWith('image/')) { videoSourceFile.value = file; videoSourcePreview.value = URL.createObjectURL(file) }
}
function removeVideoSource() {
  videoSourceFile.value = null; videoSourcePreview.value = null
  if (videoUploadRef.value) videoUploadRef.value.value = ''
}
async function handleAnimate() {
  ElMessage.info('动态视频功能开发中，敬请期待')
}

function startCompare(e: MouseEvent) {
  isDraggingCompare.value = true
  updateCompare(e)
}
function updateCompare(e: MouseEvent) {
  if (!isDraggingCompare.value || !compareRef.value) return
  const rect = compareRef.value.getBoundingClientRect()
  compareRatio.value = Math.max(5, Math.min(95, ((e.clientX - rect.left) / rect.width) * 100))
}
function endCompare() { isDraggingCompare.value = false }

function restoreHistory(index: number) {
  const item = editHistory.value[index]
  editSourcePreview.value = item.sourceUrl
  editResult.value = item.resultUrl
  editHistoryCursor.value = index
  editHistory.value = editHistory.value.slice(0, index + 1)
  compareRatio.value = 50
  fetch(item.sourceUrl).then(r => r.blob()).then(b => {
    editSourceFile.value = new File([b], 'source.png', { type: 'image/png' })
  }).catch(() => {})
}

function continueEdit() {
  if (!editResult.value) return
  const url = editResult.value
  editSourcePreview.value = url
  editResult.value = null
  editForm.value.instruction = ''
  fetch(url).then(r => r.blob()).then(b => {
    editSourceFile.value = new File([b], 'source.png', { type: 'image/png' })
  }).catch(() => {})
}

function downloadSingle(url: string, filename: string) {
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
}

// ─────────── Tab 状态 ───────────
const activeTab = ref('create')

// ─────────── 首次引导 ───────────
const guideVisible = ref(false)

function closeGuide() {
  guideVisible.value = false
  localStorage.setItem('comic_guide_shown', '1')
}

// ─────────── 生成完成通知 ───────────
let titleFlashTimer: ReturnType<typeof setInterval> | null = null

function notifyCompletion(frameCount: number) {
  if (Notification.permission === 'granted') {
    new Notification('✅ 漫剧生成完成！', {
      body: `已生成 ${frameCount} 格漫剧，点击查看`,
      icon: '/favicon.svg',
    })
  }
  const originalTitle = '漫剧工作台'
  let flash = false
  titleFlashTimer = setInterval(() => {
    document.title = flash ? '✅ 漫剧已完成！' : originalTitle
    flash = !flash
  }, 900)
  setTimeout(() => {
    if (titleFlashTimer) clearInterval(titleFlashTimer)
    document.title = originalTitle
  }, 8000)
}

// ─────────── 生命周期 ───────────
onMounted(async () => {
  try {
    const health = await getComicHealth()
    serviceAvailable.value = health.comfyui_reachable && health.enabled
  } catch {
    serviceAvailable.value = false
  }
  serviceChecked.value = true

  if (!localStorage.getItem('comic_guide_shown')) {
    setTimeout(() => { guideVisible.value = true }, 300)
  }

  if (Notification.permission === 'default') {
    Notification.requestPermission()
  }
})

onUnmounted(() => {
  stopPolling()
  if (titleFlashTimer) clearInterval(titleFlashTimer)
})
</script>

<style scoped lang="scss">
.comic-page {
  .create-card,
  .result-card,
  .result-placeholder {
    height: 100%;
  }
}

.card-header-flex {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

// ── 保留我的脸开关行 ──
.face-toggle-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.face-toggle-label {
  font-size: 14px;
  color: #303133;
  display: flex;
  flex-direction: column;
  gap: 2px;

  .face-toggle-sub {
    font-size: 12px;
    color: #909399;
    font-weight: normal;
  }
}

// ── 人脸上传区 ──
.face-upload-area {
  position: relative;
  width: 100%;
  height: 140px;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s;
  overflow: hidden;

  &:hover { border-color: #667eea; }

  &.has-image {
    border-style: solid;
    border-color: #667eea;
  }
}

.face-placeholder {
  text-align: center;
  p { color: #909399; font-size: 13px; margin-top: 8px; }
  .sub { font-size: 12px; color: #c0c4cc; }
}

.face-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.face-remove-btn {
  position: absolute;
  top: 6px;
  right: 6px;
}

// ── 风格预设 ──
.style-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.style-tag {
  transition: all 0.2s;
  &:hover { transform: translateY(-1px); }
}

// ── 提示文字 ──
.hint-text {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}

// ── 结果占位 ──
.result-placeholder {
  .placeholder-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 280px;
    color: #909399;

    .placeholder-icon {
      font-size: 64px;
      margin-bottom: 16px;
      opacity: 0.5;
    }
    p { font-size: 14px; margin: 4px 0; }
    .sub { font-size: 13px; color: #c0c4cc; }
  }

  .feature-tags {
    margin-top: 16px;
  }
}

// ── 进度区 ──
.progress-section {
  padding: 8px 0;

  .progress-hint {
    color: #909399;
    font-size: 13px;
    text-align: center;
    margin-top: 12px;
  }
}

// ── 分镜描述 ──
.storyboard-preview,
.storyboard-list {
  margin-top: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px 16px;

  .storyboard-title {
    font-size: 13px;
    font-weight: 600;
    color: #606266;
    margin-bottom: 8px;
  }
}

.storyboard-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
  line-height: 1.5;
}

.frame-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #667eea;
  color: white;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
  margin-top: 2px;
}

// ── 漫剧格子 ──
.comic-strip {
  .frames-grid {
    display: grid;
    gap: 12px;
    margin-top: 16px;

    &.cols-2 { grid-template-columns: repeat(2, 1fr); }
    &.cols-3 { grid-template-columns: repeat(3, 1fr); }
  }
}

.frame-cell--pending {
  background: #f9f9fb;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 2px dashed #e4e7ed;
  aspect-ratio: 3 / 4;
  border-radius: 8px;
}

.frame-cell {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #ebeef5;
  background: #fafafa;

  .frame-number {
    position: absolute;
    top: 6px;
    left: 6px;
    z-index: 1;
    background: rgba(0, 0, 0, 0.55);
    color: white;
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 10px;
    backdrop-filter: blur(4px);
  }
}

.frame-image {
  width: 100%;
  aspect-ratio: 3 / 4;
  display: block;
}

.image-loading {
  width: 100%;
  aspect-ratio: 3 / 4;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  font-size: 24px;
  color: #c0c4cc;
}

// ── 引导弹窗 ──
.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 8px 0;
}

.guide-step {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.guide-step-num {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.guide-step-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.guide-step-desc {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

// ── 对比滑块 ──
.compare-wrap {
  position: relative;
  user-select: none;
  cursor: col-resize;
  border-radius: 8px;
  overflow: hidden;
  line-height: 0;

  .compare-img {
    width: 100%;
    display: block;
    max-height: 480px;
    object-fit: contain;
    background: #f5f7fa;
  }

  .compare-after {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    max-height: unset;
    object-fit: contain;
    background: transparent;
  }

  .compare-divider {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: white;
    box-shadow: 0 0 6px rgba(0,0,0,0.3);
    pointer-events: none;
  }

  .compare-handle {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: white;
    border-radius: 50%;
    width: 34px;
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    cursor: col-resize;
  }

  .compare-label {
    position: absolute;
    top: 10px;
    background: rgba(0,0,0,0.52);
    color: white;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    pointer-events: none;
    &--left { left: 10px; }
    &--right { right: 10px; }
  }
}

// ── 编辑历史面板 ──
.edit-history-panel {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.edit-history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  transition: background 0.15s;

  &:hover { background: #f5f7fa; }

  &--active {
    background: #f0f9eb;
    color: #67C23A;
    font-weight: 500;
  }
}

// ── Tabs 样式 ──
.comic-tabs {
  :deep(.el-tabs__header) {
    background: white;
    border-radius: 8px;
    padding: 0 12px;
    margin-bottom: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }

  :deep(.el-tabs__item) {
    height: 48px;
    line-height: 48px;
    font-size: 14px;
  }

  :deep(.el-tabs__active-bar) {
    background: #667eea;
  }

  :deep(.el-tabs__item.is-active) {
    color: #667eea;
  }
}

// ── 结果操作 ──
.result-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}
</style>
