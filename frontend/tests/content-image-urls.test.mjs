import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

test('API images resolve to the server in native App pages', async () => {
  const source = (await readFile(new URL('../utils/api.js', import.meta.url), 'utf8'))
    .replace('import.meta.env.VITE_API_BASE_URL', "'http://8.147.110.194'")
  const prior = globalThis.uni
  globalThis.uni = {
    getStorageSync() { return '' },
    request({ url, success }) {
      const data = url.endsWith('/classic-books')
        ? [{ book_id: 'book', cover_image: '/static/books/book.jpg' }]
        : {
          topics: [{ image: '/static/images/就业.jpg' }],
          features: [{ image: 'https://example.com/cover.jpg' }],
          updates: [{ image: '/uploads/article.jpg' }, { image: '' }]
        }
      success({ statusCode: 200, data })
    }
  }
  try {
    const api = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
    const content = await api.getDiscoverContent()
    assert.equal(content.topics[0].image, 'http://8.147.110.194/static/images/就业.jpg')
    assert.equal(content.features[0].image, 'https://example.com/cover.jpg')
    assert.equal(content.updates[0].image, 'http://8.147.110.194/uploads/article.jpg')
    assert.equal(content.updates[1].image, '')
    assert.equal((await api.getClassicBooks())[0].coverImage, 'http://8.147.110.194/static/books/book.jpg')
  } finally {
    globalThis.uni = prior
  }
})
