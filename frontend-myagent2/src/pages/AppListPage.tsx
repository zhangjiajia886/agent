import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Wrench, MessageSquare, Pencil, Trash2, Bot } from 'lucide-react';
import { toast } from 'sonner';
import { appApi, type AppDTO } from '@/api/apps';

const TEMPLATES = [
  { key: 'blank',   icon: '⚙️', name: '空白应用',     desc: '从零开始，完全自定义',
    tools: [], system_prompt: '你是一个智能助手，请尽力帮助用户解决问题。', opening_msg: '你好！有什么可以帮助你的？' },
  { key: 'general', icon: '🤖', name: '通用助手',     desc: '万能对话助手，适合日常问答',
    tools: [], system_prompt: '你是一个专业、友好的智能助手。请用简洁清晰的语言回答用户问题，必要时使用列表或代码块增强可读性。', opening_msg: '你好！我是你的智能助手，有什么可以帮助你的？' },
  { key: 'search',  icon: '🌐', name: '联网搜索助手', desc: '实时搜索互联网，回答时效性问题',
    tools: ['web_search'], system_prompt: '你是一个擅长搜索和整合信息的助手。当用户询问最新事件、数据或不确定的信息时，先使用搜索工具获取最新内容，再基于搜索结果给出准确回答，并注明信息来源。', opening_msg: '你好！我可以帮你搜索互联网上的最新信息，请问有什么想了解的？' },
  { key: 'code',    icon: '💻', name: '代码助手',     desc: '编写、调试、执行代码',
    tools: ['python_exec', 'bash'], system_prompt: '你是一位资深软件工程师，精通多种编程语言。你可以直接执行代码来验证结果。请在回答时提供清晰的代码示例，并在需要时使用工具运行代码。', opening_msg: '你好！我是你的代码助手，可以帮你编写、调试和执行代码。请问有什么编程问题需要解决？' },
  { key: 'write',   icon: '📝', name: '写作助手',     desc: '文案创作、改写润色',
    tools: ['web_search'], system_prompt: '你是一位专业的写作助手，擅长各种文体的创作和改写。你注重文字的准确性、流畅性和表达力。可以根据需要搜索背景资料来丰富内容。', opening_msg: '你好！我是你的写作助手，可以帮你起草文章、改写文案、润色表达。请告诉我你需要什么样的帮助？' },
  { key: 'file',    icon: '🔍', name: '文件分析助手', desc: '读取和分析本地文件内容',
    tools: ['read_file', 'grep_search'], system_prompt: '你是一个文件分析专家，可以读取文件内容、搜索代码仓库。请帮用户分析文件内容、查找特定信息、总结文档要点。', opening_msg: '你好！我可以帮你读取和分析文件内容。请告诉我文件路径或你想了解的内容。' },
];

