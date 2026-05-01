<template>
  <div class="voice-models-page">
    <div class="page-header">
      <h1>🎭 声音模型管理</h1>
      <p>上传音频样本克隆声音，创建专属声音模型用于 TTS 合成</p>
    </div>

    <el-card shadow="hover" class="toolbar-card">
      <div class="toolbar">
        <el-input v-model="searchText" placeholder="搜索声音模型..." clearable :prefix-icon="Search" style="width: 260px;" />
        <div style="display:flex;gap:8px;">
          <el-button :icon="Discover" @click="openDiscoverDialog">发现官方音色</el-button>
          <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">创建声音模型</el-button>
        </div>
      </div>
    </el-card>

    <!-- 模型列表 -->
    <div v-loading="loading" class="models-grid">
      <el-empty v-if="!loading && filteredModels.length === 0" description="暂无声音模型，点击上方按钮创建" />

      <el-row :gutter="20">
        <el-col v-for="model in filteredModels" :key="model.id" :xs="24" :sm="12" :lg="8" :xl="6">
          <el-card shadow="hover" class="model-card">
            <div class="model-header">
              <div class="model-avatar">
                {{ model.title[0]?.toUpperCase() }}
              </div>
              <div class="model-info">
                <div class="model-title">{{ model.title }}</div>
                <div class="model-meta">
                  <el-tag size="small" :type="model.visibility === 'public' ? 'success' : 'info'">
                    {{ model.visibility === 'public' ? '公开' : '私有' }}
                  </el-tag>
                  <span class="lang-tag">{{ model.language === 'zh' ? '中文' : '英文' }}</span>
                </div>
              </div>
            </div>

            <div v-if="model.description" class="model-desc">{{ model.description }}</div>

            <div class="model-stats">
              <div class="stat-item">
                <span class="stat-val">{{ model.usage_count }}</span>
                <span class="stat-label">使用次数</span>
              </div>
              <div class="stat-item">
                <span class="stat-val">{{ formatDate(model.created_at) }}</span>
                <span class="stat-label">创建时间</span>
              </div>
            </div>

            <div class="model-actions">
              <el-button text size="small" type="primary" :icon="Microphone" @click="useTTS(model)">TTS 试用</el-button>
              <el-button text size="small" :icon="Edit" @click="openEditDialog(model)">编辑</el-button>
              <el-popconfirm title="确定要删除这个声音模型吗？" @confirm="handleDelete(model.id)">
                <template #reference>
                  <el-button text size="small" type="danger" :icon="Delete">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 创建声音模型对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建声音模型" width="560px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="rules" label-width="90px">
        <el-form-item label="模型名称" prop="title">
          <el-input v-model="createForm.title" placeholder="例如：客服小美" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="简单描述这个声音的特点..." />
        </el-form-item>
        <el-form-item label="语言">
          <el-radio-group v-model="createForm.language">
            <el-radio-button value="zh">中文</el-radio-button>
            <el-radio-button value="en">英文</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="createForm.visibility">
            <el-radio-button value="private">私有</el-radio-button>
            <el-radio-button value="public">公开</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="参考音频" prop="audioFiles">
          <el-upload
            v-model:file-list="audioFileList"
            multiple
            :auto-upload="false"
            :on-change="handleAudioChange"
            accept="audio/*"
            :limit="5"
          >
            <el-button :icon="UploadFilled">选择音频文件</el-button>
            <template #tip>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                建议上传 3~10 秒清晰音频，最多 5 个文件，质量越好克隆效果越佳
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 发现官方音色对话框 -->
    <el-dialog v-model="showDiscoverDialog" title="🌐 发现官方音色" width="800px" destroy-on-close>
      <div class="discover-toolbar">
        <el-input v-model="discoverKeyword" placeholder="搜索音色名称..." clearable style="width:200px" @keyup.enter="handleDiscoverSearch" />
        <el-button-group>
          <el-button :type="discoverTag === '' ? 'primary' : ''" @click="setDiscoverTag('')">全部</el-button>
          <el-button :type="discoverTag === 'Chinese' ? 'primary' : ''" @click="setDiscoverTag('Chinese')">🇨🇳 中文</el-button>
          <el-button :type="discoverTag === 'English' ? 'primary' : ''" @click="setDiscoverTag('English')">🇬🇧 英文</el-button>
          <el-button :type="discoverTag === 'Japanese' ? 'primary' : ''" @click="setDiscoverTag('Japanese')">🇯🇵 日语</el-button>
        </el-button-group>
        <el-button type="primary" @click="handleDiscoverSearch" :loading="discoverLoading">搜索</el-button>
        <el-button @click="handleDiscoverImport" :loading="importing" :disabled="discoverSelected.length === 0" type="success">
          导入选中 ({{ discoverSelected.length }})
        </el-button>
      </div>
      <el-table
        v-loading="discoverLoading"
        :data="discoverItems"
        @selection-change="discoverSelected = $event"
        style="width:100%;margin-top:12px"
        max-height="440"
      >
        <el-table-column type="selection" width="48" :selectable="row => !row.already_imported" />
        <el-table-column label="" width="52">
          <template #default="{ row }">
            <el-avatar
              :size="36"
              :src="row.cover_image || ''"
              :style="{ background: '#e8f0fe', fontSize: '16px' }"
            >{{ row.title[0] }}</el-avatar>
          </template>
        </el-table-column>
        <el-table-column label="音色名称" prop="title" min-width="140" />
        <el-table-column label="描述" prop="description" show-overflow-tooltip min-width="180" />
        <el-table-column label="状态" width="88" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.already_imported" type="success" size="small">✓ 已导入</el-tag>
            <el-tag v-else type="info" size="small">未导入</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <el-button v-if="discoverItems.some(i => !i.already_imported)" size="small" type="success" :loading="importing" @click="handleImportAll">
          一键全部导入
        </el-button>
        <el-pagination
          v-if="discoverTotal > 0"
          v-model:current-page="discoverPage"
          :page-size="discoverPageSize"
          :total="discoverTotal"
          layout="prev, pager, next, jumper, total"
          small
          @current-change="handleDiscoverSearch"
        />
      </div>
    </el-dialog>

    <!-- 编辑对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑声音模型" width="480px" destroy-on-close>
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="模型名称">
          <el-input v-model="editForm.title" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="editForm.visibility">
            <el-radio-button label="private">私有</el-radio-button>
            <el-radio-button label="public">公开</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="editing" @click="handleEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Plus, Microphone, Edit, Delete, UploadFilled, Promotion as Discover } from '@element-plus/icons-vue'
