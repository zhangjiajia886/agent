import { useEffect, useMemo, useState } from 'react';
import { Cpu, Plus, Star, Wifi, WifiOff, CircleDot, Pencil, X, FlaskConical, Trash2 } from 'lucide-react';
import PageHeader from '@/components/layout/PageHeader';
import type { ModelConfig } from '@/types/entities';
import { toast } from 'sonner';
import { modelApi, type ModelDTO } from '@/api/models';

const PROVIDER_LABELS: Record<string, { label: string; color: string }> = {
  ollama: { label: 'Ollama (本地)', color: 'bg-green-100 text-green-700' },
  openai: { label: 'OpenAI', color: 'bg-blue-100 text-blue-700' },
  anthropic: { label: 'Anthropic', color: 'bg-orange-100 text-orange-700' },
  deepseek: { label: 'DeepSeek', color: 'bg-cyan-100 text-cyan-700' },
  custom: { label: '自定义', color: 'bg-gray-100 text-gray-700' },
};

function dtoToModel(dto: ModelDTO): ModelConfig {
  const cfg = dto.config ?? {};
  const usageTags = Array.isArray(cfg.usage_tags) ? (cfg.usage_tags as ModelConfig['usageTags']) : ['inference'];
  return {
    id: dto.id,
    name: dto.name,
    provider: (dto.provider as ModelConfig['provider']) || 'custom',
    endpoint: dto.api_base || '',
    modelId: dto.model_id,
    apiKeyRef: dto.api_key_ref || undefined,
    contextWindow: Number(cfg.context_window ?? 32768),
    defaultTemperature: Number(cfg.default_temperature ?? 0.7),
    defaultTopP: Number(cfg.default_top_p ?? 0.9),
    defaultMaxTokens: dto.max_tokens,
    inputPricePerMToken: Number(cfg.input_price_per_m_token ?? 0),
    outputPricePerMToken: Number(cfg.output_price_per_m_token ?? 0),
    capabilities: {
      functionCalling: Boolean(cfg.function_calling ?? true),
      streaming: Boolean(cfg.streaming ?? true),
      vision: Boolean(cfg.vision ?? false),
    },
    usageTags,
    isDefault: dto.is_default,
    status: dto.api_key_ref || dto.provider === 'ollama' ? 'online' : 'unconfigured',
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

export default function ModelConfigPage() {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null);
  const [showDialog, setShowDialog] = useState(false);

  async function loadModels() {
    try {
      const res = await modelApi.list();
      setModels(res.items.map(dtoToModel));
    } catch {
      toast.error('加载模型列表失败');
    }
  }

  useEffect(() => {
    loadModels();
  }, []);

  // 按 provider 分组
  const grouped = useMemo(() => models.reduce((acc, m) => {
    (acc[m.provider] ??= []).push(m);
    return acc;
  }, {} as Record<string, ModelConfig[]>), [models]);

  async function handleSave(model: ModelConfig) {
    try {
      const payload = {
        provider: model.provider,
        name: model.name,
        model_id: model.modelId,
        api_base: model.endpoint,
        api_key_ref: model.apiKeyRef,
        is_default: model.isDefault,
        max_tokens: model.defaultMaxTokens,
        config: {
          context_window: model.contextWindow,
          default_temperature: model.defaultTemperature,
          default_top_p: model.defaultTopP,
          input_price_per_m_token: model.inputPricePerMToken,
          output_price_per_m_token: model.outputPricePerMToken,
          function_calling: model.capabilities.functionCalling,
          streaming: model.capabilities.streaming,
          vision: model.capabilities.vision,
          usage_tags: model.usageTags,
        },
      };
      const exists = models.some((m) => m.id === model.id);
      if (exists) {
        await modelApi.update(model.id, {
          name: payload.name,
          api_base: payload.api_base,
          api_key_ref: payload.api_key_ref,
          is_default: payload.is_default,
          max_tokens: payload.max_tokens,
          config: payload.config,
        });
      } else {
        await modelApi.create(payload);
      }
      await loadModels();
      setShowDialog(false);
      setEditingModel(null);
      toast.success('模型配置已保存');
    } catch {
      toast.error('保存模型配置失败');
    }
  }

  async function handleSetDefault(id: string) {
    try {
      await modelApi.setDefault(id);
      await loadModels();
      toast.success('默认模型已更新');
    } catch {
      toast.error('设置默认模型失败');
    }
  }

  async function handleDelete(id: string) {
    try {
      await modelApi.delete(id);
      await loadModels();
      toast.success('模型已删除');
    } catch {
      toast.error('删除模型失败');
    }
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="模型配置"
        description="管理 LLM 模型 Provider 和连接"
        icon={<Cpu size={24} />}
        actions={
          <button
            onClick={() => {
              setEditingModel(null);
              setShowDialog(true);
            }}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
          >
            <Plus size={16} />
            添加模型
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {Object.entries(grouped).map(([provider, list]) => {
          const prov = PROVIDER_LABELS[provider] || PROVIDER_LABELS.custom;
          return (
            <div key={provider} className="bg-white rounded-xl border border-gray-200">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${prov.color}`}>
                  {prov.label}
                </span>
                <span className="text-xs text-gray-400">{list.length} 个模型</span>
              </div>

              <div className="divide-y divide-gray-50">
                {list.map((model) => (
                  <ModelRow
                    key={model.id}
                    model={model}
                    onEdit={() => { setEditingModel(model); setShowDialog(true); }}
                    onSetDefault={() => handleSetDefault(model.id)}
                    onDelete={() => handleDelete(model.id)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* 编辑弹窗 */}
      {showDialog && (
        <ModelEditDialog
          model={editingModel}
          onSave={handleSave}
          onClose={() => { setShowDialog(false); setEditingModel(null); }}
        />
      )}
    </div>
  );
}

function ModelRow({
  model,
  onEdit,
  onSetDefault,
  onDelete,
}: {
  model: ModelConfig;
  onEdit: () => void;
  onSetDefault: () => void;
  onDelete: () => void;
}) {
  const statusIcon = model.status === 'online' ? (
    <Wifi size={14} className="text-green-500" />
  ) : model.status === 'offline' ? (
    <WifiOff size={14} className="text-red-400" />
  ) : (
    <CircleDot size={14} className="text-gray-400" />
  );

  const statusLabel = model.status === 'online' ? '在线' : model.status === 'offline' ? '离线' : '未配置';

  return (
    <div className="px-5 py-3 flex items-center gap-4 hover:bg-gray-50/50 transition-colors">
      {/* 状态 */}
      <div className="flex items-center gap-1.5 w-16 shrink-0">
        {statusIcon}
        <span className="text-xs text-gray-500">{statusLabel}</span>
      </div>

      {/* 名称 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-gray-900">{model.name}</span>
          {model.isDefault && (
            <span className="flex items-center gap-0.5 text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">
              <Star size={10} /> 默认
            </span>
          )}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {model.endpoint} · {model.modelId}
        </div>
      </div>

      {/* 上下文窗口 */}
      <div className="text-xs text-gray-500 w-28 text-right shrink-0">
        {(model.contextWindow / 1000).toFixed(0)}K tokens
      </div>

      {/* 费率 */}
      <div className="text-xs text-gray-400 w-36 text-right shrink-0">
        {model.inputPricePerMToken === 0
          ? '免费（本地）'
          : `$${model.inputPricePerMToken} / $${model.outputPricePerMToken} per M`}
      </div>

      {/* 能力标签 */}
      <div className="flex gap-1 w-32 shrink-0">
        {model.capabilities.functionCalling && (
          <span className="text-[10px] px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded">FC</span>
        )}
        {model.capabilities.streaming && (
          <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">Stream</span>
        )}
        {model.capabilities.vision && (
          <span className="text-[10px] px-1.5 py-0.5 bg-green-50 text-green-600 rounded">Vision</span>
        )}
      </div>

      {/* 操作 */}
      <div className="flex items-center gap-1 shrink-0">
        {!model.isDefault && (
          <button
            onClick={onSetDefault}
            title="设为默认"
            className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-amber-500 transition-colors"
          >
            <Star size={14} />
          </button>
        )}
        <button
          title="测试连接"
          className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-green-500 transition-colors"
        >
          <FlaskConical size={14} />
        </button>
        <button
          onClick={onEdit}
          className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <Pencil size={14} />
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

// ===== 编辑弹窗 =====
function ModelEditDialog({
  model,
  onSave,
  onClose,
}: {
  model: ModelConfig | null;
  onSave: (m: ModelConfig) => void;
  onClose: () => void;
}) {
  const isNew = !model;
  const [form, setForm] = useState<ModelConfig>(
    model ?? {
      id: `m_${Date.now()}`,
      name: '',
      provider: 'ollama',
      endpoint: 'http://localhost:11434',
      modelId: '',
      contextWindow: 32768,
      defaultTemperature: 0.7,
      defaultTopP: 0.9,
      defaultMaxTokens: 2048,
      inputPricePerMToken: 0,
      outputPricePerMToken: 0,
      capabilities: { functionCalling: true, streaming: true, vision: false },
      usageTags: ['inference'],
      isDefault: false,
      status: 'offline',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  );

  const set = (partial: Partial<ModelConfig>) => setForm((prev) => ({ ...prev, ...partial }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-[520px] max-h-[85vh] flex flex-col">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">
            {isNew ? '添加模型' : `编辑: ${model.name}`}
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
            <X size={18} className="text-gray-400" />
          </button>
        </div>

        {/* 表单 */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <FormField label="名称">
            <input className="input-base" value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="qwen3-32b" />
          </FormField>

          <FormField label="Provider">
            <select className="input-base" value={form.provider} onChange={(e) => set({ provider: e.target.value as ModelConfig['provider'] })}>
              <option value="ollama">Ollama (本地)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="deepseek">DeepSeek</option>
              <option value="custom">自定义 (OpenAI 兼容)</option>
            </select>
          </FormField>

          <FormField label="端点 URL">
            <input className="input-base font-mono text-xs" value={form.endpoint} onChange={(e) => set({ endpoint: e.target.value })} />
          </FormField>

          <FormField label="模型 ID">
            <input className="input-base font-mono text-xs" value={form.modelId} onChange={(e) => set({ modelId: e.target.value })} placeholder="qwen3:32b" />
          </FormField>

          {form.provider !== 'ollama' && (
            <FormField label="API Key（引用密钥名）">
              <input
                className="input-base font-mono text-xs"
                value={form.apiKeyRef || ''}
                onChange={(e) => set({ apiKeyRef: e.target.value })}
                placeholder="OPENAI_API_KEY"
              />
              <p className="text-[10px] text-gray-400 mt-1">在「密钥管理」中配置实际值，此处仅填写密钥名称</p>
            </FormField>
          )}

          <div className="grid grid-cols-2 gap-3">
            <FormField label="上下文窗口">
              <input type="number" className="input-base" value={form.contextWindow} onChange={(e) => set({ contextWindow: parseInt(e.target.value) || 0 })} />
            </FormField>
            <FormField label="默认最大输出">
              <input type="number" className="input-base" value={form.defaultMaxTokens} onChange={(e) => set({ defaultMaxTokens: parseInt(e.target.value) || 0 })} />
            </FormField>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="默认温度">
              <input type="number" step="0.1" min="0" max="2" className="input-base" value={form.defaultTemperature} onChange={(e) => set({ defaultTemperature: parseFloat(e.target.value) || 0 })} />
            </FormField>
            <FormField label="默认 Top-P">
              <input type="number" step="0.1" min="0" max="1" className="input-base" value={form.defaultTopP} onChange={(e) => set({ defaultTopP: parseFloat(e.target.value) || 0 })} />
            </FormField>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="输入费率 ($/M tokens)">
              <input type="number" step="0.01" className="input-base" value={form.inputPricePerMToken} onChange={(e) => set({ inputPricePerMToken: parseFloat(e.target.value) || 0 })} />
            </FormField>
            <FormField label="输出费率 ($/M tokens)">
              <input type="number" step="0.01" className="input-base" value={form.outputPricePerMToken} onChange={(e) => set({ outputPricePerMToken: parseFloat(e.target.value) || 0 })} />
            </FormField>
          </div>

          <FormField label="模型能力">
            <div className="flex items-center gap-4 py-1">
              <label className="flex items-center gap-1.5 text-xs text-gray-700">
                <input type="checkbox" checked={form.capabilities.functionCalling} onChange={(e) => set({ capabilities: { ...form.capabilities, functionCalling: e.target.checked } })} />
                Function Calling
              </label>
              <label className="flex items-center gap-1.5 text-xs text-gray-700">
                <input type="checkbox" checked={form.capabilities.streaming} onChange={(e) => set({ capabilities: { ...form.capabilities, streaming: e.target.checked } })} />
                Streaming
              </label>
              <label className="flex items-center gap-1.5 text-xs text-gray-700">
                <input type="checkbox" checked={form.capabilities.vision} onChange={(e) => set({ capabilities: { ...form.capabilities, vision: e.target.checked } })} />
                Vision
              </label>
            </div>
          </FormField>
        </div>

        {/* 底部 */}
        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between">
          <button className="px-3 py-1.5 text-sm text-green-600 hover:bg-green-50 rounded-lg transition-colors">
            测试连接
          </button>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
              取消
            </button>
            <button
              onClick={() => onSave({ ...form, updatedAt: new Date().toISOString() })}
              className="px-4 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-600 block mb-1">{label}</label>
      {children}
    </div>
  );
}
