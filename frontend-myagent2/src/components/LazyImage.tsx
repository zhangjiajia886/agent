import { useState, useCallback } from 'react';
import { Maximize2, X } from 'lucide-react';

function isAbsoluteUrl(src: string) {
  return src.startsWith('http://') || src.startsWith('https://') ||
         src.startsWith('/api/') || src.startsWith('data:');
}

export function LazyImage({ src, alt = '' }: { src: string; alt?: string }) {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading');
  const [fullscreen, setFullscreen] = useState(false);

  const handleLoad = useCallback(() => setStatus('loaded'), []);
  const handleError = useCallback(() => setStatus('error'), []);

  // Block relative paths (LLM hallucinated local filenames like "sine_cosine.png")
  if (!isAbsoluteUrl(src)) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded border border-amber-100">
        🖼️ 图片需通过工具生成后自动展示（本地路径无法直接访问：{src}）
      </span>
    );
  }

  if (status === 'error') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-400 bg-red-50 px-2 py-1 rounded">
        🖼️ 图片加载失败
        {src && <a href={src} target="_blank" rel="noreferrer" className="underline ml-1 truncate max-w-[200px]">{src}</a>}
      </span>
    );
  }

  return (
    <>
      <span className="relative inline-block group">
        {status === 'loading' && (
          <span className="absolute inset-0 bg-gray-100 animate-pulse rounded-lg" style={{ minWidth: 120, minHeight: 80 }} />
        )}
        <img
          src={src}
          alt={alt}
          onLoad={handleLoad}
          onError={handleError}
          className={`max-w-full rounded-lg border border-gray-200 transition-opacity ${status === 'loaded' ? 'opacity-100' : 'opacity-0'}`}
          style={{ maxHeight: 480 }}
        />
        {status === 'loaded' && (
          <button
            onClick={() => setFullscreen(true)}
            className="absolute top-2 right-2 p-1 bg-black/40 text-white rounded opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <Maximize2 size={13} />
          </button>
        )}
      </span>

      {fullscreen && (
        <>
          <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setFullscreen(false)}>
            <img src={src} alt={alt} className="max-w-full max-h-full rounded-lg" onClick={e => e.stopPropagation()} />
          </div>
          <button className="fixed top-4 right-4 z-50 p-2 bg-white/20 text-white rounded-full hover:bg-white/30" onClick={() => setFullscreen(false)}>
            <X size={20} />
          </button>
        </>
      )}
    </>
  );
}

/** Detect if a raw URL string points to an image */
export const IMG_URL_RE = /^https?:\/\/\S+\.(png|jpg|jpeg|gif|webp|svg|bmp)(\?[^\s]*)?$/i;