import { getModels, createModel, updateModel, deleteModel, searchOfficialVoices, importOfficialVoices } from '@/api/voice'
import type { VoiceModel } from '@/types/api'
import type { OfficialVoiceItem } from '@/api/voice'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const editing = ref(false)
const models = ref<VoiceModel[]>([])
const searchText = ref('')
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showDiscoverDialog = ref(false)
const discoverKeyword = ref('')
const discoverTag = ref('Chinese')
const discoverPage = ref(1)
const discoverPageSize = 20
const discoverItems = ref<OfficialVoiceItem[]>([])
const discoverSelected = ref<OfficialVoiceItem[]>([])
const discoverLoading = ref(false)
const discoverTotal = ref(0)
const importing = ref(false)
const createFormRef = ref()
const audioFileList = ref<{ raw: File }[]>([])
const editingModelId = ref<number | null>(null)

const createForm = reactive({ title: '', description: '', language: 'zh', visibility: 'private' })
const editForm = reactive({ title: '', description: '', visibility: 'private' })

const rules = {
  title: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
}

const filteredModels = computed(() =>
  models.value.filter(m =>
    !searchText.value || m.title.toLowerCase().includes(searchText.value.toLowerCase())
  )
)

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

function handleAudioChange(_file: { raw: File }) {
  // 通过 file-list 绑定自动管理
}

function openEditDialog(model: VoiceModel) {
  editingModelId.value = model.id
  editForm.title = model.title
  editForm.description = model.description || ''
  editForm.visibility = model.visibility
  showEditDialog.value = true
}

function useTTS(model: VoiceModel) {
  router.push({ path: '/tts', query: { voice_model_id: model.id } })
}

