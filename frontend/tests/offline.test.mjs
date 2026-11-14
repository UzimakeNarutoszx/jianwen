import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// uni-app 源码按 ESM 打包，但 frontend 没有 package type:module，因此用 data URL 载入。
const source = readFileSync(new URL('../utils/offline.js', import.meta.url))
const offline = await import(`data:text/javascript;base64,${source.toString('base64')}`)

const {
  CHECKLIST_FILE, CHECKLIST_TTL_MS, META_FILE, OFFLINE_ROOT, OFFLINE_VERSION,
  chooseAudioUrl, createOfflineCache, dateFromAudioUrl, dateKey, estimateAudioBytes,
  formatBytes, isChecklistFresh, isDateKey, isMetaFresh, normalizeChecklist, normalizeMeta,
  offlineDateDir, offlineFilePath, resolveLocalPlayablePath, resolveTodayContent, selectCleanupDates, selectFallbackDate,
  shiftDateKey, shouldDownload, summarizeUsage, voiceAudioFileName
} = offline

const NOW = Date.parse('2026-11-14T12:00:00+08:00')

function sampleArticles(count = 5) {
  return Array.from({ length: count }, (_, index) => ({
    id: `article-${index + 1}`,
    articleId: `article-${index + 1}`,
    topic: '科技',
    title: `第 ${index + 1} 篇`,
    desc: '摘要',
    image: `https://api.example.com/uploads/${index + 1}.jpg`,
    readTime: '3 分钟',
    sources: '见闻',
    viewed: false
  }))
}

// 内存平台：行为和 plus.io 平台层一一对应，用来单测目录/元数据/清理/下载，不碰真实文件系统。
function createMemoryPlatform() {
  const files = new Map()
  const dirs = new Set()
  const normalize = path => String(path).replace(/\/+/g, '/').replace(/\/$/, '')
  const parent = path => normalize(path).slice(0, normalize(path).lastIndexOf('/')) || '/'
  const base = path => normalize(path).slice(normalize(path).lastIndexOf('/') + 1)
  return {
    files,
    dirs,
    supported: () => true,
    async ensureDir(path) { dirs.add(normalize(path)) },
    async writeText(path, text) {
      files.set(normalize(path), String(text))
      dirs.add(parent(path))
    },
    async readText(path) {
      const key = normalize(path)
      return files.has(key) ? files.get(key) : null
    },
    async exists(path) { return files.has(normalize(path)) },
    async removeDir(path) {
      const target = normalize(path)
      const prefix = `${target}/`
      for (const key of [...files.keys()]) if (key === target || key.startsWith(prefix)) files.delete(key)
      for (const dir of [...dirs]) if (dir === target || dir.startsWith(prefix)) dirs.delete(dir)
    },
    async listDir(path) {
      const target = normalize(path)
      const entries = []
      for (const key of files.keys()) {
        if (parent(key) === target) entries.push({ name: base(key), isDirectory: false, size: Buffer.byteLength(files.get(key) || '') })
      }
      for (const dir of dirs) {
        if (dir !== target && parent(dir) === target) entries.push({ name: base(dir), isDirectory: true, size: 0 })
      }
      return entries
    },
    async download(url, path) {
      const content = `audio:${url}`
      files.set(normalize(path), content)
      dirs.add(parent(path))
      return { path, size: Buffer.byteLength(content) }
    },
    async networkType() { return 'wifi' }
  }
}

