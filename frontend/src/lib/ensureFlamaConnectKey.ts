import { appApi } from '@/app/api'
import { loadKey } from '@/lib/secureKeyStorage'

export async function ensureFlamaConnectKey(flamaConnect: {
  getValidKey: () => string | null
  connect: (key: string, remember: boolean) => Promise<boolean>
}): Promise<string> {
  // 1. If context already has an active valid key, return it
  const activeKey = flamaConnect.getValidKey()
  if (activeKey) return activeKey

  // 2. Try loading stored key from secure storage / localStorage
  const storedKey = await loadKey()
  if (storedKey) {
    const success = await flamaConnect.connect(storedKey, true)
    if (success) {
      const valid = flamaConnect.getValidKey()
      if (valid) return valid
    }
  }

  // 3. Auto-issue a new token for the logged-in user via API
  const res = await appApi.mutate<{ item: { token?: string } }>('/integration-tokens', 'POST', {
    name: 'Anki Sync Auto Key',
    expires_in_days: 180,
  })

  if (res.item && res.item.token) {
    const newKey = res.item.token
    await flamaConnect.connect(newKey, true)
    return newKey
  }

  throw new Error('Không thể tự động khởi tạo Flama Connect Key cho tài khoản.')
}
