import assert from 'node:assert/strict'
import { readFile, readdir, access } from 'node:fs/promises'
import { resolve, dirname, relative } from 'node:path'
import vm from 'node:vm'

const root = resolve('webpage')
async function pages(directory) {
  const files = await readdir(directory, { withFileTypes: true })
  return (await Promise.all(files.map(file => file.isDirectory() ? pages(resolve(directory, file.name)) : file.name.endsWith('.html') ? [resolve(directory, file.name)] : []))).flat()
}
const files = await pages(root)
const source = (await readFile(resolve(root, 'js/site.js'), 'utf8')).split("document.querySelectorAll('img[data-fallback]')")[0]
const expected = ['index.html', 'about.html', 'links.html', 'jianwen/index.html', 'jianwen/discover.html', 'jianwen/search.html', 'jianwen/classics.html', 'jianwen/ask.html', 'avatar.html', 'avatar-features.html', 'avatar-growth.html', 'avatar.html#contact']
for (const file of files) {
  const page = relative(root, file).replaceAll('\\', '/')
  const html = await readFile(file, 'utf8')
  assert.equal((html.match(/data-site-header/g) || []).length, 1, `${page}: one common header`)
  assert.ok(html.includes('data-site-footer'), `${page}: footer`)
  assert.doesNotMatch(html, /<style\b|intro\.html|avatar-contact\.html/, `${page}: retired styles/pages`)
  const css = [...html.matchAll(/<link[^>]*href="([^"]+\.css[^\"]*)"/g)].map(match => match[1])
  assert.ok(css.at(-1).includes('editorial.css'), `${page}: final common theme`)
  for (const match of html.matchAll(/(?:href|src)="([^"${}]+)"/g)) {
    const value = match[1]
    if (/^(https?:|data:|#|mailto:|tel:)/.test(value)) continue
    const path = value.split(/[?#]/)[0]
    if (path) await access(resolve(dirname(file), decodeURIComponent(path)))
  }
  for (const loggedIn of [false, true]) {
    const header = {}, footer = {}, main = { id: 'content' }
    const context = {
      location: { protocol: 'http:', pathname: `/${page}` },
      localStorage: { getItem: key => key === 'jianwen_auth_token' && loggedIn ? 'valid-test-token' : null },
      document: { querySelector: selector => selector === '[data-site-header]' ? header : selector === '[data-site-footer]' ? footer : selector === 'main' ? main : {} }
    }
    vm.runInNewContext(`${source}\nrenderShell()`, context)
    const hrefs = [...header.innerHTML.matchAll(/href="([^"]+)"/g)].map(match => new URL(match[1], `http://localhost/${page}`)).map(url => url.pathname.slice(1) + url.hash)
    for (const href of expected) assert.ok(hrefs.includes(href), `${page}: missing ${href}`)
    assert.ok(hrefs.includes(`jianwen/${loggedIn ? 'profile' : 'login'}.html`))
    assert.equal((header.innerHTML.match(/aria-current="page"/g) || []).length, 1, `${page}: active navigation`)
  }
}
assert.equal(files.length, 15)
console.log(`All ${files.length} pages: complete navigation in both session states, shared theme last, local assets resolved, retired pages removed.`)
