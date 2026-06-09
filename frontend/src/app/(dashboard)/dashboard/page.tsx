'use client'

import { useAuthStore } from '@/store/authStore'

export default function DashboardPage() {
  const userId = useAuthStore((state) => state.userId)

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Личный кабинет</h1>
      <p className="text-gray-600">UserID: {userId ?? '—'}</p>
    </div>
  )
}
