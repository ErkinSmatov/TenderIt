import { ReactNode } from 'react'
import Sidebar from '@/components/layout/Sidebar'
import Providers from './Providers'

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-4xl mx-auto">
          <Providers>{children}</Providers>
        </div>
      </main>
    </div>
  )
}