async function handleCreate() {
  await createFormRef.value?.validate()
  const files = audioFileList.value.map(f => f.raw).filter(Boolean)
  if (!files.length) {
    ElMessage.warning('请至少上传一个参考音频')
    return
  }
  creating.value = true
  try {
    await createModel({ ...createForm, audio_files: files })
    ElMessage.success('声音模型创建成功，正在训练中...')
    showCreateDialog.value = false
    audioFileList.value = []
    Object.assign(createForm, { title: '', description: '', language: 'zh', visibility: 'private' })
    await loadModels()
  } catch {
    ElMessage.error('创建失败，请检查音频文件格式')
  } finally {
    creating.value = false
  }
}

async function handleEdit() {
  if (!editingModelId.value) return
  editing.value = true
  try {
    await updateModel(editingModelId.value, editForm)
    ElMessage.success('更新成功')
    showEditDialog.value = false
    await loadModels()
  } finally {
    editing.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await deleteModel(id)
    ElMessage.success('删除成功')
    await loadModels()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function loadModels() {
  loading.value = true
  try {
    const res = await getModels(0, 100)
    models.value = res.items
  } finally {
    loading.value = false
  }
}

async function openDiscoverDialog() {
  showDiscoverDialog.value = true
  discoverItems.value = []
  discoverKeyword.value = ''
  discoverTag.value = 'Chinese'
  discoverPage.value = 1
  await handleDiscoverSearch()
}

function setDiscoverTag(tag: string) {
  discoverTag.value = tag
  discoverPage.value = 1
  handleDiscoverSearch()
}

async function handleDiscoverSearch() {
  discoverLoading.value = true
  try {
    const res = await searchOfficialVoices({
      title: discoverKeyword.value,
      tag: discoverTag.value,
      page_size: discoverPageSize,
      page_number: discoverPage.value,
    })
    discoverItems.value = res.items
    discoverTotal.value = res.total
  } catch {
    ElMessage.error('搜索失败')
  } finally {
    discoverLoading.value = false
  }
}

async function handleDiscoverImport() {
  if (!discoverSelected.value.length) return
  importing.value = true
  try {
    const ids = discoverSelected.value.map(i => i._id)
    const res = await importOfficialVoices(ids)
    ElMessage.success(`成功导入 ${res.imported} 个音色`)
    discoverSelected.value = []
    await handleDiscoverSearch()
    await loadModels()
  } catch {
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

async function handleImportAll() {
  const unimported = discoverItems.value.filter(i => !i.already_imported)
  if (!unimported.length) return
  importing.value = true
  try {
    const ids = unimported.map(i => i._id)
    const res = await importOfficialVoices(ids)
    ElMessage.success(`成功导入 ${res.imported} 个音色`)
    await handleDiscoverSearch()
    await loadModels()
  } catch {
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

onMounted(loadModels)
</script>

<style scoped lang="scss">
.voice-models-page {
  .toolbar-card { margin-bottom: 20px; }
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }

  .discover-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .models-grid { margin-top: 4px; }

  .model-card {
    margin-bottom: 20px;
    transition: transform 0.2s;
    &:hover { transform: translateY(-2px); }

    .model-header {
      display: flex;
      gap: 12px;
      margin-bottom: 12px;
    }

    .model-avatar {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 700;
      color: white;
      flex-shrink: 0;
    }

    .model-info {
      flex: 1;
      min-width: 0;
      .model-title {
        font-size: 15px;
        font-weight: 600;
        color: #303133;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .model-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 4px;
        .lang-tag { font-size: 12px; color: #909399; }
      }
    }

    .model-desc {
      font-size: 13px;
      color: #606266;
      margin-bottom: 12px;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      line-clamp: 2;
      -webkit-box-orient: vertical;
    }

    .model-stats {
      display: flex;
      gap: 24px;
      padding: 10px 0;
      border-top: 1px solid #f5f5f5;
      border-bottom: 1px solid #f5f5f5;
      margin-bottom: 12px;

      .stat-item {
        display: flex;
        flex-direction: column;
        gap: 2px;
        .stat-val { font-size: 14px; font-weight: 600; color: #303133; }
        .stat-label { font-size: 11px; color: #909399; }
      }
    }

    .model-actions {
      display: flex;
      gap: 4px;
      justify-content: flex-end;
    }
  }
}
</style>
