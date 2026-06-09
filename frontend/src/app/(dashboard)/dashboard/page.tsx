'use client'

import Link from 'next/link'
import { useAuthStore } from '@/store/authStore'

export default function DashboardPage() {
  const userId = useAuthStore((state) => state.userId)

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Личный кабинет</h1>
      <p className="text-gray-600 mb-4">UserID: {userId ?? '—'}</p>
      <nav className="flex flex-col gap-2">
        <Link
          href="/profile"
          className="text-blue-600 hover:underline w-fit"
        >
          Профиль компании
        </Link>
      </nav>
    </div>
  )
}
