// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useLocalAudioEngine } from './useLocalAudioEngine'
import { apiRequest } from '@/shared/api/client'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const client = vi.hoisted(() => ({
  getHealth: vi.fn(), getToken: vi.fn(), startPairing: vi.fn(), getPairingStatus: vi.fn(),
  setToken: vi.fn(), getVoices: vi.fn(), installEngine: vi.fn(), launchEngine: vi.fn(),
  synthesize: vi.fn(),
}))
const notifications = vi.hoisted(() => ({ info: vi.fn(), success: vi.fn(), error: vi.fn() }))
vi.mock('@/lib/flamaAudioClient', () => ({ flamaAudioClient: client }))
vi.mock('sonner', () => ({ toast: notifications }))
vi.mock('@/shared/api/client', () => ({ apiRequest: vi.fn().mockResolvedValue({ items: [] }) }))

const emptyCards: string[] = []
const fields = ['Word']
const audioFields = ['Audio']
let engine!: ReturnType<typeof useLocalAudioEngine>
function Harness({ isOpen = true, engineId = 'voicevox', selectedCardIds = emptyCards, targetKind = 'card' }: { isOpen?: boolean; engineId?: 'voicevox' | 'kokoro'; selectedCardIds?: string[]; targetKind?: 'card' | 'note' }) {
  engine = useLocalAudioEngine({ isOpen, engineId, selectedCardIds, targetKind, availableFieldNames: fields, availableAudioFieldNames: audioFields })
  return null
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('local engine polling lifecycle', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(async () => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    Object.values(client).forEach((mock) => mock.mockReset())
    vi.mocked(apiRequest).mockResolvedValue({ items: [] })
    localStorage.clear()
    client.getHealth.mockRejectedValue(new Error('offline'))
    client.getVoices.mockResolvedValue([])
    client.installEngine.mockResolvedValue({ status: 'ok', message: '' })
    client.launchEngine.mockResolvedValue({ status: 'ok', message: '' })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    await act(async () => { root.render(<Harness />) })
  })

  afterEach(async () => {
    await act(async () => { root.unmount() })
    container.remove()
    vi.useRealTimers()
  })

  it('loads a selected Browse Note directly without a presentation ID', async () => {
    await act(async () => { root.render(<Harness selectedCardIds={['note-only']} targetKind="note" />) })
    expect(apiRequest).toHaveBeenCalledWith('/api/browse/notes/note-only')
  })

  it('keeps the display word and media permission from a selected Note response', async () => {
    vi.mocked(apiRequest).mockResolvedValue({
      row: { note_id: 'note-only', word: '日本語' },
      note: { id: 'note-only', field_values: { Word: '日本語' } },
      fields: [{ name: 'Word', field_type: 'text' }, { name: 'Audio', field_type: 'audio' }],
      can_upload_media: false,
    })
    await act(async () => { root.render(<Harness selectedCardIds={['note-only']} targetKind="note" />) })
    await act(async () => { await engine.handleStartBatch() })
    expect(engine.items).toMatchObject([{ noteId: 'note-only', word: '日本語', sourceText: '日本語', status: 'skipped' }])
    expect(client.synthesize).not.toHaveBeenCalled()
  })

  it('previews the Note display word when the selected source field is empty', async () => {
    vi.mocked(apiRequest).mockResolvedValue({
      row: { note_id: 'note-only', word: '日本語' },
      note: { id: 'note-only', field_values: { Word: '' } },
    })
    client.synthesize.mockRejectedValue(new Error('offline'))
    await act(async () => { root.render(<Harness selectedCardIds={['note-only']} targetKind="note" />) })
    await act(async () => { await engine.handlePreviewAudio() })
    expect(client.synthesize).toHaveBeenCalledWith(expect.objectContaining({ text: '日本語' }))
  })

  it('sends native array source text to synthesis for a selected Note', async () => {
    vi.mocked(apiRequest).mockResolvedValue({
      row: { note_id: 'note-only', word: '日本語' },
      note: { id: 'note-only', field_values: { Word: ['日本語', ['勉強']] } },
    })
    client.synthesize.mockRejectedValue(new Error('offline'))
    await act(async () => { root.render(<Harness selectedCardIds={['note-only']} targetKind="note" />) })
    await act(async () => { await engine.handleStartBatch() })
    expect(client.synthesize).toHaveBeenCalledWith(expect.objectContaining({ text: '日本語 勉強' }))
    expect(engine.items).toMatchObject([{ noteId: 'note-only', word: '日本語', error: 'offline' }])
  })

  it('stops installation after 15 empty voice lists and returns to idle', async () => {
    await act(async () => { await engine.handleInstallEngine() })
    await act(async () => { await vi.advanceTimersByTimeAsync(90_000) })
    expect(client.getVoices).toHaveBeenCalledTimes(15)
    expect(engine.engineActionState).toBe('idle')
    expect(notifications.error).toHaveBeenCalledWith('Quá thời gian chờ Engine khởi động. Vui lòng kiểm tra lại ứng dụng Desktop.')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('stops launch after eight empty voice lists without an error notification', async () => {
    await act(async () => { await engine.handleLaunchEngine() })
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
    expect(client.getVoices).toHaveBeenCalledTimes(8)
    expect(engine.engineActionState).toBe('idle')
    expect(notifications.error).not.toHaveBeenCalled()
  })

  it('stops immediately when the desktop engine returns usable voices', async () => {
    client.getVoices.mockResolvedValue([{ voice_id: '3', name: 'VOICEVOX', speaker_name: 'Zundamon', style_name: 'Normal', locale: 'ja-JP', commercial_safe: true }])
    await act(async () => { await engine.handleInstallEngine() })
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
    expect(client.getVoices).toHaveBeenCalledTimes(1)
    expect(engine.engineOffline).toBe(false)
    expect(engine.engineActionState).toBe('idle')
    expect(notifications.success).toHaveBeenCalledWith('VOICEVOX Engine đã sẵn sàng!')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('does not overlap slow voice requests, and closing cancels the in-flight request', async () => {
    const pending = deferred<never[]>()
    client.getVoices.mockReturnValue(pending.promise)
    await act(async () => { await engine.handleInstallEngine() })
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })
    expect(client.getVoices).toHaveBeenCalledTimes(1)
    const signal = client.getVoices.mock.calls[0][1] as AbortSignal
    await act(async () => { root.render(<Harness isOpen={false} />) })
    expect(signal.aborted).toBe(true)
    await act(async () => { pending.resolve([]); await vi.advanceTimersByTimeAsync(60_000) })
    expect(client.getVoices).toHaveBeenCalledTimes(1)
    expect(notifications.error).not.toHaveBeenCalled()
    expect(engine.engineActionState).toBe('idle')
  })

  it('superseding launch cancels installation without letting a late install response start a poll', async () => {
    const pending = deferred<{ status: string; message: string }>()
    client.installEngine.mockReturnValue(pending.promise)
    let install!: Promise<void>
    await act(async () => { install = engine.handleInstallEngine() })
    const signal = client.installEngine.mock.calls[0][1] as AbortSignal
    await act(async () => { await engine.handleLaunchEngine() })
    expect(signal.aborted).toBe(true)
    await act(async () => { pending.resolve({ status: 'ok', message: 'old install' }); await install })
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })
    expect(client.getVoices).toHaveBeenCalledTimes(8)
    expect(notifications.success).not.toHaveBeenCalledWith('old install')
  })

  it('cancels pending engine polling when switching engines', async () => {
    await act(async () => { await engine.handleLaunchEngine() })
    const signal = client.launchEngine.mock.calls[0][1] as AbortSignal
    await act(async () => { root.render(<Harness engineId="kokoro" />) })
    expect(signal.aborted).toBe(true)
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })
    expect(client.getVoices).not.toHaveBeenCalled()
    expect(engine.engineActionState).toBe('idle')
  })

  it('cannot start a polling timer from an installation response received after unmount', async () => {
    const pending = deferred<{ status: string; message: string }>()
    client.installEngine.mockReturnValue(pending.promise)
    let install!: Promise<void>
    await act(async () => { install = engine.handleInstallEngine() })
    const signal = client.installEngine.mock.calls[0][1] as AbortSignal
    await act(async () => { root.unmount() })
    root = createRoot(container)
    expect(signal.aborted).toBe(true)
    await act(async () => { pending.resolve({ status: 'ok', message: '' }); await install; await vi.advanceTimersByTimeAsync(60_000) })
    expect(client.getVoices).not.toHaveBeenCalled()
    expect(notifications.error).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('ends an unapproved pairing challenge after 40 settled requests', async () => {
    client.startPairing.mockResolvedValue({ pairing_id: 'first', approved: false })
    client.getPairingStatus.mockResolvedValue({ pairing_id: 'first', approved: false })
    await act(async () => { await engine.handleStartPairing() })
    await act(async () => { await vi.advanceTimersByTimeAsync(120_000) })
    expect(client.getPairingStatus).toHaveBeenCalledTimes(40)
    expect(engine.pairingChallengeId).toBeNull()
    expect(engine.isPairingApproved).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('cannot save a token from an old pairing challenge after it has been replaced', async () => {
    const pending = deferred<{ pairing_id: string; approved: boolean; token: string }>()
    client.startPairing.mockResolvedValueOnce({ pairing_id: 'first', approved: false })
      .mockResolvedValueOnce({ pairing_id: 'second', approved: false })
    client.getPairingStatus.mockReturnValueOnce(pending.promise)
      .mockResolvedValue({ pairing_id: 'second', approved: false })
    await act(async () => { await engine.handleStartPairing(); await vi.advanceTimersByTimeAsync(1500) })
    const signal = client.getPairingStatus.mock.calls[0][1] as AbortSignal
    await act(async () => { await engine.handleStartPairing() })
    expect(signal.aborted).toBe(true)
    await act(async () => { pending.resolve({ pairing_id: 'first', approved: true, token: 'stale-token' }) })
    expect(client.setToken).not.toHaveBeenCalled()
    expect(engine.pairingChallengeId).toBe('second')
    expect(engine.isPairingApproved).toBe(false)
    expect(notifications.success).not.toHaveBeenCalled()
  })
})
