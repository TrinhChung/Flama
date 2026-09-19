// @vitest-environment jsdom

import { describe, it, expect, beforeEach } from 'vitest'
import { cleanTextForTts, resolveLocaleFromVoiceId } from './services/ttsTextNormalizer'
import {
  clearStoredAudioQueue,
  loadStoredAudioQueue,
  loadStoredConcurrency,
  saveStoredAudioQueue,
  saveStoredConcurrency,
} from './services/audioQueueStorage'
import type { AudioDeckJob } from './types'

describe('TTS Text Normalizer', () => {
  it('strips HTML tags cleanly', () => {
    const raw = '<p>Hello <strong>World</strong>!</p>'
    expect(cleanTextForTts(raw, 'kokoro')).toBe('Hello World !')
  })

  it('handles Japanese furigana brackets for VOICEVOX', () => {
    const raw1 = '漢字[かんじ]を勉強[べんきょう]する'
    expect(cleanTextForTts(raw1, 'voicevox')).toBe('かんじをべんきょうする')

    const raw2 = '食べる(たべる)'
    expect(cleanTextForTts(raw2, 'voicevox')).toBe('たべる')

    const raw3 = '食[た]べる'
    expect(cleanTextForTts(raw3, 'voicevox')).toBe('たべる')
  })

  it('extracts ruby <rt> reading for VOICEVOX speech synthesis', () => {
    expect(cleanTextForTts('<ruby>食<rt>た</rt></ruby>べる', 'voicevox')).toBe('たべる')
    expect(cleanTextForTts('<ruby>日<rt>に</rt>本<rt>ほん</rt>語<rt>ご</rt></ruby>', 'voicevox')).toBe('にほんご')
    expect(cleanTextForTts('<ruby>食<rp>(</rp><rt>た</rt><rp>)</rp></ruby>べる', 'voicevox')).toBe('たべる')
  })

  it('strips [sound:...] media tags', () => {
    const raw = '猫[sound:cat_audio.mp3]が好き'
    expect(cleanTextForTts(raw, 'voicevox')).toBe('猫が好き')
  })

  it('decodes HTML entities correctly', () => {
    const raw = 'A &amp; B &gt; C &lt; D &quot;quote&quot; &#39;single&#39; &nbsp; spaced'
    expect(cleanTextForTts(raw, 'kokoro')).toBe("A & B > C < D \"quote\" 'single' spaced")
  })

  it('resolves correct locale from Kokoro voice ID prefixes', () => {
    expect(resolveLocaleFromVoiceId('af_bella')).toBe('en-US')
    expect(resolveLocaleFromVoiceId('am_adam')).toBe('en-US')
    expect(resolveLocaleFromVoiceId('bf_emma')).toBe('en-GB')
    expect(resolveLocaleFromVoiceId('bm_george')).toBe('en-GB')
    expect(resolveLocaleFromVoiceId('zf_xiaobei')).toBe('zh-CN')
    expect(resolveLocaleFromVoiceId('zm_yunjian')).toBe('zh-CN')
    expect(resolveLocaleFromVoiceId('ef_dora')).toBe('es-ES')
    expect(resolveLocaleFromVoiceId('ff_siwis')).toBe('fr-FR')
    expect(resolveLocaleFromVoiceId('hf_alpha')).toBe('hi-IN')
    expect(resolveLocaleFromVoiceId('if_sara')).toBe('it-IT')
    expect(resolveLocaleFromVoiceId('pf_dora')).toBe('pt-BR')
  })
})

describe('Audio Queue Storage & Concurrency Persistence', () => {
  beforeEach(() => {
    clearStoredAudioQueue()
    localStorage.removeItem('flama_deck_audio_concurrency_v1')
  })

  it('saves and loads audio queue from localStorage', () => {
    const mockJobs: AudioDeckJob[] = [
      {
        id: 'job_1',
        deckId: 10,
        deckName: 'Minna No Nihongo',
        createdAt: '2026-08-20T00:00:00Z',
        status: 'queued',
        mode: 'missing_and_broken',
        rules: [],
        stats: {
          totalItems: 5,
          completedItems: 0,
          failedItems: 0,
          skippedItems: 0,
          currentItemIndex: 0,
          progressPercent: 0,
        },
        items: [],
      },
    ]

    saveStoredAudioQueue(mockJobs)
    const loaded = loadStoredAudioQueue()
    expect(loaded).toHaveLength(1)
    expect(loaded[0].id).toBe('job_1')
    expect(loaded[0].deckName).toBe('Minna No Nihongo')
  })

  it('transitions interrupted running jobs to paused on restore', () => {
    const mockJobs: AudioDeckJob[] = [
      {
        id: 'job_running',
        deckId: 20,
        deckName: 'N3 Kanji',
        createdAt: '2026-08-20T00:00:00Z',
        status: 'running',
        mode: 'all',
        rules: [],
        stats: {
          totalItems: 10,
          completedItems: 4,
          failedItems: 0,
          skippedItems: 0,
          currentItemIndex: 5,
          progressPercent: 40,
        },
        items: [],
      },
    ]

    saveStoredAudioQueue(mockJobs)
    const loaded = loadStoredAudioQueue()
    expect(loaded).toHaveLength(1)
    expect(loaded[0].id).toBe('job_running')
    expect(loaded[0].status).toBe('paused')
    expect(loaded[0].stats.completedItems).toBe(4)
    expect(loaded[0].stats.progressPercent).toBe(40)
  })

  it('clears stored audio queue', () => {
    saveStoredAudioQueue([
      {
        id: 'job_temp',
        deckId: 1,
        deckName: 'Test',
        createdAt: '',
        status: 'completed',
        mode: 'all',
        rules: [],
        stats: {
          totalItems: 0,
          completedItems: 0,
          failedItems: 0,
          skippedItems: 0,
          currentItemIndex: 0,
          progressPercent: 100,
        },
        items: [],
      },
    ])
    expect(loadStoredAudioQueue()).toHaveLength(1)

    clearStoredAudioQueue()
    expect(loadStoredAudioQueue()).toHaveLength(0)
  })

  it('loads default concurrency of 3 when unconfigured', () => {
    expect(loadStoredConcurrency()).toBe(3)
  })

  it('saves and loads custom concurrency, clamping values between 1 and 5', () => {
    saveStoredConcurrency(4)
    expect(loadStoredConcurrency()).toBe(4)

    saveStoredConcurrency(10) // should clamp to 5
    expect(loadStoredConcurrency()).toBe(5)

    saveStoredConcurrency(0) // should clamp to 1
    expect(loadStoredConcurrency()).toBe(1)
  })
})
