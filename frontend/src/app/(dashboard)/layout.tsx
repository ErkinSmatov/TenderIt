import { ReactNode } from 'react'

import LogoutButton from '@/components/auth/LogoutButton'

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <span className="font-semibold text-lg">TenderIt</span>
        <LogoutButton />
      </header>
      <main className="p-6">{children}</main>
    </div>
  )
}
