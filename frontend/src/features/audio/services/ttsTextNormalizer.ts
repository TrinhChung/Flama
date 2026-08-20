/**
 * Text normalizer for speech synthesis (VOICEVOX / Kokoro).
 * Cleans HTML tags, furigana brackets, sound tags, and common entities.
 */

export function cleanTextForTts(rawText: string, engineId: 'voicevox' | 'kokoro' = 'voicevox'): string {
  if (!rawText) return ''
  let text = String(rawText)

  // 1. Strip [sound:...] media tags first
  text = text.replace(/\[sound:[^\]]+\]/gi, '')

  // 2. Strip HTML tags
  text = text.replace(/<[^>]*>/g, ' ')

  if (engineId === 'voicevox') {
    // 3. Replace Japanese furigana brackets:
    // e.g. 漢字[かんじ] -> かんじ, 食[た]べる -> たべる
    text = text.replace(/([\u4e00-\u9faf\u30a0-\u30ff]+)\s*\[([^\]]+)\]/g, '$2')
    // e.g. 漢字(かんじ) -> かんじ, 食べる(たべる) -> たべる
    text = text.replace(/([\u4e00-\u9faf\u3040-\u30ff]+)\s*\(([\u3040-\u309f]+)\)/g, '$2')
  }

  // 4. Decode common HTML entities
  text = text
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")

  return text.replace(/\s+/g, ' ').trim()
}

export function resolveLocaleFromVoiceId(voiceId: string): string {
  if (!voiceId) return 'en-US'
  const prefix = voiceId[0].toLowerCase()
  switch (prefix) {
    case 'a': return 'en-US'
    case 'b': return 'en-GB'
    case 'z': return 'zh-CN'
    case 'e': return 'es-ES'
    case 'f': return 'fr-FR'
    case 'h': return 'hi-IN'
    case 'i': return 'it-IT'
    case 'p': return 'pt-BR'
    default: return 'en-US'
  }
}
