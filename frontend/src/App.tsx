import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import './app/studyContentSync'
import { LoaderCircle } from 'lucide-react'
import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { RequireAuth } from './features/auth/components/RequireAuth'
import { RequireCreator } from './features/auth/components/RequireCreator'
import { LandingPage } from './pages/LandingPage'
import { MaintenancePage } from './pages/MaintenancePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RouteErrorBoundary } from './shared/ui/RouteErrorBoundary'
import i18n from './shared/config/i18n'
import { loadRequiredNamespaces } from './shared/config/i18n/loadGuard'
import { TranslationLoadBoundary } from './shared/config/i18n/TranslationLoadBoundary'
import {
  MAINTENANCE_PATH,
  subscribeBackendUnavailable,
} from './shared/api/backendAvailability'

const LoginPage = lazy(() =>
  import('./features/auth/pages/LoginPage').then((module) => ({
    default: module.LoginPage,
  })),
)
const RegisterPage = lazy(() =>
  import('./features/auth/pages/RegisterPage').then((module) => ({
    default: module.RegisterPage,
  })),
)
const ForgotPasswordPage = lazy(() =>
  import('./features/auth/pages/ForgotPasswordPage').then((module) => ({
    default: module.ForgotPasswordPage,
  })),
)
const ResetPasswordPage = lazy(() =>
  import('./features/auth/pages/ResetPasswordPage').then((module) => ({
    default: module.ResetPasswordPage,
  })),
)
const VerifyEmailPage = lazy(() =>
  import('./features/auth/pages/VerifyEmailPage').then((module) => ({
    default: module.VerifyEmailPage,
  })),
)

const loadDashboardPage = () =>
  import('./features/dashboard/pages/DashboardPage').then((module) => ({
    default: module.DashboardPage,
  }))

const DashboardPage = lazy(loadDashboardPage)

if (
  typeof window !== 'undefined' &&
  window.location.pathname.replace(/\/+$/, '') === '/dashboard'
) {
  // A failed speculative preload must not become an unhandled rejection.
  void loadDashboardPage().catch(() => undefined)
}
const StatisticsPage = lazy(() =>
  import('./features/statistics/pages/StatisticsPage').then((module) => ({
    default: module.StatisticsPage,
  })),
)
const BrowsePage = lazy(() =>
  import('./features/browse/pages/BrowsePage').then((module) => ({
    default: module.BrowsePage,
  })),
)
const StudyPage = lazy(() =>
  import('./features/study/pages/StudyPage').then((module) => ({
    default: module.StudyPage,
  })),
)
const NoteTypeManagerPage = lazy(() =>
  import('./features/note-types/pages/NoteTypeManagerPage').then((module) => ({
    default: module.NoteTypeManagerPage,
  })),
)
const NoteTypeFieldsPage = lazy(() =>
  import('./features/note-types/pages/NoteTypeFieldsPage').then((module) => ({
    default: module.NoteTypeFieldsPage,
  })),
)
const NoteTypeDetailPage = lazy(() =>
  import('./features/note-types/pages/NoteTypeDetailPage').then((module) => ({
    default: module.NoteTypeDetailPage,
  })),
)
const NoteTypeGuidePage = lazy(() =>
  import('./features/note-types/pages/NoteTypeGuidePage').then((module) => ({
    default: module.NoteTypeGuidePage,
  })),
)
const NoteTypeTemplatesPage = lazy(() =>
  import('./features/note-types/pages/NoteTypeTemplatesPage').then((module) => ({ default: module.NoteTypeTemplatesPage })),
)
const NoteTypeTemplateMappingPage = lazy(() =>
  import('./features/note-types/pages/NoteTypeTemplateMappingPage').then((module) => ({ default: module.NoteTypeTemplateMappingPage })),
)
const InstalledDecksPage = lazy(() =>
  import('./features/library/pages/LibraryPages').then((module) => ({
    default: module.InstalledDecksPage,
  })),
)
const TemplateLibraryPage = lazy(() =>
  import('./features/template-library').then((module) => ({ default: module.TemplateLibraryPage })),
)
const TemplateDetailPage = lazy(() =>
  import('./features/template-library').then((module) => ({ default: module.TemplateDetailPage })),
)
const InstallTemplatesPage = lazy(() =>
  import('./features/library/pages/InstallTemplatesPage').then((module) => ({ default: module.InstallTemplatesPage })),
)
const AnkiSyncPage = lazy(() =>
  import('./features/import/pages/AnkiSyncPage').then((module) => ({
    default: module.AnkiSyncPage,
  })),
)
const FileImportPage = lazy(() =>
  import('./features/import/pages/FileImportPage').then((module) => ({
    default: module.FileImportPage,
  })),
)

const SharedDecksPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePages').then((module) => ({
    default: module.SharedDecksPage,
  })),
)
const SharedDeckDetailPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePages').then((module) => ({
    default: module.SharedDeckDetailPage,
  })),
)
const SharedNoteTypesPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePages').then((module) => ({
    default: module.SharedNoteTypesPage,
  })),
)
const SharedNoteTypeDetailPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePages').then((module) => ({
    default: module.SharedNoteTypeDetailPage,
  })),
)
const PaymentResultPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePages').then((module) => ({
    default: module.PaymentResultPage,
  })),
)
const OrdersPage = lazy(() =>
  import('./features/orders/pages/OrdersPage').then((module) => ({
    default: module.OrdersPage,
  })),
)
const AdminAnalyticsPage = lazy(() =>
  import('./features/admin/pages/AdminAnalyticsPage').then((module) => ({
    default: module.AdminAnalyticsPage,
  })),
)
const AdminUsersPage = lazy(() =>
  import('./features/admin/pages/AdminUsersPage').then((module) => ({
    default: module.AdminUsersPage,
  })),
)
const AdminPaymentsPage = lazy(() =>
  import('./features/admin/pages/AdminPaymentsPage').then((module) => ({
    default: module.AdminPaymentsPage,
  })),
)
const AdminFeesPage = lazy(() =>
  import('./features/admin/pages/AdminFeesPage').then((module) => ({
    default: module.AdminFeesPage,
  })),
)
const AdminTtsPage = lazy(() =>
  import('./features/admin/pages/AdminTtsPage').then((module) => ({
    default: module.AdminTtsPage,
  })),
)
const AdminMcpTokensPage = lazy(() =>
  import('./features/admin/pages/AdminMcpTokensPage').then((module) => ({
    default: module.AdminMcpTokensPage,
  })),
)
const StudyGoalsPage = lazy(() =>
  // Goal option getters use i18n.t directly rather than useTranslation.
  Promise.all([
    import('./features/settings/pages/StudyGoalsPage'),
    loadRequiredNamespaces(i18n, ['onboarding']),
  ]).then(([module]) => ({
    default: module.StudyGoalsPage,
  })),
)
const McpTokensPage = lazy(() =>
  import('./features/settings/pages/McpTokensPage').then((module) => ({
    default: module.McpTokensPage,
  })),
)
const YomitanTokensPage = lazy(() =>
  import('./features/settings/pages/YomitanTokensPage').then((module) => ({
    default: module.YomitanTokensPage,
  })),
)
const AsbplayerTokensPage = lazy(() =>
  import('./features/settings/pages/AsbplayerTokensPage').then((module) => ({
    default: module.AsbplayerTokensPage,
  })),
)
const FeedbackPage = lazy(() =>
  import('./features/support/pages/FeedbackPage').then((module) => ({
    default: module.FeedbackPage,
  })),
)
const DeckAudioGeneratorPage = lazy(() =>
  import('./features/audio/pages/DeckAudioGeneratorPage').then((module) => ({
    default: module.DeckAudioGeneratorPage,
  })),
)
const WorksheetsPage = lazy(() =>
  import('./features/worksheets/pages/WorksheetsPage').then((module) => ({
    default: module.WorksheetsPage,
  })),
)
const AdminImageLibraryPage = lazy(() =>
  import('./features/admin/pages/AdminImageLibraryPage').then((module) => ({
    default: module.AdminImageLibraryPage,
  })),
)
const MarketplacePublishDeckPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePublishDeckPage').then((module) => ({
    default: module.MarketplacePublishDeckPage,
  })),
)
const MarketplacePublishNoteTypePage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePublishNoteTypePage').then((module) => ({
    default: module.MarketplacePublishNoteTypePage,
  })),
)
const ReleaseBuilderPage = lazy(() =>
  import('./features/deck-collaboration/pages/ReleaseBuilderPage').then((module) => ({
    default: module.ReleaseBuilderPage,
  })),
)
const InstalledDeckUpdatePage = lazy(() =>
  import('./features/deck-collaboration/pages/InstalledDeckUpdatePage').then((module) => ({
    default: module.InstalledDeckUpdatePage,
  })),
)
const DeckChangeRequestPage = lazy(() =>
  import('./features/deck-collaboration/pages/DeckChangeRequestPage').then((module) => ({
    default: module.DeckChangeRequestPage,
  })),
)
const ChangeRequestInboxPage = lazy(() =>
  import('./features/deck-collaboration/pages/ChangeRequestInboxPage').then((module) => ({
    default: module.ChangeRequestInboxPage,
  })),
)
const ChangeRequestDetailPage = lazy(() =>
  import('./features/deck-collaboration/pages/ChangeRequestDetailPage').then((module) => ({
    default: module.ChangeRequestDetailPage,
  })),
)
const AdminPermissionsPage = lazy(() =>
  import('./features/admin/pages/AdminPermissionsPage').then((module) => ({
    default: module.AdminPermissionsPage,
  })),
)
const AdminSupportConfigPage = lazy(() =>
  import('./features/admin/pages/AdminSupportConfigPage').then((module) => ({
    default: module.AdminSupportConfigPage,
  })),
)
const AdminTicketsPage = lazy(() =>
  import('./features/admin/pages/AdminTicketsPage').then((module) => ({
    default: module.AdminTicketsPage,
  })),
)
const AdminTicketDetailPage = lazy(() =>
  import('./features/admin/pages/AdminTicketDetailPage').then((module) => ({
    default: module.AdminTicketDetailPage,
  })),
)
const AdminTaxonomyPage = lazy(() =>
  import('./features/admin/pages/AdminTaxonomyPage').then((module) => ({
    default: module.AdminTaxonomyPage,
  })),
)
const UserTicketDetailPage = lazy(() =>
  import('./features/support/pages/UserTicketDetailPage').then((module) => ({
    default: module.UserTicketDetailPage,
  })),
)
const SupportPage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.SupportPage,
  })),
)
const FlamaAudioGuidePage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.FlamaAudioGuidePage,
  })),
)
const GuidePage = lazy(() =>
  import('./features/guide/pages/GuidePage').then((module) => ({
    default: module.GuidePage,
  })),
)
const TermsPage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.TermsPage,
  })),
)
const PrivacyPage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.PrivacyPage,
  })),
)
const CookiesPage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.CookiesPage,
  })),
)
const MarketplaceGuidelinesPage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.MarketplaceGuidelinesPage,
  })),
)
const CommunityGuidelinesPage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.CommunityGuidelinesPage,
  })),
)
const OAuthConsentPage = lazy(() =>
  import('./features/oauth/pages/OAuthConsentPage').then((module) => ({
    default: module.OAuthConsentPage,
  })),
)
const ProfilePage = lazy(() =>
  import('./features/profile/pages/ProfilePage').then((module) => ({
    default: module.ProfilePage,
  })),
)
const LandingStoryPreviewPage = lazy(() =>
  import('./features/landing-story/pages/LandingStoryPreviewPage').then((module) => ({
    default: module.LandingStoryPreviewPage,
  })),
)
const WalletPage = lazy(() =>
  import('./features/wallet/pages/WalletPage').then((module) => ({
    default: module.WalletPage,
  })),
)