test('日期目录：_doc/jianwen/offline/<date>/，非法日期和路径分隔符一律拒绝', () => {
  assert.equal(OFFLINE_ROOT, '_doc/jianwen/offline')
  assert.equal(offlineDateDir('2026-11-14'), '_doc/jianwen/offline/2026-11-14')
  assert.equal(offlineDateDir('2026-11-14', '_doc/custom/'), '_doc/custom/2026-11-14')
  assert.equal(offlineFilePath('2026-11-14', META_FILE), '_doc/jianwen/offline/2026-11-14/meta.json')
  assert.equal(offlineFilePath('2026-11-14', CHECKLIST_FILE), '_doc/jianwen/offline/2026-11-14/today.json')

  // 日期必须是真实日历日，且不能拼 ../ 越出缓存目录。
  assert.equal(isDateKey('2026-11-14'), true)
  assert.equal(isDateKey('2026-02-30'), false)
  assert.equal(isDateKey('2026-13-01'), false)
  assert.equal(isDateKey(''), false)
  assert.throws(() => offlineDateDir('2026-13-01'), /无效的离线缓存日期/)
  assert.throws(() => offlineDateDir('../escape'), /无效的离线缓存日期/)
  assert.throws(() => offlineFilePath('2026-11-14', '../meta.json'), /无效的离线缓存文件名/)
  assert.throws(() => offlineFilePath('2026-11-14', ''), /无效的离线缓存文件名/)

  assert.equal(dateKey(new Date(2026, 10, 14, 9, 30)), '2026-11-14')
  assert.equal(dateKey('2026-11-14'), '2026-11-14')
  assert.equal(dateKey('not-a-date'), dateKey())
  assert.equal(shiftDateKey('2026-11-14', -1), '2026-11-13')
  assert.equal(shiftDateKey('2026-01-01', -1), '2025-12-31')
  assert.equal(shiftDateKey('2026-11-14', 0), '2026-11-14')
  assert.equal(dateFromAudioUrl('/uploads/tts/2026-11-12/continuous-jianwen.mp3?v=1'), '2026-11-12')
  assert.equal(dateFromAudioUrl('_doc/jianwen/offline/2026-11-12/continuous-jianwen.mp3'), '2026-11-12')
  assert.equal(dateFromAudioUrl('https://api.example.com/audio.mp3'), '')

  assert.equal(voiceAudioFileName('jianwen'), 'continuous-jianwen.mp3')
  assert.equal(voiceAudioFileName(''), 'continuous-default.mp3')
  assert.equal(voiceAudioFileName('../../evil'), 'continuous-evil.mp3')
})

test('元数据读写与过期：日期对得上且 TTL 内才算新鲜，脏数据收敛为 null', () => {
  const meta = {
    version: OFFLINE_VERSION,
    date: '2026-11-14',
    updatedAt: NOW - 1000,
    checklist: { file: CHECKLIST_FILE, savedAt: NOW - 1000, count: 5 },
    audio: { jianwen: { file: 'continuous-jianwen.mp3', size: '1024', savedAt: NOW - 500 } }
  }
  assert.equal(isMetaFresh(meta, { now: NOW, date: '2026-11-14' }), true)
  assert.equal(isChecklistFresh(meta, { now: NOW, date: '2026-11-14' }), true)

  // 元数据过期、日期不符、时钟回拨都判旧。
  assert.equal(isMetaFresh(meta, { now: NOW + CHECKLIST_TTL_MS + 1, date: '2026-11-14' }), false)
  assert.equal(isMetaFresh(meta, { now: NOW, ttlMs: 500, date: '2026-11-14' }), false)
  assert.equal(isMetaFresh(meta, { now: NOW, date: '2026-11-13' }), false)
  assert.equal(isMetaFresh(meta, { now: meta.updatedAt - 1, date: '2026-11-14' }), false)
  assert.equal(isMetaFresh(null), false)
  assert.equal(isMetaFresh({ date: '2026-11-14' }), false, '缺 updatedAt 不算合法元数据')

  // 清单计数为 0、或清单缺失时不算可用缓存。
  assert.equal(isChecklistFresh({ ...meta, checklist: { ...meta.checklist, count: 0 } }, { now: NOW }), false)
  assert.equal(isChecklistFresh({ ...meta, checklist: null }, { now: NOW }), false)

  const normalized = normalizeMeta({
    date: '2026-11-14',
    updatedAt: NOW,
    audio: { jianwen: { file: 'a.mp3', size: '12', savedAt: '5' }, bad: null, dylan: {} }
  })
  assert.deepEqual(Object.keys(normalized.audio), ['jianwen'])
  assert.equal(normalized.audio.jianwen.size, 12)
  assert.equal(normalized.checklist, null)
  assert.equal(normalizeMeta({ date: 'bad', updatedAt: NOW }), null)
  assert.equal(normalizeMeta('oops'), null)
})

