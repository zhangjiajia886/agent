import { useState, useEffect, useCallback } from 'react';
import { BarChart3, TrendingUp, MessageSquare, Wrench, Cpu } from 'lucide-react';
import { analyticsApi } from '@/api/analytics';
import type { UsageItem, UsageSummary, ModelUsage } from '@/api/analytics';

const DAYS_OPTIONS = [7, 14, 30, 90];

function StatCard({ icon, label, value, sub }: {
  icon: React.ReactNode; label: string; value: string | number; sub?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-purple-500">{icon}</span>
        <span className="text-xs text-gray-500 font-medium">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-800">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function DailyChart({ items }: { items: UsageItem[] }) {
  if (items.length === 0) return (
    <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
      暂无数据（MySQL 环境下才会记录）
    </div>
  );

  // 按日期聚合
  const byDate: Record<string, { input: number; output: number; messages: number }> = {};
  items.forEach(item => {
    const d = item.stat_date.slice(0, 10);
    if (!byDate[d]) byDate[d] = { input: 0, output: 0, messages: 0 };
    byDate[d].input += item.input_tokens;
    byDate[d].output += item.output_tokens;
    byDate[d].messages += item.messages;
  });

  const dates = Object.keys(byDate).sort();
  const maxTokens = Math.max(...dates.map(d => byDate[d].input + byDate[d].output), 1);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-4 text-xs text-gray-400 mb-3">
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-purple-400 rounded inline-block" /> 输入 tokens</span>
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-blue-400 rounded inline-block" /> 输出 tokens</span>
      </div>
      <div className="flex items-end gap-1 h-40 overflow-x-auto pb-1">
        {dates.map(d => {
          const { input, output } = byDate[d];
          const inputH = Math.round((input / maxTokens) * 140);
          const outputH = Math.round((output / maxTokens) * 140);
          return (
            <div key={d} className="flex flex-col items-center gap-0.5 min-w-[28px] group relative">
              <div className="absolute bottom-full mb-1 hidden group-hover:flex flex-col items-center z-10">
                <div className="bg-gray-800 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap">
                  {d}<br />输入: {fmt(input)}<br />输出: {fmt(output)}
                </div>
              </div>
              <div className="flex items-end gap-px">
                <div className="w-2.5 bg-purple-400 rounded-t" style={{ height: `${inputH}px` }} />
                <div className="w-2.5 bg-blue-400 rounded-t" style={{ height: `${outputH}px` }} />
              </div>
              <div className="text-[9px] text-gray-400 truncate w-full text-center">
                {d.slice(5)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ModelTable({ items }: { items: ModelUsage[] }) {
  if (items.length === 0) return (
    <div className="text-center text-gray-400 text-sm py-6">暂无数据</div>
  );
  const grandTotal = items.reduce((s, m) => s + m.input_tokens + m.output_tokens, 0) || 1;
  return (
    <div className="space-y-2">
      {items.map(m => {
        const t = m.input_tokens + m.output_tokens;
        const pct = Math.round((t / grandTotal) * 100);
        return (
          <div key={m.model} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-gray-700 truncate max-w-[60%]">{m.model || '未知模型'}</span>
              <span className="text-gray-400">{fmt(t)} tokens · {m.messages} 条消息</span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-purple-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<UsageItem[]>([]);
  const [summary, setSummary] = useState<UsageSummary>({ total_input: 0, total_output: 0, total_messages: 0, total_tokens: 0 });
  const [models, setModels] = useState<ModelUsage[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [usageRes, modelRes] = await Promise.all([
        analyticsApi.getUsage({ days }),
        analyticsApi.getByModel(days),
      ]);
      setItems(usageRes.items);
      setSummary(usageRes.summary);
      setModels(modelRes.items);
    } catch {
      // SQLite 环境会返回空数据，不报错
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 size={20} className="text-purple-500" />
            <h1 className="text-lg font-semibold text-gray-800">用量统计</h1>
          </div>
          <div className="flex gap-1">
            {DAYS_OPTIONS.map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                  days === d
                    ? 'bg-purple-600 text-white'
                    : 'border border-gray-200 text-gray-500 hover:bg-gray-50'
                }`}
              >
                {d}天
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard icon={<TrendingUp size={16} />} label="总 Tokens" value={fmt(summary.total_tokens)} sub={`输入 ${fmt(summary.total_input)} / 输出 ${fmt(summary.total_output)}`} />
          <StatCard icon={<MessageSquare size={16} />} label="消息总数" value={fmt(summary.total_messages)} />
          <StatCard icon={<Cpu size={16} />} label="输入 Tokens" value={fmt(summary.total_input)} />
          <StatCard icon={<Wrench size={16} />} label="输出 Tokens" value={fmt(summary.total_output)} />
        </div>

        {/* Daily chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-1.5">
            <TrendingUp size={14} className="text-purple-500" />每日 Token 用量
          </h2>
          {loading ? (
            <div className="h-40 flex items-center justify-center text-gray-400 text-sm">加载中…</div>
          ) : (
            <DailyChart items={items} />
          )}
        </div>

        {/* Model breakdown */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-1.5">
            <Cpu size={14} className="text-purple-500" />模型用量分布
          </h2>
          {loading ? (
            <div className="text-center text-gray-400 text-sm py-6">加载中…</div>
          ) : (
            <ModelTable items={models} />
          )}
        </div>

        {/* SQLite hint */}
        {items.length === 0 && !loading && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700">
            💡 用量统计仅在 MySQL 环境下记录。当前为 SQLite 模式，数据为空。
          </div>
        )}
      </div>
    </div>
  );
}
