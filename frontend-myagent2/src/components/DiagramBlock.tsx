import { useEffect, useRef, useState, useCallback, type ReactElement } from 'react';
import { Copy, Maximize2, X, Code2, Check } from 'lucide-react';

// ─── Mermaid ──────────────────────────────────────────────────────────────────
let _mermaidReady: Promise<typeof import('mermaid')['default']> | null = null;
let _mermaidIdSeq = 0;

function getMermaid() {
  if (!_mermaidReady) {
    _mermaidReady = import('mermaid').then(m => {
      m.default.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        fontFamily: 'system-ui, sans-serif',
      });
      return m.default;
    });
  }
  return _mermaidReady;
}

/** Auto-quote unquoted CJK text inside mermaid node/edge labels */
function autoQuoteCJK(src: string): string {
  // Only match brackets whose content has CJK AND is not already quoted (single or double)
  // e.g.  [开始] → ["开始"]   but  ["开始"] and ['开始'] stay unchanged
  return src
    .replace(/\[(?!["'])([^\]"']*[\u4e00-\u9fff\u3040-\u30ff][^\]"']*)\]/g, '["$1"]')
    .replace(/\{(?!["'])([^}"']*[\u4e00-\u9fff\u3040-\u30ff][^}"']*)\}/g, '{"$1"}')
    .replace(/\|(?!["'])([^|"']*[\u4e00-\u9fff\u3040-\u30ff][^|"']*)\|/g, '|"$1"|');
}

/** Strip/fix syntactically broken mermaid patterns */
function sanitizeMermaid(src: string): string {
  return src
    .split('\n')
    .filter(line => !/^\s*class\s+[\w,]+\s*$/.test(line))      // bare `class A,B` (no class name)
    .filter(line => !/^\s*classDef\s/.test(line))               // classDef lines (often broken)
    .map(line =>
      // Remove inline CSS-like content inside node brackets: A[fill:#fff,color:red] → A[A]
      line.replace(/\[([^\]]*(?:fill:|stroke:|color:|cursor:|font-)[^\]]*?)\]/g, (_, inner) => {
        // Extract just the text before any CSS
        const label = inner.split(/[,;]/)[0].replace(/[:#]\S*/g, '').trim();
        return `[${label || 'node'}]`;
      })
    )
    .join('\n');
}

function MermaidBlock({ code }: { code: string }) {
  const [error, setError] = useState('');
  const [svg, setSvg] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = await getMermaid();
        const id = `mer_${++_mermaidIdSeq}_${Date.now()}`;
        const src0 = code.trim();
        let result: { svg: string } | null = null;

        const isErrSvg = (r: { svg: string } | null) =>
          !r || !r.svg || r.svg.includes('error-icon') || r.svg.includes('error-text');

        /** Validate with parse() first; only render if valid — prevents error SVG injection */
        const safeRender = async (src: string, rid: string) => {
          try {
            // suppressErrors: true → returns false instead of throwing
            const valid = await mermaid.parse(src, { suppressErrors: true } as never);
            if (!valid) return null;
          } catch { return null; }
          try {
            const r = await mermaid.render(rid, src);
            return isErrSvg(r) ? null : r;
          } catch { return null; }
        };

        // Attempt 1: original
        result = await safeRender(src0, id + 'a');

        // Attempt 2: auto-quote CJK
        if (!result) result = await safeRender(autoQuoteCJK(src0), id + 'b');

        // Attempt 3: sanitize broken lines + quote CJK
        if (!result) result = await safeRender(autoQuoteCJK(sanitizeMermaid(src0)), id + 'c');

        if (result) {
          if (!cancelled) setSvg(result.svg);
          return;
        }

        // All local attempts failed — show raw code fallback (no external service needed)
        if (!cancelled) setError('mermaid syntax error');
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [code]);

  if (error) return <FallbackCode code={code} error={`Mermaid 语法错误: ${error.split('\n')[0]}`} />;
  if (!svg) return <div className="text-xs text-gray-400 italic p-3">渲染中…</div>;
  return (
    <div
      className="overflow-auto bg-white rounded-lg p-3 [&_svg]:max-w-full"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

// ─── Kroki renderer via local backend proxy (avoids CORS) ────────────────────
function KrokiBlock({ code, krokiType = 'plantuml' }: { code: string; krokiType?: string }) {
  const [svgContent, setSvgContent] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch('/api/diagram/render', {
          method: 'POST',
          body: JSON.stringify({ diagram_type: krokiType, source: code }),
          headers: { 'Content-Type': 'application/json' },
        });
        if (!resp.ok) {
          const msg = await resp.text();
          throw new Error(msg);
        }
        if (!cancelled) setSvgContent(await resp.text());
      } catch (e: unknown) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [code, krokiType]);

  if (error) return <FallbackCode code={code} error={error} />;
  if (!svgContent) return <div className="text-xs text-gray-400 italic p-3">渲染中…</div>;
  return (
    <div
      className="bg-white rounded-lg p-3 overflow-auto [&_svg]:max-w-full"
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
  );
}

