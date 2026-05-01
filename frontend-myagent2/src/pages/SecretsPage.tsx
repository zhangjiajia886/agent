import { useState } from 'react';
import { KeyRound, Plus, Pencil, Trash2, X, Eye, EyeOff, ShieldCheck } from 'lucide-react';
import PageHeader from '@/components/layout/PageHeader';
import type { SecretItem } from '@/types/entities';

const INITIAL_SECRETS: SecretItem[] = [
  {
    name: 'OPENAI_API_KEY',
    description: 'OpenAI API 密钥',
    reference: '${OPENAI_API_KEY}',
    createdAt: '2025-04-05',
    updatedAt: '2025-04-10',
  },
  {
    name: 'GITHUB_TOKEN',
    description: 'GitHub Personal Access Token',
    reference: '${GITHUB_TOKEN}',
    createdAt: '2025-04-06',
    updatedAt: '2025-04-06',
  },
  {
    name: 'DEEPSEEK_API_KEY',
    description: 'DeepSeek API 密钥',
    reference: '${DEEPSEEK_API_KEY}',
    createdAt: '2025-04-08',
    updatedAt: '2025-04-12',
  },
  {
    name: 'DB_PASSWORD',
    description: '数据库连接密码',
    reference: '${DB_PASSWORD}',
    createdAt: '2025-04-01',
    updatedAt: '2025-04-01',
  },
];

export default function SecretsPage() {
  const [secrets, setSecrets] = useState<SecretItem[]>(INITIAL_SECRETS);
  const [showDialog, setShowDialog] = useState(false);
  const [editingSecret, setEditingSecret] = useState<SecretItem | null>(null);

  function handleSave(name: string, description: string, _value: string) {
    const now = new Date().toISOString();
    setSecrets((prev) => {
      const idx = prev.findIndex((s) => s.name === name);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], description, updatedAt: now };
        return next;
      }
      return [...prev, { name, description, reference: `\${${name}}`, createdAt: now, updatedAt: now }];
    });
    setShowDialog(false);
    setEditingSecret(null);
  }

  function handleDelete(name: string) {
    setSecrets((prev) => prev.filter((s) => s.name !== name));
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="密钥管理"
        description="加密存储敏感信息，在配置中通过 ${NAME} 引用"
        icon={<KeyRound size={24} />}
        actions={
          <button
            onClick={() => { setEditingSecret(null); setShowDialog(true); }}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
          >
            <Plus size={16} />
            添加密钥
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-6">
        {/* 安全提示 */}
        <div className="flex items-start gap-3 mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <ShieldCheck size={20} className="text-amber-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">密钥值使用 Fernet 对称加密存储</p>
            <p className="text-xs text-amber-600 mt-1">
              界面仅显示密钥名称和引用方式，不会展示实际值。在模型配置、MCP 环境变量、工具参数中通过 <code className="bg-amber-100 px-1 rounded">{'${SECRET_NAME}'}</code> 引用。
            </p>
          </div>
        </div>

        {/* 密钥表格 */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">名称</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">描述</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">引用方式</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">更新时间</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {secrets.map((secret) => (
                <tr key={secret.name} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-5 py-3">
                    <span className="font-mono text-sm font-medium text-gray-900">{secret.name}</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-sm text-gray-600">{secret.description}</span>
                  </td>
                  <td className="px-5 py-3">
                    <code className="text-xs bg-gray-100 text-purple-600 px-2 py-1 rounded font-mono">
                      {secret.reference}
                    </code>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-xs text-gray-400">{secret.updatedAt}</span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => { setEditingSecret(secret); setShowDialog(true); }}
                        className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(secret.name)}
                        className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {secrets.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-gray-400 text-sm">
                    暂无密钥，点击「添加密钥」开始
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showDialog && (
        <SecretEditDialog
          secret={editingSecret}
          onSave={handleSave}
          onClose={() => { setShowDialog(false); setEditingSecret(null); }}
        />
      )}
    </div>
  );
}

function SecretEditDialog({
  secret,
  onSave,
  onClose,
}: {
  secret: SecretItem | null;
  onSave: (name: string, description: string, value: string) => void;
  onClose: () => void;
}) {
  const isNew = !secret;
  const [name, setName] = useState(secret?.name ?? '');
  const [description, setDescription] = useState(secret?.description ?? '');
  const [value, setValue] = useState('');
  const [showValue, setShowValue] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-[460px]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">
            {isNew ? '添加密钥' : `编辑: ${secret.name}`}
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
            <X size={18} className="text-gray-400" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">密钥名称</label>
            <input
              className="input-base font-mono"
              value={name}
              onChange={(e) => setName(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ''))}
              placeholder="OPENAI_API_KEY"
              disabled={!isNew}
            />
            {isNew && <p className="text-[10px] text-gray-400 mt-1">只允许大写字母、数字和下划线</p>}
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">描述</label>
            <input
              className="input-base"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="OpenAI API 密钥"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">
              {isNew ? '密钥值' : '新密钥值（留空则不修改）'}
            </label>
            <div className="relative">
              <input
                type={showValue ? 'text' : 'password'}
                className="input-base font-mono pr-10"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={isNew ? '输入密钥值...' : '留空不修改'}
              />
              <button
                type="button"
                onClick={() => setShowValue(!showValue)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
              >
                {showValue ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
            取消
          </button>
          <button
            onClick={() => onSave(name, description, value)}
            disabled={!name || (isNew && !value)}
            className="px-4 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
