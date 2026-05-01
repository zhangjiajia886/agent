<template>
  <el-container class="layout-container">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">🎙️</span>
        <span v-if="!collapsed" class="logo-text">TTS 语音平台</span>
      </div>

      <el-menu
        :default-active="$route.path"
        :collapse="collapsed"
        router
        background-color="#1a1a2e"
        text-color="#a0a3b1"
        active-text-color="#ffffff"
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <template #title>仪表盘</template>
        </el-menu-item>
        <el-menu-item index="/tts">
          <el-icon><Microphone /></el-icon>
          <template #title>语音合成 TTS</template>
        </el-menu-item>
        <el-menu-item index="/asr">
          <el-icon><Headset /></el-icon>
          <template #title>语音识别 ASR</template>
        </el-menu-item>
        <el-menu-item index="/voice-models">
          <el-icon><User /></el-icon>
          <template #title>声音模型</template>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>AI 陪聊</template>
        </el-menu-item>
        <el-menu-item index="/podcast">
          <el-icon><Mic /></el-icon>
          <template #title>播客语音</template>
        </el-menu-item>
        <el-menu-item index="/singing">
          <el-icon><VideoCamera /></el-icon>
          <template #title>AI 歌声</template>
        </el-menu-item>
        <el-menu-item index="/digital-human">
          <el-icon><Avatar /></el-icon>
          <template #title>数字人</template>
        </el-menu-item>
        <el-menu-item index="/comic">
          <el-icon><Picture /></el-icon>
          <template #title>漫剧生成</template>
        </el-menu-item>
        <el-menu-item index="/comic-agent">
          <el-icon><MagicStick /></el-icon>
          <template #title>漫剧Agent</template>
        </el-menu-item>
        <el-menu-item index="/workflow">
          <el-icon><Share /></el-icon>
          <template #title>工作流编排</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-button text :icon="collapsed ? Expand : Fold" @click="collapsed = !collapsed" />
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <div class="user-info">
              <el-avatar :size="32" :src="userStore.userInfo?.avatar_url || undefined">
                {{ userStore.userInfo?.username?.[0]?.toUpperCase() }}
              </el-avatar>
              <span>{{ userStore.userInfo?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Odometer, Microphone, Headset, User, Fold, Expand, ArrowDown, SwitchButton, ChatDotRound, Mic, VideoCamera, Avatar, Picture, MagicStick, Share } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()
const collapsed = ref(false)

onMounted(() => {
  if (!userStore.userInfo) {
    userStore.fetchUserInfo().catch(() => router.push('/login'))
  }
})

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped lang="scss">
.layout-container {
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  background: #1a1a2e;
  transition: width 0.3s;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  .sidebar-logo {
    height: 64px;
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    white-space: nowrap;
    overflow: hidden;

    .logo-icon { font-size: 24px; }
    .logo-text {
      font-size: 16px;
      font-weight: 700;
      color: white;
    }
  }

  .sidebar-menu {
    border-right: none;
    flex: 1;

    :deep(.el-menu-item.is-active) {
      background: rgba(102, 126, 234, 0.3) !important;
      border-right: 3px solid #667eea;
    }

    :deep(.el-menu-item:hover) {
      background: rgba(255, 255, 255, 0.05) !important;
    }
  }
}

.header {
  background: white;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);

  .user-info {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 14px;
    color: #303133;
  }
}

.main-content {
  background: #f5f7fa;
  overflow-y: auto;
  padding: 24px;
}
</style>