export default function AppListPage() {
  const navigate = useNavigate();
  const [apps, setApps] = useState<AppDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTemplates, setShowTemplates] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      const data = await appApi.list();
      setApps(data.items);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(tpl: typeof TEMPLATES[0]) {
    setCreating(true);
    try {
      const app = await appApi.create({
        name: tpl.name,
        description: tpl.desc,
        icon: tpl.icon,
        opening_msg: tpl.opening_msg,
        system_prompt: tpl.system_prompt,
        tools: tpl.tools,
        variables: [],
        model: '',
      });
      setShowTemplates(false);
      navigate(`/apps/${app.id}/build`);
    } catch {
      toast.error('创建失败');
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(app: AppDTO) {
    if (!confirm(`确认删除「${app.name}」？`)) return;
    await appApi.delete(app.id);
    toast.success('已删除');
    setApps(prev => prev.filter(a => a.id !== app.id));
  }

  async function handleTogglePublish(app: AppDTO) {
    const updated = await appApi.update(app.id, { is_published: !app.is_published });
    setApps(prev => prev.map(a => a.id === app.id ? updated : a));
    toast.success(updated.is_published ? '已发布' : '已下线');
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">应用中心</h1>
          <p className="text-sm text-gray-500 mt-0.5">创建 AI 应用，组合工具与技能，发布给用户使用</p>
        </div>
        <button
          onClick={() => setShowTemplates(true)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium"
        >
          <Plus size={16} /> 新建应用
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        {loading ? (
          <div className="flex items-center justify-center h-40 text-gray-400">加载中...</div>
        ) : apps.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400 gap-4">
            <Bot size={48} className="text-gray-300" />
            <p className="text-lg font-medium">还没有应用</p>
            <p className="text-sm">选择一个模板快速创建你的第一个 AI 应用</p>
            <button
              onClick={() => setShowTemplates(true)}
              className="mt-2 flex items-center gap-2 px-5 py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium"
            >
              <Plus size={16} /> 从模板创建
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {apps.map(app => (
              <AppCard
                key={app.id}
                app={app}
                onChat={() => navigate(`/apps/${app.id}/chat`)}
                onEdit={() => navigate(`/apps/${app.id}/build`)}
                onDelete={() => handleDelete(app)}
                onTogglePublish={() => handleTogglePublish(app)}
              />
            ))}
            {/* Add card */}
            <button
              onClick={() => setShowTemplates(true)}
              className="flex flex-col items-center justify-center h-52 border-2 border-dashed border-gray-200 rounded-xl text-gray-400 hover:border-purple-400 hover:text-purple-500 hover:bg-purple-50 transition-colors"
            >
              <Plus size={32} className="mb-2" />
              <span className="text-sm font-medium">新建应用</span>
            </button>
          </div>
        )}
      </div>

      {/* Template selector dialog */}
      {showTemplates && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl">
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900">选择模板</h2>
              <p className="text-sm text-gray-500 mt-0.5">选一个最接近你需求的模板，之后可以随时修改</p>
            </div>
            <div className="grid grid-cols-2 gap-3 p-6">
              {TEMPLATES.map(tpl => (
                <button
                  key={tpl.key}
                  onClick={() => !creating && handleCreate(tpl)}
                  disabled={creating}
                  className="flex items-start gap-3 p-4 border border-gray-200 rounded-xl hover:border-purple-400 hover:bg-purple-50 text-left transition-colors disabled:opacity-60"
                >
                  <span className="text-2xl mt-0.5">{tpl.icon}</span>
                  <div>
                    <div className="font-medium text-gray-800 text-sm">{tpl.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{tpl.desc}</div>
                    {tpl.tools.length > 0 && (
                      <div className="flex gap-1 mt-1.5 flex-wrap">
                        {tpl.tools.map(t => (
                          <span key={t} className="text-[10px] bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded-full">{t}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
            <div className="px-6 py-4 border-t border-gray-100 flex justify-end">
              <button onClick={() => setShowTemplates(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AppCard({ app, onChat, onEdit, onDelete, onTogglePublish }: {
  app: AppDTO;
  onChat: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onTogglePublish: () => void;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col hover:shadow-md transition-shadow">
      <div
        className="flex items-start justify-between mb-3 cursor-pointer"
        onClick={onEdit}
        title="点击配置应用"
      >
        <span className="text-3xl">{app.icon}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
          app.is_published ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
        }`}>
          {app.is_published ? '已发布' : '草稿'}
        </span>
      </div>
      <h3
        className="font-semibold text-gray-900 text-base mb-1 truncate cursor-pointer hover:text-purple-600"
        onClick={onEdit}
      >{app.name}</h3>
      <p className="text-xs text-gray-500 mb-3 line-clamp-2 flex-1">{app.description || '暂无描述'}</p>
      {app.tools.length > 0 && (
        <div className="flex gap-1 flex-wrap mb-3">
          {app.tools.slice(0, 3).map(t => (
            <span key={t} className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full">{t}</span>
          ))}
          {app.tools.length > 3 && (
            <span className="text-[10px] bg-gray-50 text-gray-400 px-1.5 py-0.5 rounded-full">+{app.tools.length - 3}</span>
          )}
        </div>
      )}
      <div className="flex gap-2 mt-auto pt-3 border-t border-gray-100">
        <button
          onClick={onChat}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-xs font-medium"
        >
          <MessageSquare size={13} /> 对话
        </button>
        <button
          onClick={onEdit}
          className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg"
          title="编辑配置"
        >
          <Pencil size={15} />
        </button>
        <button
          onClick={onTogglePublish}
          className={`p-1.5 rounded-lg text-xs ${app.is_published ? 'text-orange-500 hover:bg-orange-50' : 'text-green-600 hover:bg-green-50'}`}
          title={app.is_published ? '下线' : '发布'}
        >
          <Wrench size={15} />
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
          title="删除"
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  );
}