test('占用统计与按日期清理：keepDates 保留、超过保留天数删除', async () => {
  const platform = createMemoryPlatform()
  const cache = createOfflineCache({ platform, now: () => NOW })
  const dates = ['2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13', '2026-11-14']
  for (const date of dates) {
    await platform.ensureDir(offlineDateDir(date))
    await platform.writeText(offlineFilePath(date, META_FILE), JSON.stringify({
      version: OFFLINE_VERSION,
      date,
      updatedAt: NOW,
      checklist: { file: CHECKLIST_FILE, savedAt: NOW, count: 1 },
      audio: {}
    }))
  }
  assert.deepEqual(await cache.listDates(), dates)

  const usage = await cache.usage()
  assert.equal(usage.status, 'ok')
  assert.equal(Object.keys(usage.byDate).length, dates.length)
  assert.ok(usage.totalBytes > 0)
  assert.ok(usage.totalFiles >= dates.length)

  const plan = selectCleanupDates(dates.concat(['2026-10-01', 'bad']), {
    today: '2026-11-14',
    maxAgeDays: 2,
    keepDates: ['2026-11-09']
  })
  assert.deepEqual(plan.sort(), ['2026-10-01', '2026-11-10', '2026-11-11'])

  const cleanup = await cache.cleanup({ today: '2026-11-14', maxAgeDays: 2, keepDates: ['2026-11-09'] })
  assert.equal(cleanup.status, 'ok')
  assert.deepEqual(cleanup.removedDates.sort(), ['2026-11-10', '2026-11-11'])
  assert.ok(cleanup.freedBytes > 0)
  assert.equal(cleanup.freedLabel, formatBytes(cleanup.freedBytes))
  assert.deepEqual(await cache.listDates(), ['2026-11-09', '2026-11-12', '2026-11-13', '2026-11-14'])

  // 单日清理 + 全部清理。
  const single = await cache.removeDate('2026-11-14')
  assert.equal(single.status, 'removed')
  assert.equal((await cache.listDates()).includes('2026-11-14'), false)
  const all = await cache.cleanup({ today: '2026-11-14', includeAll: true })
  assert.deepEqual(all.removedDates.sort(), ['2026-11-09', '2026-11-12', '2026-11-13'])
  assert.deepEqual(await cache.listDates(), [])
  assert.equal((await cache.usage()).totalBytes, 0)
})

test('离线回退选择：在线优先，失败读缓存，过期缓存默认不读', () => {
  const articles = sampleArticles(6)
  const freshCache = { date: '2026-11-14', savedAt: NOW - 60 * 1000, articles, banners: [{ id: 'banner-1' }] }
  const remote = { articles: sampleArticles(3), banners: [] }

  const online = resolveTodayContent({ remote, cached: freshCache, now: NOW, date: '2026-11-14' })
  assert.equal(online.source, 'remote')
  assert.equal(online.offline, false)
  assert.equal(online.articles.length, 3)

  const cached = resolveTodayContent({ remote: null, cached: freshCache, now: NOW, date: '2026-11-14' })
  assert.equal(cached.source, 'cache')
  assert.equal(cached.offline, true)
  assert.equal(cached.stale, false)
  assert.equal(cached.articles.length, 5, '缓存最多渲染 5 篇')
  assert.equal(cached.date, '2026-11-14')

  // 请求失败（空数组）同样走缓存。
  assert.equal(resolveTodayContent({ remote: { articles: [] }, cached: freshCache, now: NOW, date: '2026-11-14' }).source, 'cache')

  const expired = { ...freshCache, savedAt: NOW - CHECKLIST_TTL_MS - 1 }
  assert.equal(resolveTodayContent({ remote: null, cached: expired, now: NOW, date: '2026-11-14' }).source, 'none')
  const stale = resolveTodayContent({ remote: null, cached: expired, now: NOW, date: '2026-11-14', allowStale: true })
  assert.equal(stale.source, 'cache')
  assert.equal(stale.stale, true)
  assert.equal(stale.articles.length, 5)

  // 日期对不上不是“今天”的离线内容。
  assert.equal(resolveTodayContent({ remote: null, cached: { ...freshCache, date: '2026-11-13' }, now: NOW, date: '2026-11-14' }).source, 'none')
  // 脏缓存不渲染。
  assert.equal(resolveTodayContent({ remote: null, cached: { articles: [{ title: '没有 id' }] }, now: NOW }).source, 'none')
  assert.equal(normalizeChecklist({ articles: [] }), null)
  assert.deepEqual(normalizeChecklist({ articles: sampleArticles(6) }).articles.length, 5)

  // 跨零点：今天没有缓存时退回之前最近一天，7 天以外不要。
  assert.equal(selectFallbackDate(['2026-11-13', '2026-11-14', '2026-11-15', 'bad'], '2026-11-14'), '2026-11-14')
  assert.equal(selectFallbackDate(['2026-11-12', '2026-11-13', '2026-11-15'], '2026-11-14'), '2026-11-13')
  assert.equal(selectFallbackDate([], '2026-11-14'), '')
  assert.equal(selectFallbackDate(['2026-10-01'], '2026-11-14'), '')
})

