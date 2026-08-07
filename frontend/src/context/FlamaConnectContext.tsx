import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type {
  FlamaAccountInfo,
  FlamaConnectErrorCategory,
} from '@/lib/flamaConnectClient'
import {
  FlamaConnectClientError,
  flamaConnectClient,
} from '@/lib/flamaConnectClient'
import {
  saveKey,
  loadKey,
  clearKey,
  getMemoryKey,
  maskKey,
} from '@/lib/secureKeyStorage'

export type FlamaConnectionStatus =
  | 'Disconnected'
  | 'Connecting'
  | 'Connected'
  | 'AuthenticationFailed'
  | 'ConnectionLost'
  | 'AuthenticationRequired'

interface FlamaConnectContextType {
  status: FlamaConnectionStatus
  account: FlamaAccountInfo | null
  error: string | null
  errorCategory: FlamaConnectErrorCategory | null
  maskedKey: string
  connect: (key: string, remember: boolean) => Promise<boolean>
  reconnect: () => Promise<boolean>
  changeKey: (newKey: string, remember: boolean) => Promise<boolean>
  forgetKey: () => Promise<void>
  disconnect: () => void
  testConnection: () => Promise<boolean>
  getValidKey: () => string | null
}

const FlamaConnectContext = createContext<FlamaConnectContextType | null>(null)

export const FlamaConnectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<FlamaConnectionStatus>('Disconnected')
  const [account, setAccount] = useState<FlamaAccountInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [errorCategory, setErrorCategory] = useState<FlamaConnectErrorCategory | null>(null)
  const [activeKey, setActiveKey] = useState<string | null>(null)

  // Auto-connect if encrypted key exists in storage on startup
  useEffect(() => {
    let active = true
    async function initializeSession() {
      const storedKey = await loadKey()
      if (!storedKey || !active) return
      setActiveKey(storedKey)
      setStatus('Connecting')
      try {
        const info = await flamaConnectClient.getCurrentUserAsync(storedKey)
        if (active) {
          setAccount(info)
          setStatus('Connected')
          setError(null)
          setErrorCategory(null)
        }
      } catch (err: any) {
        if (active) {
          setAccount(null)
          if (err instanceof FlamaConnectClientError) {
            setError(err.message)
            setErrorCategory(err.category)
            setStatus(err.category === 'NETWORK_ERROR' || err.category === 'TIMEOUT' ? 'ConnectionLost' : 'AuthenticationFailed')
          } else {
            setError('Không thể xác thực Flama Connect Key.')
            setErrorCategory('INVALID_KEY')
            setStatus('AuthenticationFailed')
          }
        }
      }
    }
    initializeSession()
    return () => {
      active = false
    }
  }, [])

  const connect = useCallback(async (key: string, remember: boolean): Promise<boolean> => {
    const trimmed = key.trim()
    if (!trimmed) {
      setError('Vui lòng nhập Flama Connect Key.')
      setErrorCategory('INVALID_KEY')
      setStatus('AuthenticationFailed')
      return false
    }

    setStatus('Connecting')
    setError(null)
    setErrorCategory(null)

    try {
      const info = await flamaConnectClient.validateKeyAsync(trimmed)
      await saveKey(trimmed, remember)
      setActiveKey(trimmed)
      setAccount(info)
      setStatus('Connected')
      return true
    } catch (err: any) {
      setAccount(null)
      if (err instanceof FlamaConnectClientError) {
        setError(err.message)
        setErrorCategory(err.category)
        setStatus(err.category === 'NETWORK_ERROR' || err.category === 'TIMEOUT' ? 'ConnectionLost' : 'AuthenticationFailed')
      } else {
        setError('Xác thực thất bại. Vui lòng kiểm tra lại key.')
        setErrorCategory('INVALID_KEY')
        setStatus('AuthenticationFailed')
      }
      return false
    }
  }, [])

  const reconnect = useCallback(async (): Promise<boolean> => {
    const key = activeKey || getMemoryKey() || (await loadKey())
    if (!key) {
      setStatus('Disconnected')
      return false
    }
    return connect(key, true)
  }, [activeKey, connect])

  const changeKey = useCallback(
    async (newKey: string, remember: boolean): Promise<boolean> => {
      return connect(newKey, remember)
    },
    [connect]
  )

  const forgetKey = useCallback(async (): Promise<void> => {
    clearKey()
    setActiveKey(null)
    setAccount(null)
    setError(null)
    setErrorCategory(null)
    setStatus('Disconnected')
  }, [])

  const disconnect = useCallback((): void => {
    setActiveKey(null)
    setAccount(null)
    setError(null)
    setErrorCategory(null)
    setStatus('Disconnected')
  }, [])

  const testConnection = useCallback(async (): Promise<boolean> => {
    const key = activeKey || getMemoryKey() || (await loadKey())
    if (!key) return false
    try {
      const info = await flamaConnectClient.getCurrentUserAsync(key)
      setAccount(info)
      setStatus('Connected')
      setError(null)
      setErrorCategory(null)
      return true
    } catch (err: any) {
      if (err instanceof FlamaConnectClientError) {
        setError(err.message)
        setErrorCategory(err.category)
        if (err.category === 'EXPIRED_KEY' || err.category === 'REVOKED_KEY' || err.category === 'INVALID_KEY') {
          setStatus('AuthenticationRequired')
        } else {
          setStatus('ConnectionLost')
        }
      } else {
        setStatus('ConnectionLost')
      }
      return false
    }
  }, [activeKey])

  const getValidKey = useCallback((): string | null => {
    if (status !== 'Connected') return null
    return activeKey || getMemoryKey()
  }, [status, activeKey])

  return (
    <FlamaConnectContext.Provider
      value={{
        status,
        account,
        error,
        errorCategory,
        maskedKey: maskKey(activeKey || getMemoryKey()),
        connect,
        reconnect,
        changeKey,
        forgetKey,
        disconnect,
        testConnection,
        getValidKey,
      }}
    >
      {children}
    </FlamaConnectContext.Provider>
  )
}

export function useFlamaConnect(): FlamaConnectContextType {
  const ctx = useContext(FlamaConnectContext)
  if (!ctx) {
    throw new Error('useFlamaConnect must be used within a FlamaConnectProvider')
  }
  return ctx
}
