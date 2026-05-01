import { useEffect, useMemo, useState } from 'react';
import { Wrench, Search, Shield, Clock, ToggleLeft, ToggleRight, ChevronDown, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import PageHeader from '@/components/layout/PageHeader';
import type { ToolDefinition } from '@/types/entities';
import { toolApi, type ToolDTO } from '@/api/tools';

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  builtin: { label: '内置', color: 'bg-green-50 text-green-700' },
  mcp: { label: 'MCP', color: 'bg-blue-50 text-blue-700' },
  custom: { label: '自定义', color: 'bg-purple-50 text-purple-700' },
};

const PERM_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  auto_allow: { label: '自动放行', color: 'text-green-600', icon: '🟢' },
  always_ask: { label: '每次确认', color: 'text-amber-600', icon: '🟡' },
  deny: { label: '禁止', color: 'text-red-600', icon: '🔴' },
};

function mapTool(dto: ToolDTO): ToolDefinition {
  const schema = dto.input_schema as { properties?: Record<string, { type?: string; description?: string; default?: unknown }>; required?: string[] };
  const required = new Set(schema?.required ?? []);
  const parameters = Object.entries(schema?.properties ?? {}).map(([name, meta]) => ({
    name,
    type: (meta.type as 'string' | 'number' | 'boolean' | 'object') || 'string',
    description: meta.description || '',
    required: required.has(name),
    default: meta.default,
  }));

  return {
    id: dto.name,
    name: dto.name,
    description: dto.description,
    source: dto.type === 'mcp' ? 'mcp' : dto.type === 'custom' ? 'custom' : 'builtin',
    parameters,
    permissionLevel: dto.risk_level === 'low' ? 'auto_allow' : dto.risk_level === 'high' ? 'deny' : 'always_ask',
    enabled: dto.is_enabled,
    executionCount: dto.call_count ?? 0,
    avgDurationMs: dto.avg_duration_ms ?? 0,
  };
}

