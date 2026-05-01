import { useEffect, useState } from 'react';
import {
  Plug, Plus, RotateCw, Power, PowerOff, Pencil, Trash2, X,
  ChevronDown, ChevronRight, AlertCircle, Wrench,
} from 'lucide-react';
import { toast } from 'sonner';
import PageHeader from '@/components/layout/PageHeader';
import type { MCPServerConfig } from '@/types/entities';
import { mcpApi, type McpServerDTO } from '@/api/mcp';

const STATUS_MAP: Record<string, { label: string; color: string; dotColor: string }> = {
  running: { label: '运行中', color: 'text-green-600', dotColor: 'bg-green-500' },
  stopped: { label: '已停止', color: 'text-gray-500', dotColor: 'bg-gray-400' },
  error: { label: '错误', color: 'text-red-600', dotColor: 'bg-red-500' },
};

function mapServer(dto: McpServerDTO): MCPServerConfig {
  return {
    id: dto.id,
    name: dto.name,
    command: dto.command,
    args: dto.args,
    env: dto.env,
    autoStart: dto.auto_start,
    timeout: 30,
    status: dto.status === 'connected' ? 'running' : dto.status === 'error' ? 'error' : 'stopped',
    tools: [],
    callCount: 0,
  };
}

const MARKETPLACE: Array<{ name: string; description: string; command: string; args: string[] }> = [
  { name: 'Filesystem', description: '文件系统操作', command: 'npx', args: ['-y', '@modelcontextprotocol/server-filesystem', '/workspace'] },
  { name: 'GitHub', description: 'GitHub API 集成', command: 'npx', args: ['-y', '@modelcontextprotocol/server-github'] },
  { name: 'Slack', description: 'Slack 消息和频道', command: 'npx', args: ['-y', '@modelcontextprotocol/server-slack'] },
  { name: 'PostgreSQL', description: 'PostgreSQL 数据库', command: 'npx', args: ['-y', '@modelcontextprotocol/server-postgres'] },
  { name: 'Puppeteer', description: '浏览器自动化', command: 'npx', args: ['-y', '@modelcontextprotocol/server-puppeteer'] },
];