test('缓存写入/读取 round-trip：清单 + 音轨元数据，损坏文件与不支持平台都不抛错', async () => {
  const platform = createMemoryPlatform()
  const cache = createOfflineCache({ platform, now: () => NOW })
  assert.equal(cache.supported(), true)

  const saved = await cache.saveChecklist({ date: '2026-11-14', articles: sampleArticles(6), banners: [{ id: 'banner-1' }] })
  assert.equal(saved.status, 'saved')
  assert.equal(saved.count, 5)
  assert.equal(await platform.exists(offlineFilePath('2026-11-14', CHECKLIST_FILE)), true)
  assert.equal(await platform.exists(offlineFilePath('2026-11-14', META_FILE)), true)

  const read = await cache.readChecklist('2026-11-14')
  assert.equal(read.date, '2026-11-14')
  assert.equal(read.checklist.articles.length, 5)
  assert.equal(read.checklist.articles[0].title, '第 1 篇')
  assert.equal(read.fresh, true)
  assert.equal(read.meta.checklist.count, 5)

  const latest = await cache.readLatestChecklist({ today: '2026-11-14', maxAgeDays: 7 })
  assert.equal(latest.date, '2026-11-14')
  assert.equal(latest.checklist.articles.length, 5)

  // 今天没有缓存（比如跨零点/首次断网）时退回之前最近一天。
  const olderPlatform = createMemoryPlatform()
  const olderCache = createOfflineCache({ platform: olderPlatform, now: () => NOW - 24 * 60 * 60 * 1000 })
  await olderCache.saveChecklist({ date: '2026-11-13', articles: sampleArticles(2) })
  const fallback = await olderCache.readLatestChecklist({ today: '2026-11-14', maxAgeDays: 7 })
  assert.equal(fallback.date, '2026-11-13')
  assert.equal(fallback.checklist.articles.length, 2)

  // 连续音轨：下载后写入元数据，下次直接从本地路径取。
  const cachedAudio = await cache.cacheAudio({ date: '2026-11-14', voice: 'jianwen', url: 'https://api.example.com/c.mp3' })
  assert.equal(cachedAudio.status, 'cached')
  assert.ok(cachedAudio.path.endsWith('/2026-11-14/continuous-jianwen.mp3'))
  assert.ok(cachedAudio.size > 0)
  assert.equal(await cache.cachedAudioPath('2026-11-14', 'jianwen'), cachedAudio.path)
  assert.equal(await cache.cachedAudioPath('2026-11-14', 'dylan'), '')

  const again = await cache.cacheAudio({ date: '2026-11-14', voice: 'jianwen', url: 'https://api.example.com/c.mp3' })
  assert.equal(again.status, 'exists')
  const meta = await cache.readMeta('2026-11-14')
  assert.equal(meta.audio.jianwen.file, 'continuous-jianwen.mp3')
  assert.equal(meta.checklist.count, 5, '缓存音轨不会覆盖清单元数据')

  // 损坏 JSON 读成 null，不抛到页面。
  await platform.writeText(offlineFilePath('2026-11-13', CHECKLIST_FILE), '{oops')
  assert.equal(await cache.readChecklist('2026-11-13'), null)
  assert.equal(await cache.readMeta('2026-11-13'), null)
  assert.equal(await cache.cachedAudioPath('2026-11-14', ''), '')

  // H5/小程序：平台不支持时所有方法安全降级。
  const unsupported = createOfflineCache({ platform: { supported: () => false }, now: () => NOW })
  assert.deepEqual(await unsupported.saveChecklist({ date: '2026-11-14', articles: sampleArticles(1) }), { status: 'unsupported' })
  assert.equal(await unsupported.readChecklist('2026-11-14'), null)
  assert.equal(await unsupported.readLatestChecklist({ today: '2026-11-14' }), null)
  assert.equal(await unsupported.cachedAudioPath('2026-11-14', 'jianwen'), '')
  assert.deepEqual(await unsupported.listDates(), [])
  assert.equal((await unsupported.cacheAudio({ date: '2026-11-14', voice: 'jianwen', url: 'u' })).status, 'unsupported')
  assert.equal((await unsupported.usage()).totalBytes, 0)
  assert.equal((await unsupported.cleanup({ today: '2026-11-14' })).status, 'unsupported')
  assert.equal((await unsupported.removeDate('2026-11-14')).status, 'skipped')
  assert.equal(await unsupported.networkType(), '')
})

