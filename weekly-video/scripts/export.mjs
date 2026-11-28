import {readFile, mkdir, readdir} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {resolve, basename} from 'node:path'
import {spawnSync} from 'node:child_process'
import os from 'node:os'

const root = fileURLToPath(new URL('..', import.meta.url))
const MODES = ['video', 'cover', 'frames']
const DEFAULT_FRAMES = [0, 30, 90]
const DEFAULT_JPEG_QUALITY = 90

const usage = `Usage: node scripts/export.mjs [video|cover|frames] [options]

  video (default)  render output/weekly-video/<id>/episode.mp4
  cover            render public/episodes/<id>/cover.jpg
  frames           render selected frames as PNG into output/weekly-video/<id>/smoke/

Options:
  --frames=0,30,90       frames for frames mode (default 0,30,90; PNG only)
  --concurrency=<n>      video concurrency (default max(2, cpus - 1))
  --image-format=<fmt>   video image format, jpeg or png (default jpeg)
  --jpeg-quality=<n>     video JPEG quality 1-100 (default ${DEFAULT_JPEG_QUALITY})
  --help                 show this help`

const fail = message => {
  throw new Error(message)
}

const parseInteger = (flag, value, {min, max}) => {
  if (!/^\d+$/.test(value ?? '')) return fail(`${flag} expects an integer, got: ${value ?? '(missing)'}`)
  const parsed = Number(value)
  if (parsed < min || parsed > max) fail(`${flag} must be between ${min} and ${max}, got: ${parsed}`)
  return parsed
}

const parseFrames = value => {
  const frames = (value ?? '').split(',').map(part => {
    if (!/^\d+$/.test(part)) fail(`--frames expects comma-separated non-negative integers, got: ${value}`)
    return Number(part)
  })
  if (frames.length === 0) fail('--frames expects at least one frame number')
  return [...new Set(frames)]
}

const parseArgs = argv => {
  const provided = new Set()
  const options = {mode: 'video'}
  for (const arg of argv) {
    if (arg === '--help' || arg === '-h') return {help: true}
    if (arg.startsWith('--')) {
      const [flag, ...rest] = arg.slice(2).split('=')
      const value = rest.join('=')
      provided.add(flag)
      switch (flag) {
        case 'frames':
          options.frames = parseFrames(value)
          break
        case 'concurrency':
          options.concurrency = parseInteger('--concurrency', value, {min: 1, max: 64})
          break
        case 'image-format':
          if (value !== 'jpeg' && value !== 'png') fail(`--image-format must be jpeg or png, got: ${value}`)
          options.imageFormat = value
          break
        case 'jpeg-quality':
          options.jpegQuality = parseInteger('--jpeg-quality', value, {min: 1, max: 100})
          break
        default:
          fail(`Unknown option: --${flag}`)
      }
      continue
    }
    if (!MODES.includes(arg)) fail(`Unknown mode: ${arg} (expected one of ${MODES.join(', ')})`)
    if (options.modeProvided) fail(`Only one mode can be selected, got: ${options.mode} and ${arg}`)
    options.mode = arg
    options.modeProvided = true
  }
  if (options.mode === 'frames') {
    if (options.imageFormat && options.imageFormat !== 'png') fail('frames mode always renders PNG; use --image-format=png or omit it')
    if (provided.has('concurrency') || provided.has('jpeg-quality')) fail('--concurrency/--jpeg-quality are video-mode options')
  }
  if (options.mode !== 'frames' && provided.has('frames')) fail('--frames is only valid in frames mode')
  options.frames ??= DEFAULT_FRAMES
  options.concurrency ??= Math.max(2, os.cpus().length - 1)
  options.imageFormat ??= options.mode === 'frames' ? 'png' : 'jpeg'
  options.jpegQuality ??= DEFAULT_JPEG_QUALITY
  return options
}

const buildCommand = (options, id) => {
  if (options.mode === 'cover') {
    const target = resolve(root, 'public/episodes', id, 'cover.jpg')
    return {target, directory: false, args: ['still', 'src/index.ts', 'WeeklyCover', target]}
  }
  if (options.mode === 'frames') {
    const target = resolve(root, '../output/weekly-video', id, 'smoke')
    return {
      target,
      directory: true,
      args: [
        'render',
        'src/index.ts',
        'WeeklyVideo',
        target,
        `--frames=${options.frames.join(',')}`,
        '--image-format=png'
      ]
    }
  }
  const target = resolve(root, '../output/weekly-video', id, 'episode.mp4')
  return {
    target,
    directory: false,
    args: [
      'render',
      'src/index.ts',
      'WeeklyVideo',
      target,
      '--codec=h264',
      '--audio-codec=aac',
      `--concurrency=${options.concurrency}`,
      `--image-format=${options.imageFormat}`,
      `--jpeg-quality=${options.jpegQuality}`
    ]
  }
}

const main = async () => {
  const options = parseArgs(process.argv.slice(2))
  if (options.help) {
    console.log(usage)
    return
  }
  const {id} = JSON.parse(await readFile(resolve(root, 'current.json'), 'utf8'))
  if (!/^\d{4}-W\d{2}$/.test(id)) fail(`Invalid active episode in current.json: ${id}`)
  const {target, directory, args} = buildCommand(options, id)
  await mkdir(directory ? target : resolve(target, '..'), {recursive: true})
  const startedAt = Date.now()
  const started = new Date(startedAt).toISOString()
  console.log(`[export] start mode=${options.mode} episode=${id} time=${started}`)
  console.log(`[export] output=${target}`)
  const result = spawnSync(resolve(root, 'node_modules/.bin/remotion'), args, {cwd: root, stdio: 'inherit'})
  const elapsedSeconds = ((Date.now() - startedAt) / 1000).toFixed(1)
  if (result.error) {
    console.error(`[export] failed after ${elapsedSeconds}s: ${result.error.message}`)
    throw result.error
  }
  const status = result.status ?? 1
  console.log(`[export] end mode=${options.mode} episode=${id} status=${status} elapsed=${elapsedSeconds}s`)
  if (status === 0 && directory) {
    const written = (await readdir(target)).filter(name => name.endsWith('.png')).sort()
    console.log(`[export] frames written (${written.length}): ${written.map(name => basename(name)).join(', ')}`)
    if (written.length !== options.frames.length) {
      console.error(`[export] expected ${options.frames.length} PNG frames, found ${written.length}`)
      process.exitCode = 1
      return
    }
  }
  process.exitCode = status
}

main().catch(error => {
  console.error(`[export] ${error.message}`)
  process.exitCode = 1
})
