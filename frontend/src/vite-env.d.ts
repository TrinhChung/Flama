/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_BACKEND_ORIGIN?: string
  readonly VITE_FLASK_ORIGIN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
