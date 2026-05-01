/**
 * useElapsed —— 工具执行耗时计时器 composable
 */
import { ref, onUnmounted } from 'vue'

export function useElapsed() {
  const elapsedTick = ref(0)
  let elapsedTimer: ReturnType<typeof setInterval> | null = null

  function startElapsedTimer() {
    if (elapsedTimer) return
    elapsedTimer = setInterval(() => { elapsedTick.value++ }, 1000)
  }

  function stopElapsedTimer() {
    if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
  }

  function toolElapsed(timestamp?: string): string {
    if (!timestamp) return ''
    // 触发响应式更新
    void elapsedTick.value
    const sec = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
    if (sec < 1) return ''
    return sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}m${sec % 60}s`
  }

  onUnmounted(() => stopElapsedTimer())

  return { elapsedTick, startElapsedTimer, stopElapsedTimer, toolElapsed }
}
