<template>
  <section v-if="activeTask" class="agent-workspace agent-workspace--narrative">
    <section class="narrative-block narrative-block--primary">
      <div class="block-marker">01</div>
      <div class="block-main">
        <div class="block-head">
          <div>
            <span class="section-kicker">Requirement Understanding</span>
            <h2>需求理解</h2>
          </div>
          <el-tag :type="taskStatusType(activeTask.status)" effect="dark">
            {{ taskStatusLabel(activeTask.status) }}
          </el-tag>
        </div>
        <div class="requirement-card">
          <div class="requirement-label">用户需求</div>
          <div class="requirement-text">{{ activeTask.userRequest }}</div>
        </div>
        <div class="understanding-grid">
          <div>
            <span>识别类型</span>
            <strong>{{ activeTask.intent }}</strong>
          </div>
          <div>
            <span>目标摘要</span>
            <strong>{{ activeTask.analysis }}</strong>
          </div>
          <div>
            <span>当前状态</span>
            <strong>{{ activeTask.currentStage }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section v-if="showPlanBlock" class="narrative-block">
      <div class="block-marker">02</div>
      <div class="block-main">
        <div class="block-head">
          <div>
            <span class="section-kicker">Plan</span>
            <h2>执行规划</h2>
          </div>
          <span class="progress-text">{{ completedStepCount }}/{{ activeTask.steps.length }} 已完成</span>
        </div>
        <div class="plan-list">
          <div v-for="(step, index) in visiblePlanSteps" :key="step.id" :class="['plan-row', `plan-row--${step.status}`]">
            <span class="plan-index">{{ index + 1 }}</span>
            <div class="plan-copy">
              <strong>{{ step.title }}</strong>
              <p>{{ step.description }}</p>
            </div>
            <el-tag size="small" :type="stepStatusType(step.status)">{{ stepStatusLabel(step.status) }}</el-tag>
          </div>
        </div>
      </div>
    </section>

    <section v-if="showExecutionBlock" class="narrative-block">
      <div class="block-marker">03</div>
      <div class="block-main">
        <div class="block-head">
          <div>
            <span class="section-kicker">Execution</span>
            <h2>执行过程</h2>
          </div>
        </div>
        <div class="execution-flow">
          <article
            v-for="(step, index) in executableSteps"
            :key="step.id"
            :class="['execution-card', `execution-card--${step.status}`]"
          >
            <div class="execution-card-head">
              <div>
                <span>Step {{ index + 1 }}</span>
                <h3>{{ step.title }}</h3>
              </div>
              <el-tag size="small" :type="stepStatusType(step.status)">{{ stepStatusLabel(step.status) }}</el-tag>
            </div>
            <p>{{ step.description }}</p>
            <div v-if="step.startedAt || step.finishedAt" class="step-meta">
              <span v-if="step.startedAt">开始 {{ formatTime(step.startedAt) }}</span>
              <span v-if="step.finishedAt">完成 {{ formatTime(step.finishedAt) }}</span>
            </div>
            <div v-if="step.status === 'awaiting_approval'" class="inline-approval">
              <el-button type="primary" size="small" @click="$emit('approve-step', step, 'approve')">确认执行</el-button>
              <el-button type="danger" size="small" plain @click="$emit('approve-step', step, 'reject')">取消操作</el-button>
            </div>
            <el-collapse v-if="stepLogs(step).length" class="compact-tool-collapse">
              <el-collapse-item>
                <template #title>
                  <span>工具调用明细已压缩 · {{ stepLogs(step).length }} 条</span>
                </template>
                <div class="compact-log-list">
                  <div v-for="log in stepLogs(step)" :key="log.id" class="compact-log-item">
                    <div class="compact-log-title">
                      <span>{{ log.title }}</span>
                      <em>{{ formatTime(log.timestamp) }}</em>
                    </div>
                    <pre>{{ compactLogContent(log.content) }}</pre>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </article>
        </div>
      </div>
    </section>

    <section v-if="showResultBlock" class="narrative-block">
      <div class="block-marker">04</div>
      <div class="block-main">
        <div class="block-head">
          <div>
            <span class="section-kicker">Result Analysis</span>
            <h2>结果分析</h2>
          </div>
        </div>
        <div class="result-strip">
          <div v-for="item in activeTask.artifacts" :key="item.id" class="result-card">
            <el-image
              v-if="item.type === 'image'"
              :src="item.url"
              fit="cover"
              class="result-preview"
              :preview-src-list="allImageUrls"
              :initial-index="allImageUrls.indexOf(item.url)"
            />
            <video v-else-if="item.type === 'video'" :src="item.url" controls class="result-video"></video>
            <div v-else class="result-file">{{ item.type === 'audio' ? '音频产物' : '文件产物' }}</div>
            <div class="result-copy">
              <strong>{{ item.title }}</strong>
              <span>{{ item.fromStep }}</span>
            </div>
          </div>
        </div>
        <div class="analysis-panel">
          {{ resultAnalysisText }}
        </div>
      </div>
    </section>

    <section v-if="showFinalBlock" class="narrative-block narrative-block--final">
      <div class="block-marker">05</div>
      <div class="block-main">
        <div class="block-head">
          <div>
            <span class="section-kicker">Final Report</span>
            <h2>总结报告</h2>
          </div>
        </div>
        <div class="final-report" v-html="renderMarkdown(finalReportText)"></div>
        <div v-if="visibleAssistantMessages.length" class="assistant-final-messages">
          <div v-for="msg in visibleAssistantMessages" :key="msg.id" class="summary-message">
            <div v-if="msg.content" v-html="renderMarkdown(msg.content || '')"></div>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import type { AgentTaskViewModel, TaskStep, TaskLog } from '../types'
import type { AgentMessage } from '@/api/comic-agent'
import { taskStatusLabel, taskStatusType, stepStatusLabel, stepStatusType } from '../composables'
import { renderMarkdown, formatTime } from '../utils'

defineProps<{
  activeTask: AgentTaskViewModel | null
  showPlanBlock: boolean
  showExecutionBlock: boolean
  showResultBlock: boolean
  showFinalBlock: boolean
  completedStepCount: number
  visiblePlanSteps: TaskStep[]
  executableSteps: TaskStep[]
  allImageUrls: string[]
  resultAnalysisText: string
  finalReportText: string
  visibleAssistantMessages: AgentMessage[]
  stepLogs: (step: TaskStep) => TaskLog[]
  compactLogContent: (content: string) => string
}>()

defineEmits<{
  (e: 'approve-step', step: TaskStep, action: 'approve' | 'reject'): void
}>()
</script>

<style lang="scss">
@import '../styles/workspace';
</style>
