import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/layout/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' },
      },
      {
        path: 'tts',
        name: 'TTS',
        component: () => import('@/views/tts/TTSView.vue'),
        meta: { title: '语音合成', icon: 'Microphone' },
      },
      {
        path: 'asr',
        name: 'ASR',
        component: () => import('@/views/asr/ASRView.vue'),
        meta: { title: '语音识别', icon: 'Headset' },
      },
      {
        path: 'voice-models',
        name: 'VoiceModels',
        component: () => import('@/views/voice-models/VoiceModelsView.vue'),
        meta: { title: '声音模型', icon: 'User' },
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/chat/ChatView.vue'),
        meta: { title: 'AI 陪聊', icon: 'ChatDotRound' },
      },
      {
        path: 'podcast',
        name: 'Podcast',
        component: () => import('@/views/podcast/PodcastView.vue'),
        meta: { title: '播客语音', icon: 'Mic' },
      },
      {
        path: 'singing',
        name: 'Singing',
        component: () => import('@/views/singing/SingingView.vue'),
        meta: { title: 'AI 歌声', icon: 'VideoCamera' },
      },
      {
        path: 'digital-human',
        name: 'DigitalHuman',
        component: () => import('@/views/digital-human/DigitalHumanView.vue'),
        meta: { title: '数字人', icon: 'Avatar' },
      },
      {
        path: 'comic',
        name: 'Comic',
        component: () => import('@/views/comic/ComicView.vue'),
        meta: { title: '漫剧生成', icon: 'Picture' },
      },
      {
        path: 'comic-agent',
        name: 'ComicAgent',
        component: () => import('@/views/comic-agent/ComicAgentView.vue'),
        meta: { title: '漫剧Agent', icon: 'MagicStick' },
      },
      {
        path: 'workflow',
        name: 'Workflow',
        component: () => import('@/views/workflow/WorkflowEditorView.vue'),
        meta: { title: '工作流编排', icon: 'Share' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth !== false && !token) {
    return { name: 'Login' }
  }
  if (to.name === 'Login' && token) {
    return { name: 'Dashboard' }
  }
})

export default router