export default function MCPServerPage() {
  const [servers, setServers] = useState<MCPServerConfig[]>([]);
  const [expandedServer, setExpandedServer] = useState<string | null>(null);
  const [showDialog, setShowDialog] = useState(false);
  const [editingServer, setEditingServer] = useState<MCPServerConfig | null>(null);

  async function loadServers() {
    try {
      const res = await mcpApi.list();
      setServers(res.items.map(mapServer));
      if (res.items.length > 0 && !expandedServer) setExpandedServer(res.items[0].id);
    } catch {
      toast.error('加载 MCP 列表失败');
    }
  }

  useEffect(() => {
    loadServers();
  }, []);

  async function handleSave(server: MCPServerConfig) {
    try {
      const exists = servers.some((s) => s.id === server.id);
      if (exists) {
        await mcpApi.update(server.id, {
          command: server.command,
          args: server.args,
          env: server.env,
          auto_start: server.autoStart,
        });
      } else {
        await mcpApi.create({
          name: server.name,
          command: server.command,
          args: server.args,
          env: server.env,
          auto_start: server.autoStart,
        });
      }
      await loadServers();
      setShowDialog(false);
      setEditingServer(null);
      toast.success('MCP 配置已保存');
    } catch {
      toast.error('保存 MCP 配置失败');
    }
  }

  async function handleToggleStatus(id: string) {
    const server = servers.find((s) => s.id === id);
    if (!server) return;
    try {
      if (server.status === 'running') {
        await mcpApi.disconnect(id);
      } else {
        await mcpApi.connect(id);
      }
      await loadServers();
    } catch {
      toast.error('切换 MCP 状态失败');
    }
  }

  async function handleDelete(id: string) {
    try {
      await mcpApi.delete(id);
      await loadServers();
    } catch {
      toast.error('删除 MCP 配置失败');
    }
  }

  function handleQuickAdd(item: typeof MARKETPLACE[0]) {
    const newServer: MCPServerConfig = {
      id: `mcp_${Date.now()}`,
      name: item.name.toLowerCase(),
      command: item.command,
      args: item.args,
      env: {},
      autoStart: false,
      timeout: 30,
      status: 'stopped',
      tools: [],
      callCount: 0,
    };
    setServers((prev) => [...prev, newServer]);
    setEditingServer(newServer);
    setShowDialog(true);
  }

  function handleDuplicate(server: MCPServerConfig) {
    setEditingServer({
      ...server,
      id: `mcp_${Date.now()}`,
      name: `${server.name}-copy`,
      status: 'stopped',
    });
    setShowDialog(true);
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="MCP Server 管理"
        description="通过 Model Context Protocol 连接外部工具服务"
        icon={<Plug size={24} />}
        actions={
          <button
            onClick={() => { setEditingServer(null); setShowDialog(true); }}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
          >
            <Plus size={16} />
            添加 Server
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Server 列表 */}
        <div className="space-y-3">
          {servers.map((server) => {
            const status = STATUS_MAP[server.status];
            const isExpanded = expandedServer === server.id;
            return (
              <div key={server.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                {/* 头部 */}
                <div className="px-5 py-4 flex items-center gap-4">
                  <button onClick={() => setExpandedServer(isExpanded ? null : server.id)} className="text-gray-400 shrink-0">
                    {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  </button>

                  {/* 状态指示 */}
                  <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${status.dotColor}`} />

                  {/* 名称+信息 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-gray-900">{server.name}</span>
                      <span className={`text-xs ${status.color}`}>{status.label}</span>
                      {server.pid && <span className="text-[10px] text-gray-400">PID {server.pid}</span>}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5 font-mono">
                      {server.command} {server.args.join(' ')}
                    </div>
                  </div>

                  {/* 统计 */}
                  <div className="text-right shrink-0">
                    <div className="text-xs text-gray-500">
                      {server.tools.length} 个工具 · {server.callCount} 次调用
                    </div>
                    {server.autoStart && (
                      <span className="text-[10px] text-green-600">自动启动 ✓</span>
                    )}
                  </div>

                  {/* 操作 */}
                  <div className="flex items-center gap-1 shrink-0">
                    {server.status === 'running' ? (
                      <>
                        <button
                          onClick={() => handleToggleStatus(server.id)}
                          title="重启"
                          className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-amber-500 transition-colors"
                        >
                          <RotateCw size={15} />
                        </button>
                        <button
                          onClick={() => handleToggleStatus(server.id)}
                          title="断开"
                          className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                        >
                          <PowerOff size={15} />
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleToggleStatus(server.id)}
                        title="连接"
                        className="p-1.5 rounded hover:bg-green-50 text-gray-400 hover:text-green-600 transition-colors"
                      >
                        <Power size={15} />
                      </button>
                    )}
                    <button
                      onClick={() => { setEditingServer(server); setShowDialog(true); }}
                      className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      onClick={() => handleDuplicate(server)}
                      className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors text-xs"
                    >
                      复制
                    </button>
                    <button
                      onClick={() => handleDelete(server.id)}
                      className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>

                {/* 错误信息 */}
                {server.lastError && server.status !== 'running' && (
                  <div className="mx-5 mb-3 px-3 py-2 bg-red-50 border border-red-100 rounded-lg flex items-center gap-2 text-xs text-red-600">
                    <AlertCircle size={14} />
                    {server.lastError}
                  </div>
                )}

                {/* 展开: 工具列表 */}
                {isExpanded && server.tools.length > 0 && (
                  <div className="px-5 pb-4 pl-14">
                    <div className="bg-gray-50 rounded-lg p-3">
                      <h4 className="text-xs font-semibold text-gray-500 mb-2">已注册工具 ({server.tools.length})</h4>
                      <div className="grid grid-cols-2 gap-2">
                        {server.tools.map((tool) => (
                          <div key={tool.id} className="flex items-center gap-2 text-xs text-gray-600 bg-white px-3 py-2 rounded-lg border border-gray-100">
                            <Wrench size={12} className="text-gray-400 shrink-0" />
                            <span className="font-mono font-medium text-gray-800">{tool.name}</span>
                            <span className="text-gray-400 truncate">{tool.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {isExpanded && server.tools.length === 0 && server.status === 'stopped' && (
                  <div className="px-5 pb-4 pl-14 text-xs text-gray-400">
                    连接后将自动发现工具
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 市场 */}
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            MCP Server 市场
            <span className="text-xs text-gray-400 font-normal">快速添加常用 Server</span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {MARKETPLACE.filter((m) => !servers.find((s) => s.name === m.name.toLowerCase())).map((item) => (
              <button
                key={item.name}
                onClick={() => handleQuickAdd(item)}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:border-purple-300 hover:shadow-sm transition-all text-sm"
              >
                <Plus size={14} className="text-purple-500" />
                <span className="font-medium text-gray-700">{item.name}</span>
                <span className="text-xs text-gray-400">{item.description}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {showDialog && (
        <MCPEditDialog
          server={editingServer}
          onSave={handleSave}
          onClose={() => { setShowDialog(false); setEditingServer(null); }}
        />
      )}
    </div>
  );
}

function MCPEditDialog({
  server,
  onSave,
  onClose,
}: {
  server: MCPServerConfig | null;
  onSave: (s: MCPServerConfig) => void;
  onClose: () => void;
}) {
  const isNew = !server;
  const [form, setForm] = useState<MCPServerConfig>(
    server ?? {
      id: `mcp_${Date.now()}`,
      name: '',
      command: 'npx',
      args: [],
      env: {},
      autoStart: false,
      timeout: 30,
      status: 'stopped',
      tools: [],
      callCount: 0,
    },
  );
  const [argsText, setArgsText] = useState(form.args.join('\n'));
  const [envEntries, setEnvEntries] = useState<Array<{ key: string; value: string }>>(
    Object.entries(form.env).map(([key, value]) => ({ key, value })),
  );

  const set = (partial: Partial<MCPServerConfig>) => setForm((prev) => ({ ...prev, ...partial }));

  function handleSaveClick() {
    const args = argsText.split('\n').map((s) => s.trim()).filter(Boolean);
    const env: Record<string, string> = {};
    envEntries.forEach((e) => { if (e.key) env[e.key] = e.value; });
    onSave({ ...form, args, env });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-[520px] max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">{isNew ? '添加 MCP Server' : `编辑: ${server.name}`}</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100"><X size={18} className="text-gray-400" /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">名称</label>
            <input className="input-base" value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="filesystem" />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">启动命令</label>
            <input className="input-base font-mono" value={form.command} onChange={(e) => set({ command: e.target.value })} placeholder="npx" />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">参数（每行一个）</label>
            <textarea
              className="input-base font-mono text-xs resize-none h-20"
              value={argsText}
              onChange={(e) => setArgsText(e.target.value)}
              placeholder={"-y\n@modelcontextprotocol/server-filesystem\n/workspace"}
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">
              环境变量
              <span className="text-gray-400 font-normal ml-2">值支持 {'${SECRET_NAME}'} 引用密钥</span>
            </label>
            <div className="space-y-2">
              {envEntries.map((entry, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    className="input-base flex-1 font-mono text-xs"
                    value={entry.key}
                    onChange={(e) => {
                      const next = [...envEntries]; next[i] = { ...entry, key: e.target.value }; setEnvEntries(next);
                    }}
                    placeholder="KEY"
                  />
                  <span className="text-gray-300">=</span>
                  <input
                    className="input-base flex-1 font-mono text-xs"
                    value={entry.value}
                    onChange={(e) => {
                      const next = [...envEntries]; next[i] = { ...entry, value: e.target.value }; setEnvEntries(next);
                    }}
                    placeholder="${SECRET_NAME}"
                  />
                  <button
                    onClick={() => setEnvEntries(envEntries.filter((_, j) => j !== i))}
                    className="p-1 text-gray-400 hover:text-red-500"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
              <button
                onClick={() => setEnvEntries([...envEntries, { key: '', value: '' }])}
                className="text-xs text-purple-600 hover:text-purple-700"
              >
                + 添加环境变量
              </button>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-xs text-gray-700">
              <input type="checkbox" checked={form.autoStart} onChange={(e) => set({ autoStart: e.target.checked })} />
              自动启动（服务启动时自动连接）
            </label>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">超时:</label>
              <input type="number" className="input-base w-16 text-xs" value={form.timeout} onChange={(e) => set({ timeout: parseInt(e.target.value) || 30 })} />
              <span className="text-xs text-gray-400">秒</span>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between">
          <button className="px-3 py-1.5 text-sm text-green-600 hover:bg-green-50 rounded-lg transition-colors">
            测试连接
          </button>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">取消</button>
            <button
              onClick={handleSaveClick}
              disabled={!form.name || !form.command}
              className="px-4 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