function deferred(element: ReactNode) {
  return (
    <TranslationLoadBoundary>
    <Suspense
      fallback={
        <div className="flex min-h-80 items-center justify-center">
          <LoaderCircle className="size-7 animate-spin text-primary" />
          <span className="sr-only">Đang tải trang</span>
        </div>
      }
    >
      {element}
    </Suspense>
    </TranslationLoadBoundary>
  )
}

const router = createBrowserRouter([
  {
    path: MAINTENANCE_PATH,
    element: deferred(<MaintenancePage />),
    errorElement: <RouteErrorBoundary />,
  },
  {
    path: 'oauth/consent',
    element: deferred(<OAuthConsentPage />),
    errorElement: <RouteErrorBoundary />,
  },
  {
    // Review-only preview of the storytelling landing; `/` keeps the current landing.
    path: 'landing-story-preview',
    element: deferred(<LandingStoryPreviewPage />),
  },
  {
    element: <AppLayout />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: deferred(<LandingPage />) },
      { path: 'login', element: deferred(<LoginPage />) },
      { path: 'register', element: deferred(<RegisterPage />) },
      { path: 'forgot-password', element: deferred(<ForgotPasswordPage />) },
      { path: 'reset-password', element: deferred(<ResetPasswordPage />) },
      { path: 'verify-email', element: deferred(<VerifyEmailPage />) },
      {
        path: 'auth/verify-email',
        element: <Navigate to="/verify-email" replace />,
      },

      { path: 'support', element: deferred(<SupportPage />) },
      {
        path: 'support-donation',
        element: <Navigate to="/support" replace />,
      },
      {
        path: 'support-donation/result',
        element: deferred(<PaymentResultPage />),
      },
      {
        path: 'payments/marketplace-result',
        element: deferred(<PaymentResultPage />),
      },
      {
        path: 'payments/result',
        element: deferred(<PaymentResultPage />),
      },
      { path: 'guide', element: deferred(<GuidePage />) },
      { path: 'guide/:categorySlug', element: deferred(<GuidePage />) },
      { path: 'guide/:categorySlug/:articleSlug', element: deferred(<GuidePage />) },
      { path: 'help', element: <Navigate to="/guide" replace /> },
      { path: 'guides', element: <Navigate to="/guide" replace /> },
      { path: 'guide/tts-key', element: <Navigate to="/guide/audio/cloud-tts-keys" replace /> },
      {
        path: 'guides/tts-key',
        element: <Navigate to="/guide/audio/cloud-tts-keys" replace />,
      },
      {
        path: 'help/tts-key',
        element: <Navigate to="/guide/audio/cloud-tts-keys" replace />,
      },
      { path: 'guide/flama-audio', element: deferred(<FlamaAudioGuidePage />) },
      {
        path: 'guides/flama-audio',
        element: <Navigate to="/guide/flama-audio" replace />,
      },
      {
        path: 'help/flama-audio',
        element: <Navigate to="/guide/flama-audio" replace />,
      },
      { path: 'terms', element: deferred(<TermsPage />) },
      { path: 'privacy', element: deferred(<PrivacyPage />) },
      { path: 'cookies', element: deferred(<CookiesPage />) },
      {
        path: 'marketplace-guidelines',
        element: deferred(<MarketplaceGuidelinesPage />),
      },
      {
        path: 'community-guidelines',
        element: deferred(<CommunityGuidelinesPage />),
      },
      {
        element: <RequireAuth />,
        children: [
          { path: 'dashboard', element: deferred(<DashboardPage />) },
          { path: 'statistics', element: deferred(<StatisticsPage />) },
          { path: 'browse', element: deferred(<BrowsePage />) },
          {
            path: 'vocabulary/browse',
            element: <Navigate to="/browse" replace />,
          },
          { path: 'study', element: deferred(<StudyPage />) },
          {
            path: 'flashcards/study',
            element: <Navigate to="/study" replace />,
          },
          { path: 'note-types', element: deferred(<NoteTypeManagerPage />) },
          { path: 'card-templates', element: deferred(<TemplateLibraryPage />) },
          { path: 'card-templates/:id', element: deferred(<TemplateDetailPage />) },
          { path: 'flashcards/note-types/:id/templates', element: deferred(<NoteTypeTemplatesPage />) },
          { path: 'flashcards/note-types/:id/templates/:applicationId', element: deferred(<NoteTypeTemplateMappingPage />) },
          { path: 'note-types/:id/templates', element: deferred(<NoteTypeTemplatesPage />) },
          { path: 'note-types/:id/templates/:applicationId', element: deferred(<NoteTypeTemplateMappingPage />) },
          {
            path: 'note-types/guide',
            element: deferred(<NoteTypeGuidePage />),
          },
          {
            path: 'note-types/:id',
            element: deferred(<NoteTypeDetailPage />),
          },
          {
            path: 'note-types/:id/fields',
            element: deferred(<NoteTypeFieldsPage />),
          },
          {
            path: 'flashcards/note-types',
            element: deferred(<NoteTypeManagerPage />),
          },
          {
            path: 'flashcards/note-types/guide',
            element: deferred(<NoteTypeGuidePage />),
          },
          {
            path: 'flashcards/note-types/:id',
            element: deferred(<NoteTypeDetailPage />),
          },
          {
            path: 'flashcards/note-types/:id/fields',
            element: deferred(<NoteTypeFieldsPage />),
          },
          {
            path: 'installed-decks',
            element: deferred(<InstalledDecksPage />),
          },
          {
            path: 'installed-decks/:installId/templates',
            element: deferred(<InstallTemplatesPage />),
          },
          {
            path: 'installed-decks/:installId/updates/:releaseId',
            element: deferred(<InstalledDeckUpdatePage />),
          },
          {
            path: 'flashcards/installed-decks',
            element: <Navigate to="/installed-decks" replace />,
          },
          {
            path: 'flashcards/shared-decks/:deckItemId/change-request',
            element: deferred(<DeckChangeRequestPage />),
          },
          {
            path: 'flashcards/change-requests/incoming',
            element: deferred(<ChangeRequestInboxPage />),
          },
          {
            path: 'flashcards/change-requests/:requestId',
            element: deferred(<ChangeRequestDetailPage />),
          },
          {
            path: 'worksheets',
            element: deferred(<WorksheetsPage />),
          },
          {
            path: 'audio/generate',
            element: deferred(<DeckAudioGeneratorPage />),
          },
          {
            path: 'audio',
            element: <Navigate to="/audio/generate" replace />,
          },
          {
            path: 'flashcards/audio',
            element: <Navigate to="/audio/generate" replace />,
          },
          {
            path: 'flashcards/sync',
            element: deferred(<AnkiSyncPage />),
          },
          {
            path: 'sync',
            element: deferred(<AnkiSyncPage />),
          },
          {
            path: 'flashcards/import',
            element: deferred(<FileImportPage />),
          },
          {
            path: 'import',
            element: deferred(<FileImportPage />),
          },
          {
            element: <RequireCreator />,
            children: [
              {
                path: 'creator/decks/:itemId/releases/new',
                element: deferred(<ReleaseBuilderPage />),
              },
            ],
          },
          {
            path: 'settings/goals',
            element: deferred(<StudyGoalsPage />),
          },
          {
            path: 'goals',
            element: <Navigate to="/settings/goals" replace />,
          },
          {
            path: 'settings/mcp-tokens',
            element: deferred(<McpTokensPage />),
          },
          {
            path: 'settings/yomitan',
            element: deferred(<YomitanTokensPage />),
          },
          {
            path: 'settings/asbplayer',
            element: deferred(<AsbplayerTokensPage />),
          },
          {
            path: 'asbplayer',
            element: <Navigate to="/settings/asbplayer" replace />,
          },
          {
            path: 'feedback',
            element: deferred(<FeedbackPage />),
          },
          {
            path: 'tickets',
            element: deferred(<FeedbackPage />),
          },
          {
            path: 'tickets/:id',
            element: deferred(<UserTicketDetailPage />),
          },
          {
            path: 'support/feedback',
            element: deferred(<FeedbackPage />),
          },
          {
            path: 'mcp-tokens',
            element: <Navigate to="/settings/mcp-tokens" replace />,
          },
          {
            path: 'marketplace/decks',
            element: deferred(<SharedDecksPage />),
          },
          {
            path: 'marketplace/decks/publish',
            element: deferred(<MarketplacePublishDeckPage />),
          },
          {
            path: 'marketplace/decks/:id',
            element: deferred(<SharedDeckDetailPage />),
          },
          {
            path: 'flashcards/shared-decks/:id',
            element: deferred(<SharedDeckDetailPage />),
          },
          {
            path: 'marketplace/note-types',
            element: deferred(<SharedNoteTypesPage />),
          },
          {
            path: 'marketplace/note-types/publish',
            element: deferred(<MarketplacePublishNoteTypePage />),
          },
          {
            path: 'marketplace/note-types/:id',
            element: deferred(<SharedNoteTypeDetailPage />),
          },
          {
            path: 'flashcards/shared-note-types/:id',
            element: deferred(<SharedNoteTypeDetailPage />),
          },
          { path: 'orders', element: deferred(<OrdersPage />) },
          { path: 'profile', element: deferred(<ProfilePage />) },
          { path: 'profile/:username', element: deferred(<ProfilePage />) },
          { path: 'wallet', element: deferred(<WalletPage />) },
          { path: 'admin', element: <Navigate to="/admin/analytics" replace /> },
          {
            path: 'admin/analytics',
            element: deferred(<AdminAnalyticsPage />),
          },
          { path: 'admin/users', element: deferred(<AdminUsersPage />) },
          {
            path: 'admin/payments',
            element: deferred(<AdminPaymentsPage />),
          },
          {
            path: 'admin/fees',
            element: deferred(<AdminFeesPage />),
          },
          { path: 'admin/tts', element: deferred(<AdminTtsPage />) },
          {
            path: 'admin/image-library',
            element: deferred(<AdminImageLibraryPage />),
          },
          {
            path: 'admin/permissions',
            element: deferred(<AdminPermissionsPage />),
          },
          {
            path: 'admin/mcp-tokens',
            element: deferred(<AdminMcpTokensPage />),
          },
          {
            path: 'admin/support',
            element: deferred(<AdminSupportConfigPage />),
          },
          {
            path: 'admin/tickets',
            element: deferred(<AdminTicketsPage />),
          },
          {
            path: 'admin/tickets/:id',
            element: deferred(<AdminTicketDetailPage />),
          },
          {
            path: 'admin/taxonomy',
            element: deferred(<AdminTaxonomyPage />),
          },
        ],
      },
      { path: 'home', element: <Navigate to="/dashboard" replace /> },
      { path: '*', element: deferred(<NotFoundPage />) },
    ],
  },
])

export default function App() {
  useEffect(
    () =>
      subscribeBackendUnavailable(() => {
        if (router.state.location.pathname !== MAINTENANCE_PATH) {
          void router.navigate(MAINTENANCE_PATH, { replace: true })
        }
      }),
    [],
  )

  return <RouterProvider router={router} />
}
