import { afterEach, describe, expect, it, vi } from 'vitest'

async function loadEnv(mediaBaseUrl: string, apiBaseUrl = 'https://api.example.test/api') {
  vi.resetModules()
  vi.stubEnv('VITE_API_BASE_URL', apiBaseUrl)
  vi.stubEnv('VITE_MEDIA_BASE_URL', mediaBaseUrl)
  return import('./env')
}

describe('resolveMediaUrl', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('serves stored media paths with and without leading slash from the media origin', async () => {
    const env = await loadEnv('https://media.example.test')
    expect(env.MEDIA_ORIGIN).toBe('https://media.example.test')

    // Leading slash
    expect(env.resolveMediaUrl('/store/abc-123')).toBe('https://media.example.test/store/abc-123')
    expect(env.resolveMediaUrl('/store/stroke_ja_4e00.svg')).toBe('https://media.example.test/store/stroke_ja_4e00.svg')
    expect(env.resolveMediaUrl('/media/proxy/abc-123')).toBe('https://media.example.test/media/proxy/abc-123')
    expect(env.resolveMediaUrl('/media/library/cat_photo')).toBe('https://media.example.test/media/library/cat_photo')

    // Without leading slash
    expect(env.resolveMediaUrl('store/abc-123')).toBe('https://media.example.test/store/abc-123')
    expect(env.resolveMediaUrl('store/stroke_ja_4e00.svg')).toBe('https://media.example.test/store/stroke_ja_4e00.svg')
    expect(env.resolveMediaUrl('media/proxy/abc-123')).toBe('https://media.example.test/media/proxy/abc-123')
    expect(env.resolveMediaUrl('media/library/cat_photo')).toBe('https://media.example.test/media/library/cat_photo')
  })

  it('resolves bare sha256 hashes and UUIDs to /store/<id>', async () => {
    const env = await loadEnv('https://media.example.test')
    const sha256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    const uuid = '160ad0b0-7fd5-4d33-af96-d50cb0cb9102'
    const hexUuid = '160ad0b07fd54d33af96d50cb0cb9102'

    expect(env.resolveMediaUrl(sha256)).toBe(`https://media.example.test/store/${sha256}`)
    expect(env.resolveMediaUrl(uuid)).toBe(`https://media.example.test/store/${uuid}`)
    expect(env.resolveMediaUrl(hexUuid)).toBe(`https://media.example.test/store/${hexUuid}`)
  })

  it('resolves bare stroke keys to /store/<key>', async () => {
    const env = await loadEnv('https://media.example.test')
    expect(env.resolveMediaUrl('stroke_ja_4e00.svg')).toBe('https://media.example.test/store/stroke_ja_4e00.svg')
    expect(env.resolveMediaUrl('stroke_ja_4e00')).toBe('https://media.example.test/store/stroke_ja_4e00')
    expect(env.resolveMediaUrl('stroke_zh-hans_4e00.svg')).toBe('https://media.example.test/store/stroke_zh-hans_4e00.svg')
  })

  it('resolves user avatars across relative avatar formats', async () => {
    const env = await loadEnv('https://media.example.test')
    expect(env.resolveMediaUrl('/static/uploads/avatars/user1.webp')).toBe('https://api.example.test/static/uploads/avatars/user1.webp')
    expect(env.resolveMediaUrl('static/uploads/avatars/user1.webp')).toBe('https://api.example.test/static/uploads/avatars/user1.webp')
    expect(env.resolveMediaUrl('uploads/avatars/user1.webp')).toBe('https://api.example.test/static/uploads/avatars/user1.webp')
    expect(env.resolveMediaUrl('avatars/user1.webp')).toBe('https://api.example.test/static/uploads/avatars/user1.webp')
  })

  it('returns empty string for null, undefined, or empty values', async () => {
    const env = await loadEnv('https://media.example.test')
    expect(env.resolveMediaUrl('')).toBe('')
    expect(env.resolveMediaUrl('   ')).toBe('')
    expect(env.resolveMediaUrl(null)).toBe('')
    expect(env.resolveMediaUrl(undefined)).toBe('')
  })

  it('preserves absolute URLs, protocol-relative URLs, data and blob URIs untouched', async () => {
    const env = await loadEnv('https://media.example.test')
    expect(env.resolveMediaUrl('https://cdn.example.test/image.png')).toBe('https://cdn.example.test/image.png')
    expect(env.resolveMediaUrl('http://example.com/audio.mp3')).toBe('http://example.com/audio.mp3')
    expect(env.resolveMediaUrl('//cdn.example.test/asset.svg')).toBe('//cdn.example.test/asset.svg')
    expect(env.resolveMediaUrl('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA')).toBe('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA')
    expect(env.resolveMediaUrl('blob:http://localhost:5173/1234-5678')).toBe('blob:http://localhost:5173/1234-5678')
    expect(env.resolveMediaUrl('#section')).toBe('#section')
  })

  it('falls back cleanly to backend rules when MEDIA_ORIGIN is empty', async () => {
    const env = await loadEnv('')
    expect(env.MEDIA_ORIGIN).toBe('')

    // Stored media paths fall back to backend origin
    expect(env.resolveMediaUrl('/store/abc-123')).toBe('https://api.example.test/store/abc-123')
    expect(env.resolveMediaUrl('store/abc-123')).toBe('https://api.example.test/store/abc-123')
    expect(env.resolveMediaUrl('/media/proxy/abc-123')).toBe('https://api.example.test/media/proxy/abc-123')
    expect(env.resolveMediaUrl('media/proxy/abc-123')).toBe('https://api.example.test/media/proxy/abc-123')

    // Bare hashes fall back to /store/<hash> on backend
    const sha256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    expect(env.resolveMediaUrl(sha256)).toBe(`https://api.example.test/store/${sha256}`)

    // Staged media
    expect(env.resolveMediaUrl('/media/staged/abcdefgh')).toBe('https://api.example.test/media/staged/abcdefgh')
  })

  it('supports local development when both media and backend origins are empty', async () => {
    const env = await loadEnv('', '/api')
    expect(env.MEDIA_ORIGIN).toBe('')
    expect(env.BACKEND_ORIGIN).toBe('')

    expect(env.resolveMediaUrl('/store/abc-123')).toBe('/store/abc-123')
    expect(env.resolveMediaUrl('store/abc-123')).toBe('/store/abc-123')
    expect(env.resolveMediaUrl('/media/proxy/abc-123')).toBe('/media/proxy/abc-123')
    expect(env.resolveMediaUrl('media/proxy/abc-123')).toBe('/media/proxy/abc-123')
    expect(env.resolveMediaUrl('stroke_ja_4e00.svg')).toBe('/store/stroke_ja_4e00.svg')
    expect(env.resolveMediaUrl('uploads/avatars/user1.webp')).toBe('/static/uploads/avatars/user1.webp')
  })
})
