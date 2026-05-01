import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Workflow, Cpu, KeyRound, Wrench, Plug, Shield,
  BookOpen, Activity, Settings, BrainCircuit, FileText,
  LayoutDashboard, MessageSquare, SquareStack, LogOut, User,
  Brain, ListTodo, BarChart3, Clock, FlaskConical,
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';

const NAV_ITEMS = [
  { to: '/chat', label: '对话', icon: MessageSquare },
  { to: '/apps', label: '应用', icon: SquareStack },
  { to: '/workflows', label: '工作流', icon: Workflow },
  { to: '/skills', label: '技能', icon: BrainCircuit },
  { to: '/prompts', label: 'Prompt', icon: FileText },
  { to: '/models', label: '模型', icon: Cpu },
  { to: '/tools', label: '工具', icon: Wrench },
  { to: '/mcp', label: 'MCP', icon: Plug },
  { to: '/secrets', label: '密钥', icon: KeyRound },
  { to: '/permissions', label: '权限', icon: Shield },
  { to: '/knowledge', label: '知识库', icon: BookOpen },
  { to: '/memories', label: '记忆', icon: Brain },
  { to: '/tasks', label: '任务', icon: ListTodo },
  { to: '/analytics', label: '用量统计', icon: BarChart3 },
  { to: '/schedules', label: '定时调度', icon: Clock },
  { to: '/evals', label: '评测', icon: FlaskConical },
  { to: '/executions', label: '执行', icon: Activity },
  { to: '/settings', label: '设置', icon: Settings },
] as const;

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  // 画布编辑器 / 应用编排使用全屏布局，不显示侧边栏
  const isEditorRoute = /^\/workflows\/[^/]+\/edit/.test(location.pathname)
    || /^\/apps\/[^/]+\/build/.test(location.pathname)
    || /^\/apps\/[^/]+\/chat/.test(location.pathname);
  if (isEditorRoute) {
    return <Outlet />;
  }

  return (
    <div className="flex h-screen w-screen bg-gray-50">
      {/* 侧边栏 */}
      <aside className="w-52 bg-white border-r border-gray-200 flex flex-col shrink-0">
        {/* Logo */}
        <div className="h-14 flex items-center gap-2.5 px-5 border-b border-gray-100">
          <LayoutDashboard size={22} className="text-purple-600" />
          <span className="font-bold text-gray-800 text-[15px]">AgentFlow</span>
        </div>

        {/* 导航 */}
        <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-purple-50 text-purple-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* 用户信息 + 登出 */}
        <div className="px-3 py-3 border-t border-gray-100">
          <div className="flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-gray-50 group">
            <div className="w-7 h-7 rounded-full bg-purple-100 flex items-center justify-center shrink-0">
              <User size={14} className="text-purple-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-700 truncate">
                {user?.display_name || user?.username || '用户'}
              </p>
              <p className="text-[10px] text-gray-400 truncate">@{user?.username}</p>
            </div>
            <button
              onClick={handleLogout}
              title="退出登录"
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-gray-200"
            >
              <LogOut size={13} className="text-gray-500" />
            </button>
          </div>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
