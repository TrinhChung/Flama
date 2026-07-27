export type FrontendRole = {
  code: string
  name: string
}

export type FrontendUser = {
  id: number
  email: string
  username: string
  timezone: string
  is_admin: boolean
  role: FrontendRole | null
}

export type FlashMessage = {
  category: string
  message: string
}

export type FrontendLinks = {
  react_root: string
  dashboard: string
  statistics: string
  legacy_dashboard: string
  browse: string
  study: string
  note_types: string
  installed_decks: string
  shared_decks: string
  shared_note_types: string
  orders: string
  support: string
  terms: string
  privacy: string
  cookies: string
  admin_users: string | null
  admin_payments: string | null
  admin_tts: string | null
}

export type FrontendBootstrap = {
  api_version: string
  csrf_token: string
  user: FrontendUser | null
  messages: FlashMessage[]
  support_contact_email: string
  links: FrontendLinks
}