test('音轨本地优先、网络策略与体积估算', () => {
  assert.deepEqual(chooseAudioUrl('https://api.example.com/c.mp3', ''), { url: 'https://api.example.com/c.mp3', local: false })
  assert.deepEqual(chooseAudioUrl('https://api.example.com/c.mp3', '_doc/jianwen/offline/2026-11-14/continuous-jianwen.mp3'), {
    url: '_doc/jianwen/offline/2026-11-14/continuous-jianwen.mp3',
    local: true
  })
  assert.deepEqual(chooseAudioUrl('', '_doc/a.mp3'), { url: '_doc/a.mp3', local: true })
  assert.deepEqual(chooseAudioUrl('', ''), { url: '', local: false })
  // Node/无 plus 环境里原样返回；App 端由 plus.io 转成原生绝对路径。
  assert.equal(resolveLocalPlayablePath('_doc/jianwen/offline/2026-11-14/continuous-jianwen.mp3'), '_doc/jianwen/offline/2026-11-14/continuous-jianwen.mp3')
  assert.equal(resolveLocalPlayablePath(''), '')
  assert.equal(resolveLocalPlayablePath(null), '')

  // 自动缓存只在 Wi-Fi；用户手动点了按钮（manual）才允许移动网络。
  assert.equal(shouldDownload({ networkType: 'wifi' }), true)
  assert.equal(shouldDownload({ networkType: '4g' }), false)
  assert.equal(shouldDownload({ networkType: '4g', manual: true }), true)
  assert.equal(shouldDownload({ networkType: 'none' }), false)
  assert.equal(shouldDownload({ networkType: '4g', wifiOnly: false }), true)

  assert.equal(estimateAudioBytes(0), 0)
  assert.equal(estimateAudioBytes(100), 819200)
  assert.equal(estimateAudioBytes(-1), 0)
  assert.equal(formatBytes(0), '0 B')
  assert.equal(formatBytes(512), '512 B')
  assert.equal(formatBytes(1024), '1 KB')
  assert.equal(formatBytes(1536), '1.5 KB')
  assert.equal(formatBytes(6 * 1024 * 1024), '6 MB')

  const summary = summarizeUsage([
    { date: '2026-11-14', bytes: 1024, files: 2 },
    { date: '2026-11-13', bytes: 2048, files: 3 },
    { date: 'bad', bytes: 999, files: 9 }
  ])
  assert.equal(summary.totalBytes, 3072)
  assert.equal(summary.totalFiles, 5)
  assert.equal(summary.label, '3 KB')
  assert.deepEqual(Object.keys(summary.byDate), ['2026-11-14', '2026-11-13'])
})
