/**
 * useChat —— 消息管理 + WebSocket 事件处理 composable
 * 从 ComicAgentView.vue 提取的消息列表、事件分发、发送逻辑和相关计算属性。
 */
import { ref, computed, nextTick, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ComicAgentWS,
  type AgentMessage, type AgentEvent,
} from '@/api/comic-agent'
import type { TaskStep, AttachedImage } from '../types'
import {
  toolDisplayName,
  taskStatusLabel,
  mapServerTaskStatus,
} from './useTask'
import type { useTask as UseTaskFn } from './useTask'
import type { useElapsed as UseElapsedFn } from './useElapsed'

type TaskReturn = ReturnType<typeof UseTaskFn>
type ElapsedReturn = ReturnType<typeof UseElapsedFn>

interface UseChatOptions {
  task: TaskReturn
  elapsed: ElapsedReturn
  showThinking: Ref<boolean>
  messagesRef: Ref<HTMLElement | undefined>
}

export function useChat(opts: UseChatOptions) {
  const { task, elapsed, showThinking, messagesRef } = opts
  const {
    activeTask, createTask,
    addTaskLog, stepLogs,
    findTaskStepByTool, ensureToolStep, addArtifact,
    upsertServerStep, upsertServerArtifact,
  } = task
  const { startElapsedTimer, stopElapsedTimer } = elapsed

  // ──────────── 核心状态 ────────────
  const messages = ref<AgentMessage[]>([])
  const inputText = ref('')
  const sending = ref(false)
  const streamingText = ref('')
  const budgetUsage = ref<Record<string, any> | null>(null)
  let msgIdCounter = 0

  // ──────────── WebSocket 实例 ────────────
  const agentWS = new ComicAgentWS()

  // ──────────── 滚动 ────────────
  function scrollToBottom() {
    nextTick(() => {
      if (messagesRef.value) {
        messagesRef.value.scrollTop = messagesRef.value.scrollHeight
      }
    })
  }

  // ──────────── 消息查找 ────────────
  function _lastAssistantMsg() {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].type === 'assistant') return messages.value[i]
      if (messages.value[i].type === 'user') return null
    }
    return null
  }

  function _lastThinkingMsg() {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].type === 'thinking') return messages.value[i]
      if (messages.value[i].type === 'assistant') return null
    }
    return null
  }

  // ──────────── 计算属性 ────────────
  const allImageUrls = computed(() => {
    const urls: string[] = []
    for (const m of messages.value) {
      if (m.type === 'assistant' && m.images?.length) urls.push(...m.images)
      if (m.type === 'tool_done' && m.imageUrl) urls.push(m.imageUrl)
    }
    activeTask.value?.artifacts
      .filter(item => item.type === 'image')
      .forEach(item => {
        if (!urls.includes(item.url)) urls.push(item.url)
      })
    return urls
  })

  const timelineMessages = computed(() => {
    if (!activeTask.value) return messages.value
    return messages.value.filter(m => m.type === 'error')
  })

  const visibleAssistantMessages = computed(() =>
    messages.value.filter(m => m.type === 'assistant' && ((m.content || '').trim() || m.images?.length || m.videos?.length))
  )

  const completedStepCount = computed(() =>
    activeTask.value?.steps.filter(s => s.status === 'completed').length || 0
  )

  const hasAgentProgress = computed(() =>
    !!activeTask.value && (
      activeTask.value.logs.length > 0 ||
      activeTask.value.artifacts.length > 0 ||
      activeTask.value.steps.some(step => !step.id.startsWith('analysis-') && step.status !== 'pending')
    )
  )

  const visiblePlanSteps = computed(() =>
    hasAgentProgress.value ? activeTask.value?.steps.filter(step => !step.id.startsWith('analysis-')) || [] : []
  )

  const executableSteps = computed(() =>
    activeTask.value?.steps.filter(s =>
      !s.id.startsWith('analysis-') && (s.status !== 'pending' || !!s.startedAt || !!s.finishedAt || !!stepLogs(s).length)
    ) || []
  )

  const showPlanBlock = computed(() => visiblePlanSteps.value.length > 0)
  const showExecutionBlock = computed(() => executableSteps.value.length > 0)
  const showResultBlock = computed(() => !!activeTask.value?.artifacts.length)
  const showFinalBlock = computed(() =>
    !!activeTask.value && ['completed', 'failed', 'canceled'].includes(activeTask.value.status)
  )

  const resultAnalysisText = computed(() => {
    if (!activeTask.value) return ''
    if (!activeTask.value.artifacts.length) return '当前还没有可分析的产物。结果生成后，将在这里对产物类型、来源步骤和后续可执行动作进行汇总分析。'
    const imageCount = activeTask.value.artifacts.filter(a => a.type === 'image').length
    const videoCount = activeTask.value.artifacts.filter(a => a.type === 'video').length
    const audioCount = activeTask.value.artifacts.filter(a => a.type === 'audio').length
    const parts = [
      imageCount ? `图像产物 ${imageCount} 项` : '',
      videoCount ? `视频产物 ${videoCount} 项` : '',
      audioCount ? `音频产物 ${audioCount} 项` : '',
    ].filter(Boolean).join('、')
    return `已完成产物汇总：${parts || '暂无媒体产物'}。系统将基于当前结果继续判断是否需要下一轮规划、编辑、动态化或最终收尾。`
  })

  const finalReportText = computed(() => {
    if (!activeTask.value) return ''
    const status = taskStatusLabel(activeTask.value.status)
    const completed = completedStepCount.value
    const total = activeTask.value.steps.length
    if (activeTask.value.status !== 'completed' && activeTask.value.status !== 'failed' && activeTask.value.status !== 'canceled') {
      return `**任务状态**：${status}\n\n**当前进度**：${completed}/${total} 个规划节点已完成。\n\n最终总结会在没有新的工具调用后生成，并固定停留在页面最下方。`
    }
    return `**任务状态**：${status}\n\n**需求理解**：${activeTask.value.analysis}\n\n**执行结果**：完成 ${completed}/${total} 个规划节点，产出 ${activeTask.value.artifacts.length} 项结果。\n\n**总结**：本轮任务已经结束，工具调用已停止，结果与执行记录已归档在上方对应模块。`
  })

  // ──────────── 审批 ────────────
  function approveTaskStep(step: TaskStep, action: 'approve' | 'reject') {
    step.status = action === 'approve' ? 'running' : 'canceled'
    if (action === 'reject' && activeTask.value) activeTask.value.status = 'canceled'
    agentWS.sendRaw({ action, tool_call_id: step.toolCallId })
  }

  function handleToolApproval(msg: AgentMessage, action: 'approve' | 'reject') {
    msg.confirmed = action
    const step = findTaskStepByTool(msg.tool, msg.toolCallId)
    if (step) {
      step.status = action === 'approve' ? 'running' : 'canceled'
      if (action === 'reject' && activeTask.value) activeTask.value.status = 'canceled'
    }
    agentWS.sendRaw({ action, tool_call_id: msg.toolCallId })
  }

  // ──────────── 事件处理 ────────────
  function handleAgentEvent(event: AgentEvent) {
    const now = new Date().toISOString()

    switch (event.type) {
      case 'task_created':
        if (activeTask.value) {
          activeTask.value.taskUid = event.task_uid
          activeTask.value.status = mapServerTaskStatus(event.task?.status as string | undefined)
          activeTask.value.currentStage = '后端任务图已创建。'
          activeTask.value.steps = []
          ;(event.steps || []).forEach(step => upsertServerStep(step))
          addTaskLog('任务图创建', `后端已创建 ${event.steps?.length || 0} 个步骤。`)
        }
        break

      case 'task_update':
        if (activeTask.value) {
          activeTask.value.status = mapServerTaskStatus(event.status)
          activeTask.value.currentStage = event.content || (event as any).message || event.status || '任务状态已更新。'
          addTaskLog('任务状态更新', activeTask.value.currentStage)
        }
        break

      case 'step_update':
        if (event.step) {
          upsertServerStep(event.step)
          addTaskLog('步骤状态更新', `${event.step.title || event.step_uid}: ${event.step.status || ''}`, event.step_uid)
        }
        break

      case 'artifact_created':
        if (event.artifact) {
          upsertServerArtifact(event.artifact, event.step_uid)
          addTaskLog('产物已登记', event.artifact.url || event.artifact.title || '后端已登记产物。', event.step_uid)
        }
        break

      case 'thinking': {
        addTaskLog('Agent 分析', event.content)
        if (activeTask.value && event.content) {
          activeTask.value.currentStage = event.content.length > 80 ? `${event.content.slice(0, 80)}...` : event.content
        }
        const last = _lastThinkingMsg()
        if (!activeTask.value && last && !last.isFinished) {
          last.content = (last.content || '') + (event.content || '')
        } else if (!activeTask.value) {
          messages.value.push({
            id: ++msgIdCounter, type: 'thinking',
            content: event.content, timestamp: now,
            expanded: showThinking.value,
          })
        }
        break
      }

      case 'delta': {
        const last = _lastAssistantMsg()
        if (last && !last.isFinished) {
          last.content = (last.content || '') + (event.content || '')
        } else {
          messages.value.push({
            id: ++msgIdCounter, type: 'assistant',
            content: event.content || '', images: [], videos: [], timestamp: now,
          })
        }
        break
      }

      case 'text':
        messages.value.push({
          id: ++msgIdCounter, type: 'assistant',
          content: event.content, images: [], videos: [], timestamp: now,
        })
        break

      case 'done': {
        const last = _lastAssistantMsg()
        if (last) last.isFinished = true
        const lastThinking = _lastThinkingMsg()
        if (lastThinking) lastThinking.isFinished = true
        sending.value = false
        if (event.metadata?.budget_usage) {
          budgetUsage.value = event.metadata.budget_usage as Record<string, any>
        }
        if (activeTask.value && event.final_report) {
          activeTask.value.finalReport = event.final_report
          activeTask.value.status = mapServerTaskStatus(event.status || event.final_report.status as string | undefined)
          activeTask.value.currentStage = event.final_report.summary as string || '后端最终报告已生成。'
          ;((event.final_report.artifacts as Record<string, any>[] | undefined) || []).forEach(item => upsertServerArtifact(item))
          addTaskLog('最终报告', activeTask.value.currentStage)
          break
        }
        if (activeTask.value && !['failed', 'canceled'].includes(activeTask.value.status)) {
          const hasCompletedWork = activeTask.value.steps.some(s => s.status === 'completed') || activeTask.value.artifacts.length > 0
          const hasRunningWork = activeTask.value.steps.some(s => s.status === 'running' || s.status === 'awaiting_approval')
          const assistantText = visibleAssistantMessages.value.map(m => m.content || '').join('\n')
          const hasIncompleteText = /(剩余\s*TODO|尚未完成|未完成|还需要|需要继续|先执行第?\s*[1-9一二三四五六]?步)/.test(assistantText)
          if (hasCompletedWork || !hasRunningWork) {
            activeTask.value.status = hasCompletedWork && !hasIncompleteText ? 'completed' : 'failed'
            activeTask.value.currentStage = hasCompletedWork
              ? (hasIncompleteText ? '任务未完成：模型列出了剩余 TODO，但没有继续调用工具。' : '任务已完成，结果与过程记录已汇总。')
              : '本轮没有检测到实际工具执行，请重新发送并明确要求调用工具。'
            if (hasCompletedWork && !hasIncompleteText) {
              activeTask.value.steps
                .filter(s => s.status === 'running' || s.status === 'awaiting_approval')
                .forEach(s => {
                  s.status = 'completed'
                  s.finishedAt = s.finishedAt || now
                })
            }
          }
        }
        break
      }

      case 'incomplete':
        sending.value = false
        if (activeTask.value) {
          activeTask.value.status = 'failed'
          activeTask.value.currentStage = event.content || '任务未完成：仍有 TODO 未执行。'
          addTaskLog('任务未完成', event.content || '仍有 TODO 未执行。')
        }
        messages.value.push({
          id: ++msgIdCounter, type: 'error',
          content: event.content || '任务未完成：仍有 TODO 未执行。', timestamp: now,
        })
        break

      case 'tool_confirm':
        { const lastTh = _lastThinkingMsg(); if (lastTh) lastTh.isFinished = true }
        if (activeTask.value) {
          const step = ensureToolStep(event.tool, event.description, event.tool_call_id)
          if (step) {
            step.status = 'awaiting_approval'
            step.startedAt = step.startedAt || now
          }
          activeTask.value.status = 'awaiting_approval'
          activeTask.value.currentStage = `等待确认：${step?.title || toolDisplayName(event.tool)}`
          addTaskLog('等待用户确认', event.description || toolDisplayName(event.tool), step?.id)
        }
        messages.value.push({
          id: ++msgIdCounter, type: 'tool_confirm',
          tool: event.tool, toolInput: event.input,
          description: event.description,
          toolCallId: event.tool_call_id,
          timestamp: now,
        })
        break

      case 'tool_start':
        if (activeTask.value) {
          const step = ensureToolStep(event.tool, event.description, event.tool_call_id)
          if (step) {
            step.status = 'running'
            step.startedAt = step.startedAt || now
          }
          activeTask.value.status = 'running'
          activeTask.value.currentStage = `正在执行：${step?.title || toolDisplayName(event.tool)}`
          addTaskLog('开始执行工具', event.description || toolDisplayName(event.tool), step?.id)
        }
        messages.value.push({
          id: ++msgIdCounter, type: 'tool_start',
          tool: event.tool, toolInput: event.input, description: event.description, timestamp: now,
        })
        startElapsedTimer()
        break

      case 'tool_done': {
        stopElapsedTimer()
        let frameIdx: number | undefined
        try { frameIdx = event.result ? JSON.parse(event.result).frame : undefined } catch { /* ignore */ }

        let startIdx = -1
        if (frameIdx !== undefined) {
          for (let i = messages.value.length - 1; i >= 0; i--) {
            const m = messages.value[i]
            if (m.type === 'tool_start' && m.tool === event.tool && m.toolInput?.frame === frameIdx) {
              startIdx = i; break
            }
          }
        }
        if (startIdx < 0) {
          for (let i = messages.value.length - 1; i >= 0; i--) {
            if (messages.value[i].type === 'tool_start' && messages.value[i].tool === event.tool) {
              startIdx = i; break
            }
          }
        }
        if (startIdx >= 0) messages.value.splice(startIdx, 1)

        const imageUrl = event.image_url
          || (event.result || '').match(/(\/uploads\/\S+\.(?:png|jpg|jpeg|webp))/i)?.[1]
          || (event.result || '').match(/(https?:\/\/\S+\.(?:png|jpg|jpeg|webp))/i)?.[1]
        const videoUrl = event.video_url
          || (event.result || '').match(/(\/uploads\/\S+\.(?:mp4|webm))/i)?.[1]
        const audioUrl = event.audio_url
          || (event.result || '').match(/(\/uploads\/\S+\.(?:mp3|wav))/i)?.[1]

        if (activeTask.value) {
          const step = findTaskStepByTool(event.tool)
          if (event.step_uid && event.standard_result?.artifacts) {
            ;(event.standard_result.artifacts as Record<string, any>[]).forEach(item => upsertServerArtifact(item, event.step_uid))
          }
          if (step) {
            const failed = !!(event.result || '').match(/"error"|"status":\s*"failed"|用户拒绝执行/)
            step.status = failed ? 'failed' : 'completed'
            step.finishedAt = now
            activeTask.value.status = failed ? 'failed' : 'running'
            activeTask.value.currentStage = failed ? `${step.title} 执行失败` : `${step.title} 已完成`
            addTaskLog(failed ? '工具执行失败' : '工具执行完成', event.result || step.title, step.id)
            if (imageUrl) addArtifact('image', imageUrl, step.title)
            if (videoUrl) addArtifact('video', videoUrl, step.title)
            if (audioUrl) addArtifact('audio', audioUrl, step.title)
          }
        }

        if (imageUrl) {
          const aMsg = _lastAssistantMsg()
          if (aMsg) {
            if (!aMsg.images) aMsg.images = []
            aMsg.images.push(imageUrl)
          } else {
            messages.value.push({
              id: ++msgIdCounter, type: 'assistant',
              content: '', images: [imageUrl], timestamp: now,
            })
          }
        } else if (videoUrl) {
          const aMsg = _lastAssistantMsg()
          if (aMsg) {
            if (!aMsg.videos) aMsg.videos = []
            aMsg.videos.push(videoUrl)
          }
        } else if (audioUrl) {
          messages.value.push({
            id: ++msgIdCounter, type: 'assistant',
            content: `🔊 语音已生成：[播放](${audioUrl})`, timestamp: now,
          })
        } else {
          messages.value.push({
            id: ++msgIdCounter, type: 'tool_done',
            tool: event.tool, toolResult: event.result,
            duration: event.duration, timestamp: now,
          })
        }
        break
      }

      case 'error':
        if (activeTask.value) {
          activeTask.value.status = 'failed'
          activeTask.value.currentStage = event.content || '执行过程中发生错误。'
          addTaskLog('执行错误', event.content)
        }
        messages.value.push({
          id: ++msgIdCounter, type: 'error',
          content: event.content, timestamp: now,
        })
        break
    }
    scrollToBottom()
  }

  // ──────────── 发送 ────────────
  interface SendParams {
    selectedStyle: Ref<string>
    selectedFrames: Ref<number>
    selectedModel: Ref<string>
    ttsEnabled: Ref<boolean>
    autoVideo: Ref<boolean>
    autoExec: Ref<boolean>
    attachedImages: Ref<AttachedImage[]>
  }

  function handleSend(params: SendParams) {
    const text = inputText.value.trim()
    if (!text || sending.value) return
    inputText.value = ''
    sendToAgent(text, params)
  }

  function sendQuickPrompt(text: string, params: SendParams) {
    if (sending.value) return
    sendToAgent(text, params)
  }

  async function sendToAgent(text: string, params: SendParams) {
    createTask(text)
    messages.value.push({
      id: ++msgIdCounter,
      type: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    })
    scrollToBottom()

    sending.value = true

    try {
      if (!agentWS.connected) {
        await agentWS.connect(
          (event: AgentEvent) => handleAgentEvent(event),
          () => {
            sending.value = false
            messages.value.forEach(m => {
              if (m.type === 'thinking' || m.type === 'assistant') m.isFinished = true
            })
            scrollToBottom()
          },
          0,
          {
            autoReconnect: true,
            onReconnect: () => {
              const taskUid = agentWS.lastTaskUid
              if (taskUid) {
                agentWS.replayEvents(taskUid, handleAgentEvent).catch(() => {})
              }
            },
          },
        )
      }

      const imagePaths = params.attachedImages.value
        .filter(img => img.uploaded)
        .map(img => img.uploaded!.file_path)

      agentWS.send(text, {
        style: params.selectedStyle.value,
        frames: params.selectedFrames.value,
        model: params.selectedModel.value,
        tts: params.ttsEnabled.value,
        autoVideo: params.autoVideo.value,
        auto_mode: params.autoExec.value,
        image_paths: imagePaths.length > 0 ? imagePaths : undefined,
      })

      params.attachedImages.value.forEach(img => URL.revokeObjectURL(img.previewUrl))
      params.attachedImages.value = []
    } catch (e) {
      messages.value.push({
        id: ++msgIdCounter,
        type: 'error',
        content: '连接失败: ' + (e instanceof Error ? e.message : '未知错误'),
        timestamp: new Date().toISOString(),
      })
      sending.value = false
      scrollToBottom()
    }
  }

  // ──────────── 操作 ────────────
  function clearChat() {
    agentWS.disconnect()
    messages.value = []
    activeTask.value = null
    streamingText.value = ''
    sending.value = false
    msgIdCounter = 0
  }

  async function downloadAllImages() {
    for (let i = 0; i < allImageUrls.value.length; i++) {
      const url = allImageUrls.value[i]
      try {
        const resp = await fetch(url)
        const blob = await resp.blob()
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `comic_frame_${i + 1}.png`
        a.click()
        URL.revokeObjectURL(a.href)
        await new Promise(r => setTimeout(r, 300))
      } catch {
        ElMessage.error(`下载第 ${i + 1} 张失败`)
      }
    }
  }

  function disconnect() {
    agentWS.disconnect()
    sending.value = false
  }

  return {
    // 状态
    messages,
    inputText,
    sending,
    streamingText,
    agentWS,
    // 计算属性
    allImageUrls,
    timelineMessages,
    visibleAssistantMessages,
    completedStepCount,
    hasAgentProgress,
    visiblePlanSteps,
    executableSteps,
    showPlanBlock,
    showExecutionBlock,
    showResultBlock,
    showFinalBlock,
    resultAnalysisText,
    finalReportText,
    budgetUsage,
    // 方法
    scrollToBottom,
    approveTaskStep,
    handleToolApproval,
    handleSend,
    sendQuickPrompt,
    clearChat,
    downloadAllImages,
    disconnect,
  }
}
