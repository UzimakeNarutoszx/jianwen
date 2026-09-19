import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const cli = fileURLToPath(new URL('../node_modules/@dcloudio/vite-plugin-uni/bin/uni.js', import.meta.url))
const child = spawn(process.execPath, [cli, ...process.argv.slice(2)], {
  cwd: process.cwd(),
  env: { ...process.env, UNI_INPUT_DIR: process.cwd() },
  stdio: 'inherit'
})

child.on('exit', code => process.exit(code ?? 1))
