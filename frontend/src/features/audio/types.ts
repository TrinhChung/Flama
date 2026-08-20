export type TtsOptions = {
  speed?: number
  pitch?: number
  intonation?: number
  volume?: number
}

export type TtsRequest = {
  request_id: string
  engine_id: string
  language: string
  voice_id: string
  text: string
  output_format?: string
  options?: TtsOptions
}

export type VoiceDescriptor = {
  voice_id: string
  name: string
  speaker_name: string
  style_name: string
  locale: string
  commercial_safe: boolean
  attribution?: string
}

export type EnginePackageState = {
  engine_id: string
  installed_version?: string
  status: string
  is_available: boolean
}

export type PairingChallenge = {
  pairing_id: string
  origin: string
  client_info: string
  approved: boolean
  token?: string
  created_at: string
}

export type LocalAudioServiceStatus = {
  status: string
  app: string
  version: string
  port: number
}

// ----------------------------------------------------
// Deck Audio Generator & Queue Engine Types
// ----------------------------------------------------

export type FieldMapping = {
  id: string
  sourceField: string
  destinationField: string
}

export type AudioRuleConfig = {
  id: string
  name: string
  engineId: 'voicevox' | 'kokoro'
  voiceId: string
  speed: number
  pitch: number
  intonation: number
  volume: number
  mappings: FieldMapping[]
}

export type AudioJobItemStatus = 'pending' | 'synthesizing' | 'uploading' | 'done' | 'failed' | 'skipped'

export type AudioJobItem = {
  id: string
  noteId: string
  cardId?: string
  word: string
  sourceField: string
  destinationField: string
  text: string
  engineId: 'voicevox' | 'kokoro'
  voiceId: string
  options: TtsOptions
  status: AudioJobItemStatus
  error?: string
  assetUrl?: string
}

export type AudioDeckJobStatus = 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'

export type AudioDeckJob = {
  id: string
  deckId: number
  deckName: string
  createdAt: string
  startedAt?: string
  completedAt?: string
  status: AudioDeckJobStatus
  rules: AudioRuleConfig[]
  mode: 'missing_and_broken' | 'all'
  stats: {
    totalItems: number
    completedItems: number
    failedItems: number
    skippedItems: number
    currentItemIndex: number
    progressPercent: number
    currentWord?: string
    currentField?: string
  }
  items: AudioJobItem[]
}

export type DeckScanSummary = {
  total_notes: number
  needs_audio_count: number
  missing_field_count: number
  broken_field_count: number
  valid_field_count: number
}

export type DeckScanAutoMapping = {
  source_field: string
  destination_field: string
  confidence: string
}

export type DeckScanFieldDef = {
  name: string
  field_type: string
  position: number
  required: boolean
}

export type DeckScanNoteType = {
  id: string
  name: string
  fields: DeckScanFieldDef[]
}

export type AudioFieldStatus = {
  status: 'missing' | 'broken' | 'valid'
  value?: string
  asset_id?: string | null
  url?: string | null
  filename?: string
  reason?: string
}

export type DeckScanNoteItem = {
  note_id: string
  card_id: string
  word: string
  note_type_id: string
  field_values: Record<string, string>
  audio_status: Record<string, AudioFieldStatus>
  needs_audio: boolean
}

export type DeckScanResponse = {
  deck: {
    id: number
    name: string
  }
  total_notes: number
  summary: DeckScanSummary
  note_types: DeckScanNoteType[]
  auto_mappings: DeckScanAutoMapping[]
  notes: DeckScanNoteItem[]
}
