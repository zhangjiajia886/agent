import { useCallback, useRef, useState } from 'react';
import {
  Upload, X, AlertTriangle, FileText, CheckCircle2,
  XCircle, Loader2, Plus, ChevronDown, ChevronUp,
} from 'lucide-react';
import { importDifyDSL } from '@/utils/difyImporter';
import type { ImportResult } from '@/utils/difyImporter';
import { workflowApi } from '@/api/workflows';

// ── Types ──────────────────────────────────────────────────────────────────────

type FileStatus = 'parse-error' | 'pending' | 'importing' | 'success' | 'warning' | 'error';

interface FileEntry {
  id: string;
  fileName: string;
  parsed: ImportResult | null;
  parseError: string;
  status: FileStatus;
  apiError: string;
}

interface DifyImportDialogProps {
  open: boolean;
  onClose: () => void;
  onDone: (successCount: number) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function statusIcon(s: FileStatus) {
  if (s === 'importing') return <Loader2 size={13} className="animate-spin text-blue-500" />;
  if (s === 'success')   return <CheckCircle2 size={13} className="text-green-500" />;
  if (s === 'warning')   return <AlertTriangle size={13} className="text-yellow-500" />;
  if (s === 'error' || s === 'parse-error') return <XCircle size={13} className="text-red-500" />;
  return <FileText size={13} className="text-gray-400" />;
}

function statusLabel(e: FileEntry) {
  if (e.status === 'parse-error') return <span className="text-red-500">{e.parseError}</span>;
  if (e.status === 'importing')   return <span className="text-blue-500">导入中…</span>;
  if (e.status === 'success')     return <span className="text-green-600">导入成功 · {e.parsed!.name}</span>;
  if (e.status === 'warning')     return <span className="text-yellow-600">已导入（{e.parsed!.warnings.length} 条警告）</span>;
  if (e.status === 'error')       return <span className="text-red-500">{e.apiError || '导入失败'}</span>;
  return <span className="text-gray-500 truncate">{e.parsed?.name ?? e.fileName}</span>;
}

async function parseFile(file: File): Promise<FileEntry> {
  const id = `${Date.now()}_${Math.random().toString(36).slice(2)}`;
  try {
    const text = await file.text();
    const parsed = importDifyDSL(text);
    return { id, fileName: file.name, parsed, parseError: '', status: 'pending', apiError: '' };
  } catch (err) {
    return {
      id, fileName: file.name, parsed: null,
      parseError: err instanceof Error ? err.message : '解析失败',
      status: 'parse-error', apiError: '',
    };
  }
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function DifyImportDialog({ open, onClose, onDone }: DifyImportDialogProps) {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [running, setRunning] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [pasteError, setPasteError] = useState('');
  const [showPaste, setShowPaste] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef(false);

  const addFiles = useCallback(async (files: FileList | File[]) => {
    const arr = Array.from(files).filter(f => /\.(yml|yaml|json)$/i.test(f.name));
    if (!arr.length) return;
    const parsed = await Promise.all(arr.map(parseFile));
    setEntries(prev => {
      const existing = new Set(prev.map(e => e.fileName));
      return [...prev, ...parsed.filter(p => !existing.has(p.fileName))];
    });
  }, []);

  const handleFileInput = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) await addFiles(e.target.files);
    e.target.value = '';
  }, [addFiles]);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    await addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const removeEntry = (id: string) => setEntries(prev => prev.filter(e => e.id !== id));

  const clearAll = () => setEntries([]);

  async function handlePasteAdd() {
    if (!pasteText.trim()) return;
    setPasteError('');
    try {
      const parsed = importDifyDSL(pasteText.trim());
      const id = `paste_${Date.now()}`;
      const entry: FileEntry = { id, fileName: `${parsed.name}.yml`, parsed, parseError: '', status: 'pending', apiError: '' };
      setEntries(prev => [...prev, entry]);
      setPasteText('');
      setShowPaste(false);
    } catch (err) {
      setPasteError(err instanceof Error ? err.message : '解析失败');
    }
  }

  async function handleImportAll() {
    const toImport = entries.filter(e => e.status === 'pending' || e.status === 'warning' || e.status === 'error');
    if (!toImport.length) return;
    setRunning(true);
    abortRef.current = false;
    let successCount = 0;

    for (const entry of toImport) {
      if (abortRef.current) break;
      if (!entry.parsed) continue;

      setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'importing' } : e));
      try {
        await workflowApi.create({
          name: entry.parsed.name,
          description: entry.parsed.description,
          definition: entry.parsed.definition as Record<string, unknown>,
          tags: ['dify-import'],
        });
        const newStatus: FileStatus = entry.parsed.warnings.length > 0 ? 'warning' : 'success';
        setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: newStatus } : e));
        successCount++;
      } catch {
        setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'error', apiError: 'API 调用失败' } : e));
      }
    }
    setRunning(false);
    if (successCount > 0) onDone(successCount);
  }

  function handleClose() {
    if (running) { abortRef.current = true; }
    setEntries([]);
    setPasteText('');
    setPasteError('');
    setShowPaste(false);
    onClose();
  }

  if (!open) return null;

  const pendingCount = entries.filter(e => e.status === 'pending').length;
  const successCount = entries.filter(e => e.status === 'success' || e.status === 'warning').length;
  const errorCount = entries.filter(e => e.status === 'error' || e.status === 'parse-error').length;
  const importableCount = entries.filter(e => e.status === 'pending' || e.status === 'error').length;
  const total = entries.length;
  const doneCount = entries.filter(e => ['success', 'warning', 'error', 'parse-error'].includes(e.status)).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-[680px] max-h-[88vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <div className="font-semibold text-gray-900">批量导入 Dify 工作流</div>
            <div className="text-xs text-gray-400 mt-0.5">
              支持同时导入多个 .yml / .yaml / .json 文件
            </div>
          </div>
          <button onClick={handleClose} className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-400">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 min-h-0">

          {/* Dropzone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            className={`flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${
              dragging ? 'border-purple-400 bg-purple-50' : 'border-gray-200 hover:border-purple-300 hover:bg-gray-50'
            }`}
          >
            <Upload size={20} className={dragging ? 'text-purple-500' : 'text-gray-400'} />
            <div className="text-sm text-gray-500">
              <span className="text-purple-600 font-medium">点击选择</span> 或拖拽文件到这里
            </div>
            <div className="text-xs text-gray-400">支持批量选择 .yml / .yaml / .json · 同名文件自动跳过</div>
            <input
              ref={fileRef}
              type="file"
              accept=".yml,.yaml,.json"
              multiple
              onChange={handleFileInput}
              className="hidden"
            />
          </div>

          {/* How to export hint */}
          <div className="flex gap-2 p-2.5 bg-blue-50 border border-blue-100 rounded-lg text-xs text-blue-600">
            <FileText size={13} className="shrink-0 mt-0.5" />
            <span>Dify 导出方式：工作流页 → 右上角菜单 → <b>导出 DSL</b> → 下载 .yml 文件</span>
          </div>

          {/* File list */}
          {entries.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-medium text-gray-500">
                  已选 {total} 个文件
                  {successCount > 0 && <span className="ml-2 text-green-600">✓ {successCount} 成功</span>}
                  {errorCount > 0 && <span className="ml-2 text-red-500">✗ {errorCount} 失败</span>}
                </div>
                {!running && (
                  <button onClick={clearAll} className="text-xs text-gray-400 hover:text-red-500 transition-colors">
                    全部清除
                  </button>
                )}
              </div>
              <div className="space-y-1 max-h-[280px] overflow-y-auto pr-1">
                {entries.map(entry => (
                  <div
                    key={entry.id}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs border ${
                      entry.status === 'success' ? 'bg-green-50 border-green-100' :
                      entry.status === 'warning' ? 'bg-yellow-50 border-yellow-100' :
                      entry.status === 'error' || entry.status === 'parse-error' ? 'bg-red-50 border-red-100' :
                      entry.status === 'importing' ? 'bg-blue-50 border-blue-100' :
                      'bg-gray-50 border-gray-100'
                    }`}
                  >
                    {statusIcon(entry.status)}
                    <span className="font-mono text-gray-500 shrink-0 w-40 truncate">{entry.fileName}</span>
                    <span className="flex-1 truncate">{statusLabel(entry)}</span>
                    {entry.parsed?.warnings.length ? (
                      <span className="text-[10px] text-yellow-500 shrink-0">{entry.parsed.warnings.length} 警告</span>
                    ) : null}
                    {!running && entry.status !== 'importing' && (
                      <button
                        onClick={() => removeEntry(entry.id)}
                        className="p-0.5 rounded hover:bg-gray-200 text-gray-300 hover:text-gray-500 shrink-0"
                      >
                        <X size={11} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Progress bar (during import) */}
          {running && total > 0 && (
            <div>
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>正在导入…</span>
                <span>{doneCount} / {total}</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-purple-500 rounded-full transition-all duration-300"
                  style={{ width: `${total > 0 ? (doneCount / total) * 100 : 0}%` }}
                />
              </div>
            </div>
          )}

          {/* Paste section */}
          <div className="border border-gray-100 rounded-xl overflow-hidden">
            <button
              onClick={() => setShowPaste(v => !v)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-gray-500 hover:bg-gray-50 transition-colors"
            >
              <span className="font-medium">或直接粘贴单个 DSL 内容</span>
              {showPaste ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
            {showPaste && (
              <div className="px-4 pb-4 space-y-2">
                <textarea
                  value={pasteText}
                  onChange={e => { setPasteText(e.target.value); setPasteError(''); }}
                  rows={8}
                  placeholder="粘贴 Dify DSL YAML 或 JSON 内容…"
                  className="w-full text-xs font-mono bg-gray-50 border border-gray-200 rounded-lg px-3 py-2.5 outline-none focus:border-purple-400 resize-none"
                />
                {pasteError && (
                  <div className="flex items-center gap-1.5 text-xs text-red-500">
                    <AlertTriangle size={12} />
                    {pasteError}
                  </div>
                )}
                <button
                  onClick={handlePasteAdd}
                  disabled={!pasteText.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 rounded-lg disabled:opacity-40 transition-colors"
                >
                  <Plus size={12} />
                  加入队列
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
          <div className="text-xs text-gray-400">
            {pendingCount > 0 ? `${pendingCount} 个文件等待导入` : total > 0 ? '全部处理完成' : '未选择文件'}
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              {running ? '中止' : '关闭'}
            </button>
            <button
              onClick={handleImportAll}
              disabled={running || importableCount === 0}
              className="flex items-center gap-1.5 px-5 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-40 transition-colors"
            >
              {running ? (
                <><Loader2 size={14} className="animate-spin" />导入中…</>
              ) : (
                <><Upload size={14} />导入全部 ({importableCount})</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