function DrawioBlock({ code }: { code: string }) {
  return <KrokiBlock code={code} krokiType="diagramsnet" />;
}

// ─── PlantUML via kroki.io ───────────────────────────────────────────────────
function PlantUMLBlock({ code }: { code: string }) {
  return <KrokiBlock code={code} krokiType="plantuml" />;
}

// ─── Graphviz DOT via kroki.io ───────────────────────────────────────────────
function GraphvizBlock({ code }: { code: string }) {
  return <KrokiBlock code={code} krokiType="graphviz" />;
}

// ─── BPMN ─────────────────────────────────────────────────────────────────────
function BpmnBlock({ code }: { code: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('bpmn-js 渲染需先安装：npm install bpmn-js');
  }, []);

  if (error) return <FallbackCode code={code} error={error} />;
  return <div ref={containerRef} className="w-full rounded-lg border border-gray-200" style={{ height: 400 }} />;
}

// ─── Fallback: 显示原始代码 ──────────────────────────────────────────────────
function FallbackCode({ code, error }: { code: string; error?: string }) {
  return (
    <div>
      {error && <div className="text-xs text-red-500 mb-1 px-1">⚠️ 渲染失败: {error}</div>}
      <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs overflow-x-auto whitespace-pre-wrap">{code}</pre>
    </div>
  );
}

// ─── 外层容器（工具栏 + 全屏） ───────────────────────────────────────────────
const DIAGRAM_LANGS: Record<string, { label: string; component: (p: { code: string }) => ReactElement | null }> = {
  mermaid:  { label: 'Mermaid',   component: MermaidBlock },
  drawio:   { label: 'draw.io',   component: DrawioBlock },
  xml:      { label: 'draw.io',   component: DrawioBlock },
  plantuml: { label: 'PlantUML',  component: PlantUMLBlock },
  puml:     { label: 'PlantUML',  component: PlantUMLBlock },
  dot:      { label: 'Graphviz',  component: GraphvizBlock },
  graphviz: { label: 'Graphviz',  component: GraphvizBlock },
  bpmn:     { label: 'BPMN',      component: BpmnBlock },
};

export function isDiagramLang(lang: string): boolean {
  return lang.toLowerCase() in DIAGRAM_LANGS;
}

export function DiagramBlock({ lang, code }: { lang: string; code: string }) {
  const key = lang.toLowerCase();
  const meta = DIAGRAM_LANGS[key];
  const [showCode, setShowCode] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [copied, setCopied] = useState(false);

  const copy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [code]);

  if (!meta) return <FallbackCode code={code} />;
  const Renderer = meta.component;

  const content = (
    <div className={`rounded-xl border border-gray-200 overflow-hidden ${fullscreen ? 'fixed inset-4 z-50 shadow-2xl' : ''}`}>
      {/* 工具栏 */}
      <div className="flex items-center justify-between bg-gray-50 border-b border-gray-200 px-3 py-1.5">
        <span className="text-[11px] font-medium text-gray-500">{meta.label}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowCode(v => !v)}
            className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-700"
            title={showCode ? '查看图表' : '查看代码'}
          >
            <Code2 size={13} />
          </button>
          <button onClick={copy} className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-700" title="复制代码">
            {copied ? <Check size={13} className="text-green-500" /> : <Copy size={13} />}
          </button>
          <button onClick={() => setFullscreen(v => !v)} className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-700" title="全屏">
            {fullscreen ? <X size={13} /> : <Maximize2 size={13} />}
          </button>
        </div>
      </div>
      {/* 内容 */}
      <div className="bg-white" style={fullscreen ? { height: 'calc(100% - 36px)', overflow: 'auto' } : {}}>
        {showCode
          ? <pre className="bg-gray-900 text-gray-100 p-3 text-xs overflow-x-auto m-0 whitespace-pre-wrap">{code}</pre>
          : <Renderer code={code} />}
      </div>
    </div>
  );

  return (
    <>
      {content}
      {fullscreen && <div className="fixed inset-0 bg-black/50 z-40" onClick={() => setFullscreen(false)} />}
    </>
  );
}
