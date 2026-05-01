import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import AppLayout from '@/components/layout/AppLayout';
import WorkflowListPage from '@/pages/WorkflowListPage';
import FlowEditorPage from '@/pages/FlowEditorPage';
import ModelConfigPage from '@/pages/ModelConfigPage';
import SecretsPage from '@/pages/SecretsPage';
import SkillListPage from '@/pages/SkillListPage';
import PromptListPage from '@/pages/PromptListPage';
import ToolListPage from '@/pages/ToolListPage';
import MCPServerPage from '@/pages/MCPServerPage';
import ExecutionMonitorPage from '@/pages/ExecutionMonitorPage';
import PermissionPage from '@/pages/PermissionPage';
import KnowledgePage from '@/pages/KnowledgePage';
import SettingsPage from '@/pages/SettingsPage';
import ChatPage from '@/pages/ChatPage';
import AppListPage from '@/pages/AppListPage';
import MemoryPage from '@/pages/MemoryPage';
import TasksPage from '@/pages/TasksPage';
import AnalyticsPage from '@/pages/AnalyticsPage';
import SchedulePage from '@/pages/SchedulePage';
import EvalPage from '@/pages/EvalPage';
import AppBuilderPage from '@/pages/AppBuilderPage';
import AppChatPage from '@/pages/AppChatPage';
import LoginPage from '@/pages/LoginPage';
import { useAuthStore } from '@/stores/authStore';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function App() {
  const hydrate = useAuthStore((s) => s.hydrate);
  useEffect(() => { hydrate(); }, [hydrate]);

  return (
    <BrowserRouter>
      <Toaster position="top-right" richColors />
      <Routes>
        {/* 登录页 — 独立布局 */}
        <Route path="/login" element={<LoginPage />} />

        <Route element={<AuthGuard><AppLayout /></AuthGuard>}>
          {/* Chat - 核心入口 */}
          <Route path="/chat" element={<ChatPage />} />

          {/* Apps */}
          <Route path="/apps" element={<AppListPage />} />
          <Route path="/apps/:id/chat" element={<AppChatPage />} />

          {/* Phase 1 */}
          <Route path="/workflows" element={<WorkflowListPage />} />
          <Route path="/models" element={<ModelConfigPage />} />
          <Route path="/secrets" element={<SecretsPage />} />

          {/* Phase 2 */}
          <Route path="/skills" element={<SkillListPage />} />
          <Route path="/prompts" element={<PromptListPage />} />
          <Route path="/tools" element={<ToolListPage />} />
          <Route path="/mcp" element={<MCPServerPage />} />

          {/* Phase 3 */}
          <Route path="/executions" element={<ExecutionMonitorPage />} />
          <Route path="/permissions" element={<PermissionPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/memories" element={<MemoryPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/schedules" element={<SchedulePage />} />
          <Route path="/evals" element={<EvalPage />} />

          {/* 默认重定向 */}
          <Route path="/" element={<Navigate to="/chat" replace />} />
        </Route>

        {/* 画布编辑器 — 全屏布局（也需要登录） */}
        <Route path="/workflows/:id/edit" element={<AuthGuard><FlowEditorPage /></AuthGuard>} />
        {/* 应用编排 — 全屏布局（也需要登录） */}
        <Route path="/apps/:id/build" element={<AuthGuard><AppBuilderPage /></AuthGuard>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App
