/**
 * Secure Key Storage helper using Web Crypto API (AES-GCM) with device entropy.
 * Ensures the Flama Connect key is never stored in plain text.
 */

const STORAGE_KEY = 'flama_connect_encrypted_credential_v1'
const SALT_KEY = 'flama_connect_credential_salt_v1'
let memoryKey: string | null = null

export function maskKey(key: string | null | undefined): string {
  if (!key || typeof key !== 'string' || key.length < 12) {
    return 'flama_yt_****'
  }
  const trimmed = key.trim()
  const prefix = trimmed.slice(0, 8)
  const suffix = trimmed.slice(-3)
  return `${prefix}_****...****${suffix}`
}

export function redact_sensitive_text(text: string): string {
  if (!text || typeof text !== 'string') return text
  return text.replace(/flama_[a-zA-Z0-9_-]{12,128}/g, (match) => maskKey(match))
}

async function getDerivedKey(salt: Uint8Array): Promise<CryptoKey> {
  const deviceEntropy = `${navigator.userAgent}-${navigator.language}-${screen.width}x${screen.height}`
  const encoder = new TextEncoder()
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    encoder.encode(deviceEntropy),
    { name: 'PBKDF2' },
    false,
    ['deriveKey']
  )
  const saltBuffer = salt.buffer.slice(salt.byteOffset, salt.byteOffset + salt.byteLength) as ArrayBuffer
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: saltBuffer,
      iterations: 100000,
      hash: 'SHA-256',
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  )
}

export async function saveKey(key: string, remember: boolean): Promise<void> {
  const trimmedKey = key.trim()
  memoryKey = trimmedKey

  if (!remember) {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(SALT_KEY)
    return
  }

  try {
    const salt = crypto.getRandomValues(new Uint8Array(16))
    const iv = crypto.getRandomValues(new Uint8Array(12))
    const derivedKey = await getDerivedKey(salt)
    const encoder = new TextEncoder()

    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      derivedKey,
      encoder.encode(trimmedKey)
    )

    const payload = {
      iv: Array.from(iv),
      data: Array.from(new Uint8Array(encrypted)),
    }

    localStorage.setItem(SALT_KEY, JSON.stringify(Array.from(salt)))
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch (err) {
    console.warn('[FlamaConnectStorage] Secure persistence unavailable, keeping in memory session.', err)
  }
}

export async function loadKey(): Promise<string | null> {
  if (memoryKey) return memoryKey

  const rawPayload = localStorage.getItem(STORAGE_KEY)
  const rawSalt = localStorage.getItem(SALT_KEY)

  if (!rawPayload || !rawSalt) return null

  try {
    const salt = new Uint8Array(JSON.parse(rawSalt))
    const { iv, data } = JSON.parse(rawPayload)
    const derivedKey = await getDerivedKey(salt)

    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: new Uint8Array(iv) },
      derivedKey,
      new Uint8Array(data)
    )

    const decoder = new TextDecoder()
    const decryptedKey = decoder.decode(decrypted)
    memoryKey = decryptedKey
    return decryptedKey
  } catch (err) {
    console.warn('[FlamaConnectStorage] Failed to decrypt stored credential, resetting storage.', err)
    clearKey()
    return null
  }
}

export function clearKey(): void {
  memoryKey = null
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem(SALT_KEY)
}

export function getMemoryKey(): string | null {
  return memoryKey
}
