import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { RequireAuth } from './features/auth/components/RequireAuth'
import { LandingPage } from './pages/LandingPage'
import { MaintenancePage } from './pages/MaintenancePage'
import { NotFoundPage } from './pages/NotFoundPage'
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
const DashboardPage = lazy(() =>
  import('./features/dashboard/pages/DashboardPage').then((module) => ({
    default: module.DashboardPage,
  })),
)
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
const InstalledDecksPage = lazy(() =>
  import('./features/library/pages/LibraryPages').then((module) => ({
    default: module.InstalledDecksPage,
  })),
)
const ImportPage = lazy(() =>
  import('./features/import/pages/ImportPage').then((module) => ({
    default: module.ImportPage,
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
const OrdersPage = lazy(() =>
  import('./features/orders/pages/OrdersPage').then((module) => ({
    default: module.OrdersPage,
  })),
)
const AdminUsersPage = lazy(() =>
  import('./features/admin/pages/AdminPages').then((module) => ({
    default: module.AdminUsersPage,
  })),
)
const AdminPaymentsPage = lazy(() =>
  import('./features/admin/pages/AdminPages').then((module) => ({
    default: module.AdminPaymentsPage,
  })),
)
const AdminTtsPage = lazy(() =>
  import('./features/admin/pages/AdminPages').then((module) => ({
    default: module.AdminTtsPage,
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
const AdminImageLibraryPage = lazy(() =>
  import('./features/admin/pages/AdminImageLibraryPage').then((module) => ({
    default: module.AdminImageLibraryPage,
  })),
)
const MarketplacePublishDeckPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePublishPages').then((module) => ({
    default: module.MarketplacePublishDeckPage,
  })),
)
const MarketplacePublishNoteTypePage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePublishPages').then((module) => ({
    default: module.MarketplacePublishNoteTypePage,
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
const SupportPage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.SupportPage,
  })),
)
const TtsKeyGuidePage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.TtsKeyGuidePage,
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

function deferred(element: ReactNode) {
  return (
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
  )
}

const router = createBrowserRouter([
  {
    path: MAINTENANCE_PATH,
    element: <MaintenancePage />,
  },
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: 'login', element: deferred(<LoginPage />) },
      { path: 'register', element: deferred(<RegisterPage />) },
      { path: 'support', element: deferred(<SupportPage />) },
      {
        path: 'support-donation',
        element: <Navigate to="/support" replace />,
      },
      { path: 'guide/tts-key', element: deferred(<TtsKeyGuidePage />) },
      {
        path: 'guides/tts-key',
        element: <Navigate to="/guide/tts-key" replace />,
      },
      {
        path: 'help/tts-key',
        element: <Navigate to="/guide/tts-key" replace />,
      },
      { path: 'terms', element: deferred(<TermsPage />) },
      { path: 'privacy', element: deferred(<PrivacyPage />) },
      { path: 'cookies', element: deferred(<CookiesPage />) },
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
            path: 'flashcards/installed-decks',
            element: <Navigate to="/installed-decks" replace />,
          },
          {
            path: 'flashcards/import',
            element: deferred(<ImportPage />),
          },
          {
            path: 'import',
            element: deferred(<ImportPage />),
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
          { path: 'admin/users', element: deferred(<AdminUsersPage />) },
          {
            path: 'admin/payments',
            element: deferred(<AdminPaymentsPage />),
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
            path: 'admin/support',
            element: deferred(<AdminSupportConfigPage />),
          },
        ],
      },
      { path: 'home', element: <Navigate to="/dashboard" replace /> },
      { path: '*', element: <NotFoundPage /> },
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
