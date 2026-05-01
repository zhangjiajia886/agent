/**
 * 漫剧 Agent 前端工具函数（纯函数，无 Vue 依赖）
 */

// ──────────── Markdown 渲染 ────────────
export function renderMarkdown(raw: string): string {
  // 1. HTML 沙箱：```html ... ``` 渲染为 iframe srcdoc
  const blocks: string[] = []
  let text = raw.replace(/```(?:html|HTML)\n([\s\S]*?)\n```/g, (_, html) => {
    const srcdoc = html.trim()
      .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    const idx = blocks.length
    blocks.push(`<div class="html-sandbox-wrap"><iframe class="html-sandbox" srcdoc="${srcdoc}" sandbox="allow-scripts allow-same-origin" frameborder="0"></iframe></div>`)
    return `\x00BLOCK${idx}\x00`
  })

  // 2. 转义普通 HTML 字符
  text = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // 3. 表格  | col | col |
  text = text.replace(/((?:\|[^\n]+\|\n?)+)/g, (table) => {
    const rows = table.trim().split('\n').filter(r => !r.match(/^\|[-:\s|]+\|$/))
    const html = rows.map((r, i) => {
      const cells = r.split('|').slice(1, -1).map(c => c.trim())
      const tag = i === 0 ? 'th' : 'td'
      return '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>'
    }).join('')
    return `<table class="md-table"><tbody>${html}</tbody></table>`
  })

  // 4. 内联样式
  text = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^#{3}\s+(.+)$/gm, '<h3>$1</h3>')
    .replace(/^#{2}\s+(.+)$/gm, '<h2>$1</h2>')
    .replace(/^#\s+(.+)$/gm, '<h1>$1</h1>')
    .replace(/^-\s+(.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br/>')

  // 5. 还原 HTML 沙箱占位符
  text = text.replace(/\x00BLOCK(\d+)\x00/g, (_, i) => blocks[Number(i)])
  return text
}

// ──────────── 时间格式 ────────────
export function formatTime(ts: string): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// ──────────── 参数精简展示 ────────────
export function compactParams(input: Record<string, any>): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [k, v] of Object.entries(input)) {
    if (v === undefined || v === null || v === '') continue
    const str = typeof v === 'string' ? v : JSON.stringify(v)
    result[k] = str.length > 80 ? str.slice(0, 77) + '...' : str
  }
  return result
}
