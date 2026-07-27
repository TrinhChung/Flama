import { lazy, Suspense, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { RequireAuth } from './features/auth/components/RequireAuth'
import { LandingPage } from './pages/LandingPage'
import { NotFoundPage } from './pages/NotFoundPage'

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
const SharedDecksPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePages').then((module) => ({
    default: module.SharedDecksPage,
  })),
)
const SharedNoteTypesPage = lazy(() =>
  import('./features/marketplace/pages/MarketplacePages').then((module) => ({
    default: module.SharedNoteTypesPage,
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
const SupportPage = lazy(() =>
  import('./pages/StaticPages').then((module) => ({
    default: module.SupportPage,
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
    element: <AppLayout />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: 'login', element: deferred(<LoginPage />) },
      { path: 'register', element: deferred(<RegisterPage />) },
      { path: 'support', element: deferred(<SupportPage />) },
      { path: 'terms', element: deferred(<TermsPage />) },
      { path: 'privacy', element: deferred(<PrivacyPage />) },
      { path: 'cookies', element: deferred(<CookiesPage />) },
      {
        element: <RequireAuth />,
        children: [
          { path: 'dashboard', element: deferred(<DashboardPage />) },
          { path: 'statistics', element: deferred(<StatisticsPage />) },
          { path: 'browse', element: deferred(<BrowsePage />) },
          { path: 'study', element: deferred(<StudyPage />) },
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
            path: 'marketplace/decks',
            element: deferred(<SharedDecksPage />),
          },
          {
            path: 'marketplace/note-types',
            element: deferred(<SharedNoteTypesPage />),
          },
          { path: 'orders', element: deferred(<OrdersPage />) },
          { path: 'admin/users', element: deferred(<AdminUsersPage />) },
          {
            path: 'admin/payments',
            element: deferred(<AdminPaymentsPage />),
          },
          { path: 'admin/tts', element: deferred(<AdminTtsPage />) },
        ],
      },
      { path: 'home', element: <Navigate to="/dashboard" replace /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
