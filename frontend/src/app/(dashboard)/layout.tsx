import { ReactNode } from 'react'

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <span className="font-semibold text-lg">TenderIt</span>
        {/* Logout link — POST /api/auth/logout endpoint arrives in wave 2 */}
        <a
          href="/api/auth/logout"
          className="text-sm text-gray-600 hover:text-gray-900 underline"
        >
          Выйти
        </a>
      </header>
      <main className="p-6">{children}</main>
    </div>
  )
}
