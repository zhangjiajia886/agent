import { useEffect, useMemo, useState } from 'react';
import { Play, X } from 'lucide-react';

interface RunWorkflowDialogProps {
  open: boolean;
  title: string;
  inputFields: string[];
  defaultValues?: Record<string, string>;
  onClose: () => void;
  onSubmit: (inputs: Record<string, unknown>) => Promise<void>;
}

export default function RunWorkflowDialog({ open, title, inputFields, defaultValues, onClose, onSubmit }: RunWorkflowDialogProps) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const normalizedFields = useMemo(
    () => Array.from(new Set(inputFields.map((item) => item.trim()).filter(Boolean))),
    [inputFields],
  );

  useEffect(() => {
    if (!open) return;
    setValues(Object.fromEntries(normalizedFields.map((field) => [field, defaultValues?.[field] ?? ''])));
  }, [normalizedFields, open]);

  if (!open) return null;

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(values)
          .filter(([, value]) => value.trim() !== '')
          .map(([key, value]) => [key, value]),
      );
      await onSubmit(payload);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <div className="text-sm font-semibold text-gray-900">运行工作流</div>
            <div className="text-xs text-gray-400 mt-0.5">{title}</div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
            <X size={16} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {normalizedFields.length === 0 ? (
            <div className="text-sm text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-3 py-3">
              该工作流未声明输入变量，将以空输入运行。
            </div>
          ) : (
            <div className="space-y-3">
              {normalizedFields.map((field) => (
                <div key={field}>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{field}</label>
                  <textarea
                    value={values[field] ?? ''}
                    onChange={(e) => setValues((prev) => ({ ...prev, [field]: e.target.value }))}
                    rows={3}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-100 resize-y"
                    placeholder={`请输入 ${field}`}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 bg-gray-50">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg bg-white border border-gray-200 text-gray-600 hover:bg-gray-50">
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50"
          >
            <Play size={14} />
            {submitting ? '启动中...' : '启动执行'}
          </button>
        </div>
      </div>
    </div>
  );
}
