<template>
  <div class="input-area">
    <div class="input-toolbar">
      <el-select v-model="model" size="small" placeholder="执行模型" style="width:170px">
        <el-option
          v-for="m in enabledAgentModels"
          :key="m.model_id"
          :label="m.name"
          :value="m.model_id"
        >
          <span>{{ m.name }}</span>
          <el-tag v-if="m.is_default" size="small" type="success" style="margin-left:4px;transform:scale(0.85)">默认</el-tag>
        </el-option>
      </el-select>
      <el-select v-model="style" size="small" placeholder="创作风格" style="width:100px">
        <el-option label="自动识别" value="auto" />
        <el-option label="⚔️ 仙侠" value="xianxia" />
        <el-option label="🖌️ 水墨" value="ink" />
        <el-option label="🎁 盲盒" value="blindbox" />
        <el-option label="🌸 动漫" value="anime" />
        <el-option label="📷 写实" value="realistic" />
      </el-select>
      <el-select v-model="frames" size="small" placeholder="分镜数" style="width:90px">
        <el-option :label="'2 格'" :value="2" />
        <el-option :label="'4 格'" :value="4" />
        <el-option :label="'6 格'" :value="6" />
      </el-select>
      <div class="toolbar-divider"></div>
      <el-tooltip content="开启后 Agent 回复将自动语音播报">
        <div class="toolbar-switch">
          <el-switch v-model="tts" size="small" />
          <span class="toolbar-switch-label">🔊 语音播报</span>
        </div>
      </el-tooltip>
      <el-tooltip content="开启后每格图片自动生成动态视频">
        <div class="toolbar-switch">
          <el-switch v-model="video" size="small" />
          <span class="toolbar-switch-label">🎬 动态化</span>
        </div>
      </el-tooltip>
      <el-tooltip content="新消息的思考过程自动展开">
        <div class="toolbar-switch">
          <el-switch v-model="thinking" size="small" />
          <span class="toolbar-switch-label">🤔 展开分析</span>
        </div>
      </el-tooltip>
      <el-tooltip content="开启后创作类工具（生图/视频/TTS）无需逐个审批">
        <div class="toolbar-switch">
          <el-switch v-model="exec" size="small" active-color="#67C23A" />
          <span class="toolbar-switch-label">⚡ 自动审批</span>
        </div>
      </el-tooltip>
    </div>
    <!-- 图片附件预览 -->
    <div v-if="attachedImages.length" class="attached-images">
      <div v-for="(img, idx) in attachedImages" :key="idx" class="attached-image-item">
        <img :src="img.previewUrl" class="attached-thumb" />
        <div v-if="img.uploading" class="attached-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
        </div>
        <button class="attached-remove" @click="$emit('remove-image', idx)">×</button>
      </div>
    </div>
    <div class="input-row">
      <input
        ref="fileInputRef"
        type="file"
        accept="image/*"
        multiple
        style="display: none"
        @change="$emit('image-select', $event)"
      />
      <el-tooltip content="上传参考图片（最多4张）">
        <el-button
          :icon="PictureFilled"
          circle
          size="small"
          @click="fileInputRef?.click()"
          :disabled="sending || attachedImages.length >= maxImages"
          class="upload-btn"
        />
      </el-tooltip>
      <el-input
        v-model="text"
        type="textarea"
        :rows="2"
        :placeholder="sending ? '系统正在处理中...' : '请输入你的创作需求，按 Enter 发送...'"
        resize="none"
        @keydown.enter.exact.prevent="$emit('send')"
        :disabled="sending"
        class="input-textarea"
      />
      <div class="input-actions">
        <el-button
          type="primary"
          :icon="sending ? Loading : Promotion"
          :loading="sending"
          :disabled="!text.trim() || sending"
          circle
          size="large"
          @click="$emit('send')"
        />
      </div>
    </div>
    <div class="input-hint">
      Enter 发送 · Shift+Enter 换行 · 模型：{{ model }} · 风格：{{ style === 'auto' ? '自动识别' : style }} · 分镜：{{ frames }} 格
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Loading, Promotion, PictureFilled } from '@element-plus/icons-vue'
import type { AttachedImage } from '../types'

const model = defineModel<string>('model', { required: true })
const style = defineModel<string>('style', { required: true })
const frames = defineModel<number>('frames', { required: true })
const tts = defineModel<boolean>('tts', { required: true })
const video = defineModel<boolean>('video', { required: true })
const thinking = defineModel<boolean>('thinking', { required: true })
const exec = defineModel<boolean>('exec', { required: true })
const text = defineModel<string>('text', { required: true })

defineProps<{
  sending: boolean
  attachedImages: AttachedImage[]
  maxImages: number
  enabledAgentModels: { model_id: string; name: string; is_default?: boolean }[]
}>()

defineEmits<{
  (e: 'send'): void
  (e: 'image-select', event: Event): void
  (e: 'remove-image', index: number): void
}>()

const fileInputRef = ref<HTMLInputElement>()
</script>

<style lang="scss">
@import '../styles/input';
</style>
