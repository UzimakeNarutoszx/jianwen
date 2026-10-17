import { readFile, writeFile, copyFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const id = process.argv[2]
if (!/^\d{4}-W\d{2}$/.test(id || '')) throw new Error('Usage: node scripts/select-episode.mjs YYYY-Www')
const timeline = JSON.parse(await readFile(resolve(root, 'episodes', id, 'timeline.json'), 'utf8'))
if (timeline.id !== id || timeline.durationSeconds < 180 || timeline.durationSeconds > 300) throw new Error('Prepare and validate this episode first')
await mkdir(resolve(root, 'public/episodes', id), { recursive: true })
await copyFile(resolve(root, 'episodes', id, 'timeline.json'), resolve(root, 'public/episodes', id, 'timeline.json'))
await writeFile(resolve(root, 'src/current-episode.ts'), `// Change with: node scripts/select-episode.mjs YYYY-Www\nexport {default} from '../episodes/${id}/timeline.json';\n`)
await writeFile(resolve(root, 'current.json'), JSON.stringify({id}) + '\n')
console.log(`Studio selected ${id}. Past episode snapshots are unchanged.`)
