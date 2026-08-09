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
