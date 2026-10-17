import {readFile, mkdir} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {resolve} from 'node:path'
import {spawnSync} from 'node:child_process'

const root = fileURLToPath(new URL('..', import.meta.url))
const {id} = JSON.parse(await readFile(resolve(root, 'current.json'), 'utf8'))
if (!/^\d{4}-W\d{2}$/.test(id)) throw new Error('Invalid active episode')
const cover = process.argv[2] === 'cover'
const target = cover ? resolve(root, 'public/episodes', id, 'cover.jpg') : resolve(root, '../output/weekly-video', id, 'episode.mp4')
await mkdir(resolve(target, '..'), {recursive:true})
const args = cover ? ['still', 'src/index.ts', 'WeeklyCover', target] : ['render', 'src/index.ts', 'WeeklyVideo', target, '--codec=h264', '--audio-codec=aac']
const result = spawnSync(resolve(root, 'node_modules/.bin/remotion'), args, {cwd:root, stdio:'inherit'})
if (result.error) throw result.error
process.exit(result.status ?? 1)