export default function ToolListPage() {
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSource, setFilterSource] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedTool, setExpandedTool] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await toolApi.list();
        setTools(res.items.map(mapTool));
      } catch {
        toast.error('加载工具列表失败');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = useMemo(() => tools.filter((t) => {
    if (filterSource !== 'all' && t.source !== filterSource) return false;
    if (searchQuery && !t.name.includes(searchQuery) && !t.description.includes(searchQuery)) return false;
    return true;
  }), [tools, filterSource, searchQuery]);

  const grouped = filtered.reduce((acc, t) => {
    (acc[t.source] ??= []).push(t);
    return acc;
  }, {} as Record<string, ToolDefinition[]>);

  function togglePermission(id: string) {
    const cycle: Record<string, ToolDefinition['permissionLevel']> = {
      auto_allow: 'always_ask',
      always_ask: 'deny',
      deny: 'auto_allow',
    };
    setTools((prev) => prev.map((t) => t.id === id ? { ...t, permissionLevel: cycle[t.permissionLevel] } : t));
  }

  function toggleEnabled(id: string) {
    setTools((prev) => prev.map((t) => t.id === id ? { ...t, enabled: !t.enabled } : t));
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="工具管理"
        description={loading ? '正在加载真实工具清单...' : `内置 + MCP + 自定义工具，共 ${tools.length} 个`}
        icon={<Wrench size={24} />}
      />

      {/* 筛选 */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-100 bg-white">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text" placeholder="搜索工具..."
            value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-purple-400 w-64"
          />
        </div>
        <div className="flex gap-1">
          <FilterChip label="全部" active={filterSource === 'all'} onClick={() => setFilterSource('all')} />
          {Object.entries(SOURCE_LABELS).map(([key, val]) => (
            <FilterChip key={key} label={`${val.label} (${tools.filter((t) => t.source === key).length})`} active={filterSource === key} onClick={() => setFilterSource(key)} />
          ))}
        </div>
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {(['builtin', 'mcp', 'custom'] as const).map((source) => {
          const list = grouped[source];
          if (!list?.length) return null;
          const meta = SOURCE_LABELS[source];
          return (
            <div key={source} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${meta.color}`}>{meta.label}</span>
                <span className="text-xs text-gray-400">{list.length} 个工具</span>
              </div>
              <div className="divide-y divide-gray-50">
                {list.map((tool) => (
                  <ToolRow
                    key={tool.id}
                    tool={tool}
                    expanded={expandedTool === tool.id}
                    onToggleExpand={() => setExpandedTool(expandedTool === tool.id ? null : tool.id)}
                    onTogglePermission={() => togglePermission(tool.id)}
                    onToggleEnabled={() => toggleEnabled(tool.id)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ToolRow({
  tool,
  expanded,
  onToggleExpand,
  onTogglePermission,
  onToggleEnabled,
}: {
  tool: ToolDefinition;
  expanded: boolean;
  onToggleExpand: () => void;
  onTogglePermission: () => void;
  onToggleEnabled: () => void;
}) {
  const perm = PERM_LABELS[tool.permissionLevel];

  return (
    <div className={`${!tool.enabled ? 'opacity-50' : ''}`}>
      <div className="px-5 py-3 flex items-center gap-4 hover:bg-gray-50/50 transition-colors">
        {/* 展开箭头 */}
        <button onClick={onToggleExpand} className="text-gray-400 hover:text-gray-600 shrink-0">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>

        {/* 启用/禁用 */}
        <button onClick={onToggleEnabled} className="shrink-0">
          {tool.enabled
            ? <ToggleRight size={20} className="text-green-500" />
            : <ToggleLeft size={20} className="text-gray-300" />
          }
        </button>

        {/* 名称 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-medium text-gray-900">{tool.name}</span>
            {tool.mcpServer && (
              <span className="text-[10px] text-gray-400">来自: {tool.mcpServer}</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{tool.description}</p>
        </div>

        {/* 权限 */}
        <button
          onClick={onTogglePermission}
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors shrink-0 ${perm.color}`}
          title="点击切换权限"
        >
          <Shield size={12} />
          {perm.label}
        </button>

        {/* 统计 */}
        <div className="text-right shrink-0 w-28">
          <div className="text-xs text-gray-500">{tool.executionCount} 次调用</div>
          <div className="text-[10px] text-gray-400 flex items-center justify-end gap-1 mt-0.5">
            <Clock size={10} />
            avg {tool.avgDurationMs}ms
          </div>
        </div>
      </div>

      {/* 展开详情 */}
      {expanded && (
        <div className="px-5 pb-3 pl-16">
          <div className="bg-gray-50 rounded-lg p-3">
            <h4 className="text-xs font-semibold text-gray-500 mb-2">参数</h4>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-400">
                  <th className="pb-1 pr-4 font-medium">名称</th>
                  <th className="pb-1 pr-4 font-medium">类型</th>
                  <th className="pb-1 pr-4 font-medium">描述</th>
                  <th className="pb-1 pr-4 font-medium">必填</th>
                  <th className="pb-1 font-medium">默认值</th>
                </tr>
              </thead>
              <tbody className="text-gray-600">
                {tool.parameters.map((p) => (
                  <tr key={p.name}>
                    <td className="py-0.5 pr-4 font-mono text-purple-600">{p.name}</td>
                    <td className="py-0.5 pr-4 font-mono text-gray-400">{p.type}</td>
                    <td className="py-0.5 pr-4">{p.description}</td>
                    <td className="py-0.5 pr-4">{p.required ? '✅' : '—'}</td>
                    <td className="py-0.5 font-mono text-gray-400">{p.default !== undefined ? String(p.default) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 text-[11px] rounded-md transition-colors ${
        active ? 'bg-purple-100 text-purple-700 font-medium' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
      }`}
    >
      {label}
    </button>
  );
}
