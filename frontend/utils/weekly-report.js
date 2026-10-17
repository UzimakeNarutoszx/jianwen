// One data model and drawing vocabulary for on-screen charts and the full export.
export const REPORT_COLORS = ['#28645e', '#c09a54', '#597d9b', '#96647c', '#729255', '#aa704e']
export const minutes = seconds => (Number(seconds || 0) / 60).toFixed(1)
export const CHARTS = [
  { key: 'daily', title: '每天的阅读与追问', caption: '每天同一文章、章节各计一次；提问按次数统计。' },
  { key: 'topics', title: '阅读主题占比', caption: '按本周读过的不同文章统计，包含已有浏览记录。' },
  { key: 'trend', title: '阅读时间的积累', caption: '仅累计实际采集到的前台停留，不补算历史时长。' },
  { key: 'radar', title: '我的主题阅读分布', caption: '沿用网站主题顺序，数值为文章篇数，不代表能力评分。' }
]
export function reportModel(report) {
  const s = report.summary || {}
  const sections = [
    { title: `这一周，看过的文章 · ${s.articles || 0} 篇`, empty: '这一周还没有文章阅读记录。', items: (report.articles || []).map(i => ({ kind: 'article', source: i, title: i.title, meta: `${i.topic || '其他'} · ${(i.dates || []).join('、')} · ${i.seconds > 0 ? `已记录停留 ${minutes(i.seconds)} 分钟` : '未采集阅读时长'}` })) },
    ...['ask', 'ajin'].map(channel => ({ title: `${channel === 'ask' ? 'AI 问问' : '阿烬提问'} · ${s[channel] || 0} 次`, empty: '这一周还没有提问记录。', items: (report.questions || []).filter(q => q.channel === channel).map(q => ({ title: q.question, meta: String(q.created_at || '').slice(0, 16).replace('T', ' ') })) })),
    { title: `这一周，读过的名著 · ${s.books || 0} 本`, empty: '还没有累计停留满 30 秒的名著章节。', items: (report.classics || []).map(i => ({ kind: 'classic', source: i, title: `${i.book_title} · ${i.title}`, meta: `${(i.dates || []).join('、')} · 章内最近进度 ${i.scroll_progress || 0}% · 有效停留 ${minutes(i.seconds)} 分钟` })) }
  ]
  if ((report.legacy || []).length) sections.push({ title: '名著历史位置', intro: '仅保留最近阅读位置，无法确认有效停留，不计入上方名著阅读统计。', items: report.legacy.map(i => ({ kind: 'classic', source: i, title: `${i.book_title ? i.book_title + ' · ' : ''}${i.title}`, meta: `${String(i.date || '').slice(0, 16).replace('T', ' ')} · 章内进度 ${i.scroll_progress || 0}%` })) })
  return {
    title: `${report.user?.nickname || '我'}的见闻周报`, period: `${report.week_start} — ${report.week_end}`,
    badge: report.is_current ? '本周 · 持续更新中' : '个人历史周报', active: `这一周，你有 ${s.active_days || 0} 天留下阅读或提问记录。`,
    stats: [['文章阅读', `${s.articles || 0} 篇`], ['名著阅读', `${s.chapters || 0} 章 / ${s.books || 0} 本`], ['AI 问问', `${s.ask || 0} 次`], ['阿烬提问', `${s.ajin || 0} 次`], ['有效停留', `${minutes(s.reading_seconds)} 分钟`]], sections,
    notes: ['仅记录当前登录账号的个人活动。北京时间周一至周日。', '文章按已有浏览／已读记录计数，同一天同一篇只计一次，本周按文章去重；名著章节需累计有效停留满 30 秒。每日数量之和可能与周去重数量不同。', '隐藏、离开页面或连续 60 秒无操作时暂停计时，重叠时间只计一次。', `${report.tracking_since ? `当前账号最早留存的有效停留记录：${report.tracking_since}。` : '当前账号尚无有效停留记录。'}历史文章计入篇数，不补算未采集的阅读时长。周报随记录清除而更新。`]
  }
}
// Conservatively reserve one full em for non-ASCII glyphs, avoiding canvas text clipping.
export function wrapText(value, width, size) {
  const result = []
  String(value ?? '').split('\n').forEach(paragraph => {
    let line = '', used = 0
    for (const char of paragraph) {
      const advance = size
      if (line && used + advance > width) { result.push(line); line = ''; used = 0 }
      line += char; used += advance
    }
    result.push(line)
  })
  return result
}
const text = (ops, value, x, y, size = 12, color = '#152c31', align = 'left') => ops.push({ type: 'text', value: String(value), x, y, size, color, align })
const line = (ops, points, color = '#d8e1df', width = 1, fill = '') => ops.push({ type: 'path', points, color, width, fill })
export function chartScene(key, data, width, height = 260, dark = false) {
  const ops = [], ink = dark ? '#dce8e9' : '#152c31', muted = dark ? '#9baeb7' : '#657779'
  const days = data.days || [], topics = data.topics || [], left = 36, right = width - 16, top = 24, bottom = height - 55
  if (key === 'daily' || key === 'trend') {
    const fields = ['articles', 'chapters', 'ask', 'ajin']
    const maximum = Math.max(1, ...days.flatMap(d => key === 'daily' ? fields.map(f => Number(d[f]) || 0) : [Number(d.cumulative_seconds || 0) / 60]))
    for (let tick = 0; tick <= 3; tick++) {
      const y = bottom - tick * (bottom - top) / 3
      line(ops, [[left, y], [right, y]])
      text(ops, key === 'daily' ? String(Math.ceil(maximum / 3) * tick) : (maximum * tick / 3).toFixed(1), left - 5, y + 4, 10, muted, 'right')
    }
    const scaleMax = key === 'daily' ? Math.ceil(maximum / 3) * 3 : maximum
    const slot = (right - left) / Math.max(1, days.length)
    const trend = []
    days.forEach((d, index) => {
      const x = left + slot * (index + 0.5)
      text(ops, String(d.date).slice(5), x, bottom + 18, Math.min(10, slot / 3.4), muted, 'center')
      if (key === 'daily') fields.forEach((f, i) => {
        const w = Math.max(2, Math.min(12, slot / 5)), barH = (Number(d[f]) || 0) / scaleMax * (bottom - top)
        ops.push({ type: 'rect', x: x - w * 2 + i * w, y: bottom - barH, width: w - 1, height: barH, color: REPORT_COLORS[i] })
      })
      else trend.push([x, bottom - Number(d.cumulative_seconds || 0) / 60 / scaleMax * (bottom - top)])
    })
    if (key === 'trend') { line(ops, trend, REPORT_COLORS[0], 3); text(ops, '累计有效停留（分钟）', left, height - 10, 11, muted) }
    else ['文章', '名著章节', 'AI 问问', '阿烬'].forEach((name, i) => text(ops, name, 6 + i * width / 4, height - 10, 10, REPORT_COLORS[i]))
  } else if (key === 'topics') {
    const total = topics.reduce((sum, t) => sum + Number(t.count || 0), 0)
    const cx = width / 2, cy = 83, radius = 65
    let angle = -Math.PI / 2
    topics.forEach((t, i) => {
      if (!t.count) return
      const end = angle + Number(t.count) / total * Math.PI * 2
      ops.push({ type: 'slice', x: cx, y: cy, radius, start: angle, end, color: REPORT_COLORS[i % REPORT_COLORS.length] }); angle = end
    })
    if (!total) text(ops, '本周暂无文章阅读', cx, cy, 13, muted, 'center')
    topics.forEach((t, i) => text(ops, `${t.name} ${t.count} 篇`, 12 + (i % 2) * width / 2, 168 + Math.floor(i / 2) * 21, 11, REPORT_COLORS[i % REPORT_COLORS.length]))
  } else if (key === 'radar') {
    const axes = topics.slice(); while (axes.length < 3) axes.push({ name: '暂无主题', count: 0 })
    const max = Math.max(1, ...axes.map(t => Number(t.count) || 0)), cx = width / 2, cy = height / 2, r = Math.min(width / 2 - 56, height / 2 - 32)
    const point = (i, radius) => [cx + Math.cos(-Math.PI / 2 + i * Math.PI * 2 / axes.length) * radius, cy + Math.sin(-Math.PI / 2 + i * Math.PI * 2 / axes.length) * radius]
    for (let level = 1; level <= 3; level++) { const points = axes.map((_, i) => point(i, r * level / 3)); line(ops, [...points, points[0]]) }
    axes.forEach((axis, i) => {
      line(ops, [[cx, cy], point(i, r)])
      const [x, y] = point(i, r + 16)
      wrapText(axis.name, 54, 10).forEach((label, row) => text(ops, label, x, y + row * 12, 10, ink, 'center'))
    })
    const points = axes.map((axis, i) => point(i, r * axis.count / max)); line(ops, [...points, points[0]], REPORT_COLORS[0], 2, 'rgba(40,100,94,0.16)')
  }
  return ops
}
export function chartHeight(key, data) { return key === 'topics' ? Math.max(260, 180 + Math.ceil((data.topics || []).length / 2) * 21) : 260 }
export function exportScene(data, width = 720) {
  const ops = [], model = reportModel(data), margin = 38, contentWidth = width - margin * 2
  let y = 42
  function paragraph(value, size = 20, color = '#152c31') {
    for (const row of wrapText(value, contentWidth, size)) { text(ops, row, margin, y + size, size, color); y += size * 1.55 }
    y += 9
  }
  paragraph(model.title, 32); paragraph(model.period); paragraph(model.badge, 18, '#28645e'); paragraph(model.active)
  model.stats.forEach(([label, value]) => paragraph(`${label}   ${value}`, 22))
  CHARTS.forEach(chart => {
    y += 18; paragraph(chart.title, 25)
    const height = chartHeight(chart.key, data)
    const chartOps = chartScene(chart.key, data, contentWidth, height)
    chartOps.forEach(op => ops.push({ ...op, x: op.x == null ? op.x : op.x + margin, y: op.y == null ? op.y : op.y + y, points: op.points?.map(([x, py]) => [x + margin, py + y]) }))
    y += height + 12; paragraph(chart.caption, 17, '#657779')
  })
  paragraph('每日图表数据', 25)
  ;(data.days || []).forEach(d => paragraph(`${d.date}：文章 ${d.articles} · 章节 ${d.chapters} · 问问 ${d.ask} · 阿烬 ${d.ajin} · 停留 ${minutes(d.reading_seconds)} 分钟`, 18))
  paragraph((data.topics || []).map(t => `${t.name} ${t.count} 篇`).join(' · '), 18)
  model.sections.forEach(section => {
    y += 22; paragraph(section.title, 25)
    if (section.intro) paragraph(section.intro, 18, '#657779')
    if (!section.items.length) paragraph(section.empty, 18, '#657779')
    section.items.forEach(item => { paragraph(item.title, 21); paragraph(item.meta, 17, '#657779'); y += 10 })
  })
  y += 24; model.notes.forEach(note => paragraph(note, 17, '#657779'))
  const height = Math.ceil(y + 30)
  if (height > 30000 || width * height > 16000000) throw new Error('本周明细超出当前设备的单张长图容量，请使用内存更充足的设备重试。')
  return { width, height, ops }
}
export function paintScene(ctx, ops, width, height, background = '#fffef9') {
  ctx.setFillStyle(background); ctx.fillRect(0, 0, width, height)
  for (const op of ops) {
    if (op.type === 'text') { ctx.setFillStyle(op.color); ctx.setFontSize(op.size); ctx.setTextAlign(op.align); ctx.fillText(op.value, op.x, op.y) }
    else if (op.type === 'rect') { ctx.setFillStyle(op.color); ctx.fillRect(op.x, op.y, op.width, op.height) }
    else if (op.type === 'slice') { ctx.beginPath(); ctx.moveTo(op.x, op.y); ctx.arc(op.x, op.y, op.radius, op.start, op.end); ctx.closePath(); ctx.setFillStyle(op.color); ctx.fill() }
    else if (op.type === 'path' && op.points?.length) {
      ctx.beginPath(); ctx.moveTo(...op.points[0]); op.points.slice(1).forEach(p => ctx.lineTo(...p)); ctx.setLineWidth(op.width); ctx.setStrokeStyle(op.color)
      if (op.fill) { ctx.closePath(); ctx.setFillStyle(op.fill); ctx.fill() } ctx.stroke()
    }
  }
}
