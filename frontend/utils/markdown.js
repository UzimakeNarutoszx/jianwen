function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// Colours stay inherited so light/dark themes control contrast; only the
// translucent tint layers are baked in, because rich-text cannot read CSS vars.
function inlineMarkdown(value = '') {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code style="padding:2px 6px;border-radius:4px;background:rgba(31,95,122,.10);color:inherit;font-size:0.92em;">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong style="font-weight:900;color:inherit;">$1</strong>')
}

function flushList(html, listItems, ordered) {
  if (!listItems.length) return
  const tag = ordered ? 'ol' : 'ul'
  const padding = ordered ? '0 0 0 22px' : '0 0 0 20px'
  html.push(`<${tag} style="margin:8px 0 12px;padding:${padding};">`)
  listItems.forEach(item => {
    html.push(`<li style="margin:4px 0;line-height:1.7;">${inlineMarkdown(item)}</li>`)
  })
  html.push(`</${tag}>`)
  listItems.length = 0
}

export function markdownToHtml(markdown = '') {
  const lines = String(markdown || '').replace(/\r\n/g, '\n').split('\n')
  const html = []
  const listItems = []
  let listOrdered = false
  let inCodeBlock = false
  let codeLines = []

  function flushCodeBlock() {
    if (!codeLines.length) return
    html.push(
      `<pre style="box-sizing:border-box;margin:10px 0;padding:12px;border-radius:8px;background:rgba(31,95,122,.10);color:inherit;white-space:pre-wrap;line-height:1.55;font-size:0.87em;"><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`
    )
    codeLines = []
  }

  lines.forEach(rawLine => {
    const line = rawLine.trimEnd()
    const trimmed = line.trim()

    if (trimmed.startsWith('```')) {
      flushList(html, listItems, listOrdered)
      if (inCodeBlock) {
        flushCodeBlock()
        inCodeBlock = false
      } else {
        inCodeBlock = true
      }
      return
    }

    if (inCodeBlock) {
      codeLines.push(rawLine)
      return
    }

    if (!trimmed) {
      flushList(html, listItems, listOrdered)
      return
    }

    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/)
    if (headingMatch) {
      flushList(html, listItems, listOrdered)
      const level = headingMatch[1].length
      const size = level === 1 ? '1.25em' : level === 2 ? '1.125em' : '1em'
      html.push(
        `<div style="margin:${level === 1 ? 14 : 12}px 0 8px;color:inherit;font-weight:900;font-size:${size};line-height:1.35;">${inlineMarkdown(headingMatch[2])}</div>`
      )
      return
    }

    const quoteMatch = trimmed.match(/^>\s?(.+)$/)
    if (quoteMatch) {
      flushList(html, listItems, listOrdered)
      html.push(
        `<blockquote style="box-sizing:border-box;margin:8px 0;padding:8px 12px;border-left:3px solid rgba(31,95,122,.45);background:rgba(31,95,122,.10);color:inherit;line-height:1.65;">${inlineMarkdown(quoteMatch[1])}</blockquote>`
      )
      return
    }

    const unorderedMatch = trimmed.match(/^[-*]\s+(.+)$/)
    if (unorderedMatch) {
      if (listItems.length && listOrdered) flushList(html, listItems, listOrdered)
      listOrdered = false
      listItems.push(unorderedMatch[1])
      return
    }

    const orderedMatch = trimmed.match(/^\d+[.)]\s+(.+)$/)
    if (orderedMatch) {
      if (listItems.length && !listOrdered) flushList(html, listItems, listOrdered)
      listOrdered = true
      listItems.push(orderedMatch[1])
      return
    }

    flushList(html, listItems, listOrdered)
    html.push(`<p style="margin:0 0 10px;line-height:1.75;">${inlineMarkdown(trimmed)}</p>`)
  })

  flushList(html, listItems, listOrdered)
  if (inCodeBlock) flushCodeBlock()

  return html.join('')
}
