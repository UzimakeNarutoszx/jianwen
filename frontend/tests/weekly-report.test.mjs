import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
const source = await readFile(new URL('../utils/weekly-report.js', import.meta.url), 'utf8')
const { reportModel, CHARTS, chartScene, exportScene, wrapText } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
const report = {
  user: { nickname: '测试读者' }, week_start: '2026-10-12', week_end: '2026-10-18', is_current: true,
  summary: { articles: 1, chapters: 1, books: 1, ask: 2, ajin: 1, reading_seconds: 150, active_days: 2 },
  days: Array.from({ length: 7 }, (_, i) => ({ date: `2026-10-${12 + i}`, articles: i === 0 ? 1 : 0, chapters: i === 1 ? 1 : 0, ask: i === 0 ? 2 : 0, ajin: i === 0 ? 1 : 0, reading_seconds: i === 0 ? 150 : 0, cumulative_seconds: 150 })),
  topics: [{ name: '科技', count: 1 }, { name: '社会', count: 0 }],
  articles: [{ content_id: 'one', title: '本周文章标题', topic: '科技', dates: ['2026-10-12'], seconds: 120 }],
  classics: [{ book_id: 'b', content_id: '1', title: '第一章', book_title: '测试名著', dates: ['2026-10-13'], scroll_progress: 40, seconds: 30 }],
  questions: [{ channel: 'ask', question: '怎样理解这项变化？', created_at: '2026-10-12T10:00:00+08:00' }, { channel: 'ajin', question: '继续追问', created_at: '2026-10-12T11:00:00+08:00' }],
  legacy: [{ book_id: 'b', content_id: '2', title: '旧的阅读位置', date: '2026-10-12T09:00:00+08:00', scroll_progress: 20 }]
}
test('export includes all sections, captions, daily data, questions and legacy', () => {
  const scene = exportScene(report), text = scene.ops.filter(op => op.type === 'text').map(op => op.value).join('')
  for (const value of ['测试读者', '本周文章标题', '怎样理解这项变化？', '继续追问', '测试名著', '旧的阅读位置', '2026-10-18', '历史文章计入篇数']) assert.ok(text.includes(value), value)
  for (const chart of CHARTS) { assert.ok(text.includes(chart.title)); assert.ok(text.includes(chart.caption)) }
  assert.ok(scene.ops.filter(op => op.type === 'text').every(op => op.y < scene.height))
  assert.equal(reportModel(report).sections.length, 5)
})
test('empty charts have finite coordinates and readable empty text', () => {
  for (const chart of CHARTS) for (const op of chartScene(chart.key, { days: [], topics: [] }, 280)) {
    for (const key of ['x', 'y', 'radius', 'width', 'height']) if (op[key] != null) assert.ok(Number.isFinite(op[key]))
    for (const point of op.points || []) assert.ok(point.every(Number.isFinite))
  }
  assert.ok(chartScene('topics', { topics: [] }, 280).some(op => op.value === '本周暂无文章阅读'))
})
test('long text wraps without losing characters; oversized report is rejected', () => {
  const value = '甲乙丙丁'.repeat(40)
  assert.equal(wrapText(value, 100, 20).join(''), value)
  const large = { ...report, questions: Array.from({ length: 3000 }, () => ({ channel: 'ask', question: value })) }
  assert.throws(() => exportScene(large), /单张长图容量/)
})
