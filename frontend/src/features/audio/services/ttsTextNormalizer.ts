/**
 * Text normalizer for speech synthesis (VOICEVOX / Kokoro).
 * Cleans HTML tags, furigana brackets, sound tags, and common entities.
 */

export function cleanTextForTts(rawText: string, engineId: 'voicevox' | 'kokoro' = 'voicevox'): string {
  if (!rawText) return ''
  let text = String(rawText)

  // Strip HTML tags
  text = text.replace(/<[^>]*>/g, ' ')

  if (engineId === 'voicevox') {
    // Replace Japanese furigana brackets: 漢字[かんじ] -> かんじ or 漢字(かんじ) -> かんじ
    text = text.replace(/[\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]+\s*\[([^\]]+)\]/g, '$1')
    text = text.replace(/[\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]+\s*\(([^)]+)\)/g, '$1')
  }

  // Strip [sound:...] media tags
  text = text.replace(/\[sound:[^\]]+\]/gi, '')

  // Decode common HTML entities
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
