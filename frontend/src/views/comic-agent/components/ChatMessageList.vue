<template>
  <!-- 消息列表 -->
  <div
    v-for="msg in timelineMessages"
    :key="msg.id"
    class="message-row"
    :class="msg.type"
  >
    <!-- 用户消息 -->
    <template v-if="msg.type === 'user'">
      <div class="msg-bubble user-bubble">
        <div class="msg-content">{{ msg.content }}</div>
        <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
      </div>
      <div class="msg-avatar user-avatar">👤</div>
    </template>

    <!-- Agent 文字回复 + 内联图片/视频 -->
    <template v-else-if="msg.type === 'assistant'">
      <div class="msg-avatar bot-avatar">🤖</div>
      <div class="msg-bubble bot-bubble">
        <div v-if="msg.content" class="msg-content" v-html="renderMarkdown(msg.content || '')"></div>
        <!-- 内联图片网格 -->
        <div v-if="msg.images?.length" class="inline-images">
          <el-image
            v-for="(url, i) in msg.images"
            :key="i"
            :src="url"
            fit="cover"
            class="inline-img"
            :preview-src-list="allImageUrls"
            :initial-index="allImageUrls.indexOf(url)"
            lazy
          >
            <template #placeholder>
              <div class="img-loading"><el-icon class="is-loading"><Loading /></el-icon></div>
            </template>
          </el-image>
        </div>
        <!-- 内联视频 -->
        <div v-if="msg.videos?.length" class="inline-videos">
          <video v-for="(url, i) in msg.videos" :key="i" :src="url" controls class="inline-video" />
        </div>
        <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
      </div>
    </template>

    <!-- 思考过程（始终可折叠显示） -->
    <template v-else-if="msg.type === 'thinking'">
      <div class="msg-avatar bot-avatar" style="opacity:0.5">🤔</div>
      <div :class="['thinking-bubble', { 'thinking-done': msg.isFinished }]">
        <!-- 可折叠头部 -->
        <div class="thinking-collapse-header" @click="msg.expanded = !msg.expanded">
          <template v-if="!msg.isFinished">
            <span class="thinking-dot"></span>
            <span class="thinking-dot"></span>
            <span class="thinking-dot"></span>
            <span style="margin-left:6px;font-size:11px;color:#909399">思考中...</span>
          </template>
          <template v-else>
            <span style="color:#67C23A;font-size:12px">已完成分析</span>
            <span style="margin-left:6px;font-size:11px;color:#909399">共 {{ (msg.content||'').split('\n').length }} 行</span>
          </template>
          <span style="margin-left:auto;font-size:11px;color:#c0c4cc">{{ msg.expanded ? '▲ 收起详情' : '▼ 查看详情' }}</span>
        </div>
        <div v-show="msg.expanded" class="thinking-content">{{ msg.content }}</div>
      </div>
    </template>

    <!-- 工具开始执行 -->
    <template v-else-if="msg.type === 'tool_start'">
      <div class="msg-avatar bot-avatar">🤖</div>
      <div class="tool-card tool-card--running">
        <div class="tool-card-header">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span class="tool-name">{{ toolDisplayName(msg.tool) }}</span>
          <el-tag size="small" type="warning">处理中</el-tag>
          <span class="tool-elapsed">{{ toolElapsed(msg.timestamp) }}</span>
        </div>
        <div class="tool-action-desc" v-if="msg.description">{{ msg.description }}</div>
        <div class="tool-hint" v-if="!msg.description && toolHint(msg.tool)">{{ toolHint(msg.tool) }}</div>
        <div class="tool-params" v-if="msg.toolInput">
          <div v-for="(val, key) in compactParams(msg.toolInput)" :key="key" class="tool-param-row">
            <span class="tool-param-key">{{ key }}:</span>
            <span class="tool-param-val">{{ val }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- 工具确认请求 -->
    <template v-else-if="msg.type === 'tool_confirm'">
      <div class="msg-avatar bot-avatar">🤖</div>
      <div class="tool-card tool-card--confirm">
        <div class="tool-card-header">
          <el-icon color="#E6A23C"><Warning /></el-icon>
          <span class="tool-name">{{ toolDisplayName(msg.tool) }}</span>
          <el-tag size="small" type="warning">待你确认</el-tag>
        </div>
        <div class="tool-action-desc" v-if="msg.description">{{ msg.description }}</div>
        <div class="tool-params" v-if="msg.toolInput">
          <div v-for="(val, key) in compactParams(msg.toolInput)" :key="key" class="tool-param-row">
            <span class="tool-param-key">{{ key }}:</span>
            <span class="tool-param-val">{{ val }}</span>
          </div>
        </div>
        <div class="tool-confirm-actions" v-if="!msg.confirmed">
          <el-button type="primary" size="small" @click="$emit('tool-approval', msg, 'approve')">
            确认执行
          </el-button>
          <el-button type="danger" size="small" plain @click="$emit('tool-approval', msg, 'reject')">
            取消本次操作
          </el-button>
        </div>
        <div v-else class="tool-confirm-result">
          <el-tag :type="msg.confirmed === 'approve' ? 'success' : 'danger'" size="small">
            {{ msg.confirmed === 'approve' ? '已确认执行' : '已取消' }}
          </el-tag>
        </div>
      </div>
    </template>

    <!-- 工具执行完成 -->
    <template v-else-if="msg.type === 'tool_done'">
      <div class="msg-avatar bot-avatar">🤖</div>
      <div class="tool-card tool-card--done">
        <div class="tool-card-header">
          <el-icon color="#67C23A"><CircleCheck /></el-icon>
          <span class="tool-name">{{ toolDisplayName(msg.tool) }}</span>
          <el-tag size="small" type="success">已完成</el-tag>
          <span v-if="msg.duration" class="tool-duration">{{ msg.duration.toFixed(1) }}s</span>
        </div>
        <!-- 图片预览 -->
        <div v-if="msg.imageUrl" class="tool-image-wrap">
          <el-image
            :src="msg.imageUrl"
            fit="cover"
            class="tool-image"
            :preview-src-list="allImageUrls"
            :initial-index="allImageUrls.indexOf(msg.imageUrl)"
            lazy
          >
            <template #placeholder>
              <div class="img-loading"><el-icon class="is-loading"><Loading /></el-icon></div>
            </template>
          </el-image>
        </div>
        <!-- 视频预览 -->
        <div v-if="msg.videoUrl" class="tool-video-wrap">
          <video :src="msg.videoUrl" controls class="tool-video"></video>
        </div>
        <!-- 文字结果 -->
        <div v-if="msg.toolResult && !msg.imageUrl && !msg.videoUrl" class="tool-result-text">
          {{ msg.toolResult }}
        </div>
      </div>
    </template>

    <!-- 错误 -->
    <template v-else-if="msg.type === 'error'">
      <div class="msg-avatar bot-avatar">🤖</div>
      <el-alert :title="msg.content || '未知错误'" type="error" show-icon :closable="false" class="error-alert" />
    </template>
  </div>

  <!-- 流式打字中 -->
  <div v-if="streamingText" class="message-row assistant">
    <div class="msg-avatar bot-avatar">🤖</div>
    <div class="msg-bubble bot-bubble">
      <div class="msg-content" v-html="renderMarkdown(streamingText)"></div>
      <span class="cursor-blink">▋</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Loading, CircleCheck, Warning } from '@element-plus/icons-vue'
import type { AgentMessage } from '@/api/comic-agent'
import { toolDisplayName, toolHint } from '../composables'
import { renderMarkdown, formatTime, compactParams } from '../utils'

defineProps<{
  timelineMessages: AgentMessage[]
  streamingText: string
  allImageUrls: string[]
  toolElapsed: (timestamp?: string) => string
}>()

defineEmits<{
  (e: 'tool-approval', msg: AgentMessage, action: 'approve' | 'reject'): void
}>()
</script>
