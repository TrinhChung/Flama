import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { i18nReady } from '@/shared/config/i18n'
import { TranslationLoadBoundary, TranslationLoadFailure } from '@/shared/config/i18n/TranslationLoadBoundary'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import './index.css'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
})

const root = createRoot(document.getElementById('root')!)
void i18nReady.then(() => {
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <TranslationLoadBoundary><App /></TranslationLoadBoundary>
          <Toaster position="bottom-right" richColors />
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
}).catch(() => root.render(<TranslationLoadFailure />))
