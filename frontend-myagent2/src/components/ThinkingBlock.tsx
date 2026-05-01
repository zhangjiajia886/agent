import { useState } from 'react';
import { Brain, ChevronDown, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ThinkingBlockProps {
  thinking: string;
  loading?: boolean;
  thinkSeconds?: number;
}

export function ThinkingBlock({ thinking, loading, thinkSeconds }: ThinkingBlockProps) {
  const [open, setOpen] = useState(false);
  const isStreaming = loading && !thinkSeconds;
  const wordCount = thinking.length;

  return (
    <div className="mb-3">
      <button
        onClick={() => !isStreaming && setOpen(v => !v)}
        className="flex items-center gap-1.5 w-full text-left"
        disabled={isStreaming}
      >
        <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors ${
          isStreaming
            ? 'bg-violet-50 border-violet-200 text-violet-600'
            : 'bg-gray-50 border-gray-200 text-gray-500 hover:bg-gray-100'
        }`}>
          {isStreaming ? (
            <>
              <span className="text-[10px]">●</span>
              <span className="text-xs font-medium">正在思考</span>
              <span className="flex gap-0.5 items-end h-3 ml-0.5">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-0.5 bg-violet-400 rounded-full animate-bounce"
                    style={{ height: `${6 + i * 2}px`, animationDelay: `${i * 0.15}s`, animationDuration: '0.8s' }}
                  />
                ))}
              </span>
            </>
          ) : (
            <>
              <Brain size={11} />
              <span className="text-xs font-medium">
                {thinkSeconds ? `已思考 ${thinkSeconds}s` : '思考过程'}
              </span>
              <span className="text-[10px] text-gray-400 ml-0.5">
                · {wordCount > 999 ? `${(wordCount / 1000).toFixed(1)}k` : wordCount} 字
              </span>
              {open ? <ChevronDown size={10} className="ml-0.5" /> : <ChevronRight size={10} className="ml-0.5" />}
            </>
          )}
        </div>
      </button>

      {open && thinking && (
        <div className="mt-2 px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-500 max-h-56 overflow-y-auto leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{thinking}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
