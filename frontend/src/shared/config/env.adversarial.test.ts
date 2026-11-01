import { afterEach, describe, expect, it, vi } from 'vitest'

async function loadEnv(mediaBaseUrl: string, apiBaseUrl = 'https://api.example.test/api') {
  vi.resetModules()
  vi.stubEnv('VITE_API_BASE_URL', apiBaseUrl)
  vi.stubEnv('VITE_MEDIA_BASE_URL', mediaBaseUrl)
  return import('./env')
}

describe('resolveMediaUrl Adversarial Stress Suite', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  // -------------------------------------------------------------
  // Group 1: Malformed, Nil, Falsy, and Boundary Non-String Inputs
  // -------------------------------------------------------------
  describe('Group 1: Malformed and Falsy Inputs', () => {
    it('handles falsy and whitespace inputs without crashing', async () => {
      const env = await loadEnv('https://media.example.test')

      expect(env.resolveMediaUrl(null)).toBe('')
      expect(env.resolveMediaUrl(undefined)).toBe('')
      expect(env.resolveMediaUrl('')).toBe('')
      expect(env.resolveMediaUrl('   ')).toBe('')
      expect(env.resolveMediaUrl('\t\n\r')).toBe('')
      expect(env.resolveMediaUrl('  \t  \n  ')).toBe('')
      expect(env.resolveMediaUrl('\u00A0')).toBe('') // non-breaking space
    })

    it('handles unexpected types coerced via runtime JS', async () => {
      const env = await loadEnv('https://media.example.test')

      // @ts-expect-error Testing runtime JS callers passing numbers: 0 is falsy, safely returns ''
      expect(env.resolveMediaUrl(0)).toBe('')
      // @ts-expect-error Testing runtime JS callers passing booleans: false is falsy, safely returns ''
      expect(env.resolveMediaUrl(false)).toBe('')
      // @ts-expect-error Testing runtime JS callers passing NaN: NaN is falsy, safely returns ''
      expect(env.resolveMediaUrl(NaN)).toBe('')
    })

    it('survives long inputs without catastrophic backtracking (ReDoS)', async () => {
      const env = await loadEnv('https://media.example.test')

      const longA = 'a'.repeat(10000)
      const start = Date.now()
      const result = env.resolveMediaUrl(longA)
      const elapsed = Date.now() - start

      expect(elapsed).toBeLessThan(100) // Must resolve in < 100ms
      expect(result).toBe(`https://api.example.test/${longA}`)

      // Pathological patterns for regexes
      const pathologicalStore = '/store/' + 'a'.repeat(500)
      const resultStore = env.resolveMediaUrl(pathologicalStore)
      expect(resultStore).toBe(`https://api.example.test${pathologicalStore}`)

      const pathologicalStroke = 'stroke_' + 'a-'.repeat(250) + '.svg'
      const resultStroke = env.resolveMediaUrl(pathologicalStroke)
      expect(resultStroke).toBe(`https://media.example.test/store/${pathologicalStroke}`)
    })
  })

  // -------------------------------------------------------------
  // Group 2: Protocol Attacks, Schemes, and XSS Injection
  // -------------------------------------------------------------
  describe('Group 2: Protocol Attacks, Schemes, and XSS Vectors', () => {
    it('preserves absolute URLs with standard and custom protocols untouched', async () => {
      const env = await loadEnv('https://media.example.test')

      expect(env.resolveMediaUrl('https://media.flama.vn/store/123')).toBe('https://media.flama.vn/store/123')
      expect(env.resolveMediaUrl('http://insecure.example.com/asset.png')).toBe('http://insecure.example.com/asset.png')
      expect(env.resolveMediaUrl('ftp://files.example.com/audio.mp3')).toBe('ftp://files.example.com/audio.mp3')
      expect(env.resolveMediaUrl('blob:http://localhost:5173/00000000-0000-0000-0000-000000000000')).toBe(
        'blob:http://localhost:5173/00000000-0000-0000-0000-000000000000',
      )
      expect(env.resolveMediaUrl('data:image/svg+xml;utf8,<svg></svg>')).toBe('data:image/svg+xml;utf8,<svg></svg>')
      expect(env.resolveMediaUrl('mailto:admin@flama.vn')).toBe('mailto:admin@flama.vn')
      expect(env.resolveMediaUrl('tel:+84999999999')).toBe('tel:+84999999999')
    })

    it('preserves protocol-relative and anchor URLs untouched', async () => {
      const env = await loadEnv('https://media.example.test')

      expect(env.resolveMediaUrl('//cdn.flama.vn/store/123')).toBe('//cdn.flama.vn/store/123')
      expect(env.resolveMediaUrl('//evil.attacker.com/store/exploit')).toBe('//evil.attacker.com/store/exploit')
      expect(env.resolveMediaUrl('#section-media')).toBe('#section-media')
    })

    it('does not re-encode or break dangerous pseudo-protocols (leaves to sanitization layers)', async () => {
      const env = await loadEnv('https://media.example.test')

      // Since URL_SCHEME matches ^[a-z][a-z\d+.-]*:, these schemes are recognized and returned untouched
      expect(env.resolveMediaUrl('javascript:alert(1)')).toBe('javascript:alert(1)')
      expect(env.resolveMediaUrl('JAVASCRIPT:alert(1)')).toBe('JAVASCRIPT:alert(1)')
      expect(env.resolveMediaUrl('javascript:/*--></title></style></textarea></script>*/<svg/onload=alert(1)>')).toBe(
        'javascript:/*--></title></style></textarea></script>*/<svg/onload=alert(1)>',
      )
      expect(env.resolveMediaUrl('vbscript:msgbox(1)')).toBe('vbscript:msgbox(1)')
      expect(env.resolveMediaUrl('file:///etc/passwd')).toBe('file:///etc/passwd')
    })
  })

  // -------------------------------------------------------------
  // Group 3: Path Traversal and Special Characters
  // -------------------------------------------------------------
  describe('Group 3: Path Traversal and Directory Escaping', () => {
    it('does NOT treat path traversal attempts as stored media paths', async () => {
      const env = await loadEnv('https://media.example.test')

      // Relative escapes
      expect(env.resolveMediaUrl('../../store/secret')).toBe('https://api.example.test/../../store/secret')
      expect(env.resolveMediaUrl('../media/proxy/secret')).toBe('https://api.example.test/../media/proxy/secret')
      expect(env.resolveMediaUrl('./store/abc')).toBe('https://api.example.test/./store/abc')

      // Slashes inside asset ID segment in store path
      expect(env.resolveMediaUrl('/store/../../etc/passwd')).toBe('https://api.example.test/store/../../etc/passwd')
      expect(env.resolveMediaUrl('store/../../secret')).toBe('https://api.example.test/store/../../secret')
      expect(env.resolveMediaUrl('/media/proxy/../../secret')).toBe('https://api.example.test/media/proxy/../../secret')

      // URL-encoded traversals are rejected by MEDIA_PATH_RE because '%' is disallowed
      expect(env.resolveMediaUrl('/store/%2e%2e%2fsecret')).toBe('https://api.example.test/store/%2e%2e%2fsecret')
      expect(env.resolveMediaUrl('store/..%2fsecret')).toBe('https://api.example.test/store/..%2fsecret')
    })

    it('tests avatar path traversal boundary', async () => {
      const env = await loadEnv('https://media.example.test')

      // Slash in avatar path terminates regex match -> falls back to backend path
      expect(env.resolveMediaUrl('avatars/../../secret.webp')).toBe('https://api.example.test/avatars/../../secret.webp')
      expect(env.resolveMediaUrl('/static/uploads/avatars/../admin.webp')).toBe(
        'https://api.example.test/static/uploads/avatars/../admin.webp',
      )

      // Subdirectories inside avatars do not match AVATAR_PATH_RE
      expect(env.resolveMediaUrl('avatars/sub/user.webp')).toBe('https://api.example.test/avatars/sub/user.webp')
      expect(env.resolveMediaUrl('uploads/avatars/sub/user.webp')).toBe(
        'https://api.example.test/uploads/avatars/sub/user.webp',
      )
    })
  })

  // -------------------------------------------------------------
  // Group 4: Bare SHA-256 and UUID Boundary Testing
  // -------------------------------------------------------------
  describe('Group 4: Bare Hash and UUID Boundary Inputs', () => {
    it('accepts valid 64-char hex SHA-256 hashes in all cases', async () => {
      const env = await loadEnv('https://media.example.test')

      const shaLower = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
      const shaUpper = shaLower.toUpperCase()
      const shaMixed = 'E3b0C44298fc1c149afbF4c8996fb92427ae41E4649b934ca495991b7852b855'

      expect(env.resolveMediaUrl(shaLower)).toBe(`https://media.example.test/store/${shaLower}`)
      expect(env.resolveMediaUrl(shaUpper)).toBe(`https://media.example.test/store/${shaUpper}`)
      expect(env.resolveMediaUrl(shaMixed)).toBe(`https://media.example.test/store/${shaMixed}`)
    })

    it('rejects 63-char and 65-char hashes from bare hash matching', async () => {
      const env = await loadEnv('https://media.example.test')

      const sha63 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85'
      const sha65 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855a'

      // Does not match BARE_HASH_OR_UUID_RE, falls back to backend path
      expect(env.resolveMediaUrl(sha63)).toBe(`https://api.example.test/${sha63}`)
      expect(env.resolveMediaUrl(sha65)).toBe(`https://api.example.test/${sha65}`)
    })

    it('rejects 64-char strings containing non-hex characters', async () => {
      const env = await loadEnv('https://media.example.test')

      // 'g' is not hex
      const notHex = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85g'
      expect(env.resolveMediaUrl(notHex)).toBe(`https://api.example.test/${notHex}`)
    })

    it('accepts 32-char hex unhyphenated UUIDs / MD5 hashes', async () => {
      const env = await loadEnv('https://media.example.test')

      const hex32Lower = '160ad0b07fd54d33af96d50cb0cb9102'
      const hex32Upper = hex32Lower.toUpperCase()

      expect(env.resolveMediaUrl(hex32Lower)).toBe(`https://media.example.test/store/${hex32Lower}`)
      expect(env.resolveMediaUrl(hex32Upper)).toBe(`https://media.example.test/store/${hex32Upper}`)

      // 31 or 33 chars do not match
      expect(env.resolveMediaUrl('160ad0b07fd54d33af96d50cb0cb910')).toBe(
        'https://api.example.test/160ad0b07fd54d33af96d50cb0cb910',
      )
      expect(env.resolveMediaUrl('160ad0b07fd54d33af96d50cb0cb9102a')).toBe(
        'https://api.example.test/160ad0b07fd54d33af96d50cb0cb9102a',
      )
    })

    it('accepts standard 36-char hyphenated UUIDs in all cases', async () => {
      const env = await loadEnv('https://media.example.test')

      const uuidLower = '160ad0b0-7fd5-4d33-af96-d50cb0cb9102'
      const uuidUpper = uuidLower.toUpperCase()

      expect(env.resolveMediaUrl(uuidLower)).toBe(`https://media.example.test/store/${uuidLower}`)
      expect(env.resolveMediaUrl(uuidUpper)).toBe(`https://media.example.test/store/${uuidUpper}`)

      // Malformed UUIDs with misplaced or missing hyphens
      const malformedUuid = '160ad0b0-7fd54d33-af96-d50cb0cb9102'
      expect(env.resolveMediaUrl(malformedUuid)).toBe(`https://api.example.test/${malformedUuid}`)
    })
  })

  // -------------------------------------------------------------
  // Group 5: Kanji / Hanzi Stroke SVG Keys
  // -------------------------------------------------------------
  describe('Group 5: Kanji / Hanzi Stroke SVG Keys', () => {
    it('accepts valid stroke keys with and without .svg extension', async () => {
      const env = await loadEnv('https://media.example.test')

      expect(env.resolveMediaUrl('stroke_ja_611b.svg')).toBe('https://media.example.test/store/stroke_ja_611b.svg')
      expect(env.resolveMediaUrl('stroke_ja_611b')).toBe('https://media.example.test/store/stroke_ja_611b')
      expect(env.resolveMediaUrl('stroke_zh_4e00.svg')).toBe('https://media.example.test/store/stroke_zh_4e00.svg')
      expect(env.resolveMediaUrl('stroke_zh-hans_4e00.svg')).toBe('https://media.example.test/store/stroke_zh-hans_4e00.svg')
      expect(env.resolveMediaUrl('stroke_zh-hant_4e00.svg')).toBe('https://media.example.test/store/stroke_zh-hant_4e00.svg')
      expect(env.resolveMediaUrl('stroke_ko_ac00.svg')).toBe('https://media.example.test/store/stroke_ko_ac00.svg')
    })

    it('rejects invalid or bare stroke prefixes', async () => {
      const env = await loadEnv('https://media.example.test')

      // Bare prefix without key
      expect(env.resolveMediaUrl('stroke_')).toBe('https://api.example.test/stroke_')

      // Non-svg extension (e.g. .png)
      expect(env.resolveMediaUrl('stroke_ja_4e00.png')).toBe('https://api.example.test/stroke_ja_4e00.png')

      // Stroke key with spaces
      expect(env.resolveMediaUrl('stroke_ja 4e00.svg')).toBe('https://api.example.test/stroke_ja 4e00.svg')
    })
  })

  // -------------------------------------------------------------
  // Group 6: Stored Media Paths and Variations
  // -------------------------------------------------------------
  describe('Group 6: Stored Media Paths and Prefixes', () => {
    it('supports store, proxy, and library with or without leading slash and media/ prefix', async () => {
      const env = await loadEnv('https://media.example.test')

      const patterns = [
        ['/store/test-asset', 'https://media.example.test/store/test-asset'],
        ['store/test-asset', 'https://media.example.test/store/test-asset'],
        ['/media/store/test-asset', 'https://media.example.test/media/store/test-asset'],
        ['media/store/test-asset', 'https://media.example.test/media/store/test-asset'],
        ['/media/proxy/test-asset', 'https://media.example.test/media/proxy/test-asset'],
        ['media/proxy/test-asset', 'https://media.example.test/media/proxy/test-asset'],
        ['/proxy/test-asset', 'https://media.example.test/proxy/test-asset'],
        ['proxy/test-asset', 'https://media.example.test/proxy/test-asset'],
        ['/media/library/test-asset', 'https://media.example.test/media/library/test-asset'],
        ['media/library/test-asset', 'https://media.example.test/media/library/test-asset'],
        ['/library/test-asset', 'https://media.example.test/library/test-asset'],
        ['library/test-asset', 'https://media.example.test/library/test-asset'],
      ]

      for (const [input, expected] of patterns) {
        expect(env.resolveMediaUrl(input)).toBe(expected)
      }
    })

    it('enforces maximum length on asset ID in media path', async () => {
      const env = await loadEnv('https://media.example.test')

      // 1 char initial + 127 chars = 128 chars max
      const id128 = 'a' + 'b'.repeat(127)
      expect(env.resolveMediaUrl(`/store/${id128}`)).toBe(`https://media.example.test/store/${id128}`)

      // 129 chars exceeds {0,127}
      const id129 = 'a' + 'b'.repeat(128)
      expect(env.resolveMediaUrl(`/store/${id129}`)).toBe(`https://api.example.test/store/${id129}`)
    })

    it('rejects empty asset ID in stored media path', async () => {
      const env = await loadEnv('https://media.example.test')

      expect(env.resolveMediaUrl('/store/')).toBe('https://api.example.test/store/')
      expect(env.resolveMediaUrl('store/')).toBe('https://api.example.test/store/')
      expect(env.resolveMediaUrl('/media/proxy/')).toBe('https://api.example.test/media/proxy/')
    })
  })

  // -------------------------------------------------------------
  // Group 7: Avatar Normalization Across Prefix Variants
  // -------------------------------------------------------------
  describe('Group 7: Avatar Path Normalization', () => {
    it('normalizes all 4 avatar prefix formats to /static/uploads/avatars/<filename>', async () => {
      const env = await loadEnv('https://media.example.test')

      const expected = 'https://api.example.test/static/uploads/avatars/avatar_user1.webp'

      expect(env.resolveMediaUrl('/static/uploads/avatars/avatar_user1.webp')).toBe(expected)
      expect(env.resolveMediaUrl('static/uploads/avatars/avatar_user1.webp')).toBe(expected)
      expect(env.resolveMediaUrl('/uploads/avatars/avatar_user1.webp')).toBe(expected)
      expect(env.resolveMediaUrl('uploads/avatars/avatar_user1.webp')).toBe(expected)
      expect(env.resolveMediaUrl('/avatars/avatar_user1.webp')).toBe(expected)
      expect(env.resolveMediaUrl('avatars/avatar_user1.webp')).toBe(expected)
    })

    it('falls back to MEDIA_ORIGIN when BACKEND_ORIGIN is empty for avatars', async () => {
      const env = await loadEnv('https://media.example.test', '/api')

      // BACKEND_ORIGIN is empty because '/api' has no origin
      expect(env.BACKEND_ORIGIN).toBe('')
      expect(env.MEDIA_ORIGIN).toBe('https://media.example.test')

      expect(env.resolveMediaUrl('avatars/user.webp')).toBe(
        'https://media.example.test/static/uploads/avatars/user.webp',
      )
    })
  })

  // -------------------------------------------------------------
  // Group 8: Fallback and Edge Case Query/Hash Handling
  // -------------------------------------------------------------
  describe('Group 8: Fallbacks and Query/Hash Fragments', () => {
    it('routes query params on stored paths through fallback', async () => {
      const env = await loadEnv('https://media.example.test')

      // Query param contains '?' and '=', which are not in [A-Za-z0-9_.-]
      // Thus MEDIA_PATH_RE does not match, falls back to resolveBackendUrl
      expect(env.resolveMediaUrl('/store/image1?v=2')).toBe('https://api.example.test/store/image1?v=2')
      expect(env.resolveMediaUrl('store/image1?v=2')).toBe('https://api.example.test/store/image1?v=2')
    })

    it('preserves hash fragments in relative paths', async () => {
      const env = await loadEnv('https://media.example.test')

      expect(env.resolveMediaUrl('/store/icon.svg#layer1')).toBe('https://api.example.test/store/icon.svg#layer1')
    })

    it('handles trailing slash normalization in MEDIA_BASE_URL', async () => {
      const env = await loadEnv('https://media.example.test///')
      expect(env.MEDIA_BASE_URL).toBe('https://media.example.test')
      expect(env.MEDIA_ORIGIN).toBe('https://media.example.test')

      expect(env.resolveMediaUrl('/store/asset-1')).toBe('https://media.example.test/store/asset-1')
    })
  })
})
