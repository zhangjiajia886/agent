import { useState, useEffect } from 'react';
import { BarChart3, RefreshCw } from 'lucide-react';
import { skillApi, type SkillStats } from '@/api/skills';

const SOURCE_LABELS: Record<string, string> = {
  user: '用户', file: '文件', bundled: 'Bundled', legacy_command: 'Legacy', community: '社区',
};
const STATUS_LABELS: Record<string, string> = {
  full: '完整', partial: '部分', degraded: '降级', pending: '待定',
};
const MODE_LABELS: Record<string, string> = {
  inline: 'Inline', fork: 'Fork',
};

const BAR_COLORS = [
  'bg-blue-400', 'bg-green-400', 'bg-amber-400', 'bg-purple-400',
  'bg-cyan-400', 'bg-pink-400', 'bg-indigo-400', 'bg-orange-400',
];

export default function SkillStatsPanel() {
  const [stats, setStats] = useState<SkillStats | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const res = await skillApi.stats();
      setStats(res);
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6 text-xs text-gray-400">
        <RefreshCw size={14} className="animate-spin mr-2" /> 加载统计...
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="text-center py-4 text-xs text-gray-400">统计数据加载失败</div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 总数 */}
      <div className="flex items-center gap-2">
        <BarChart3 size={14} className="text-purple-500" />
        <span className="text-xs font-medium text-gray-700">Skill 统计</span>
        <span className="ml-auto text-lg font-bold text-purple-600">{stats.total}</span>
        <span className="text-[10px] text-gray-400">总数</span>
        <button onClick={load} className="p-1 rounded hover:bg-gray-100 text-gray-400" title="刷新">
          <RefreshCw size={12} />
        </button>
      </div>

      {/* 来源分布 */}
      <DistributionBar
        title="按来源"
        data={stats.by_source_type}
        labels={SOURCE_LABELS}
        total={stats.total}
      />

      {/* 迁移状态分布 */}
      <DistributionBar
        title="按迁移状态"
        data={stats.by_migration_status}
        labels={STATUS_LABELS}
        total={stats.total}
      />

      {/* 执行模式分布 */}
      <DistributionBar
        title="按执行模式"
        data={stats.by_context_mode}
        labels={MODE_LABELS}
        total={stats.total}
      />
    </div>
  );
}

function DistributionBar({
  title,
  data,
  labels,
  total,
}: {
  title: string;
  data: Record<string, number>;
  labels: Record<string, string>;
  total: number;
}) {
  const entries = Object.entries(data).filter(([, v]) => v > 0);
  if (entries.length === 0) {
    return (
      <div>
        <p className="text-[10px] text-gray-400 mb-1">{title}</p>
        <p className="text-[10px] text-gray-300">暂无数据</p>
      </div>
    );
  }

  return (
    <div>
      <p className="text-[10px] text-gray-400 mb-1.5">{title}</p>
      {/* 比例条 */}
      <div className="flex h-2 rounded-full overflow-hidden bg-gray-100">
        {entries.map(([key, count], i) => (
          <div
            key={key}
            className={`${BAR_COLORS[i % BAR_COLORS.length]} transition-all`}
            style={{ width: `${total > 0 ? (count / total) * 100 : 0}%` }}
            title={`${labels[key] || key}: ${count}`}
          />
        ))}
      </div>
      {/* 图例 */}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5">
        {entries.map(([key, count], i) => (
          <div key={key} className="flex items-center gap-1 text-[10px] text-gray-500">
            <span className={`inline-block w-2 h-2 rounded-sm ${BAR_COLORS[i % BAR_COLORS.length]}`} />
            <span>{labels[key] || key}</span>
            <span className="font-medium text-gray-700">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
