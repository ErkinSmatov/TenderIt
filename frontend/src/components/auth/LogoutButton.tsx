'use client'

import { useRouter } from 'next/navigation'

import { api } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

export default function LogoutButton() {
  const router = useRouter()

  async function onLogout() {
    try {
      await api.post('/api/auth/logout', {})
    } catch {
      // Server may have already invalidated the session — clear local state regardless
    }
    useAuthStore.getState().clearAuth()
    router.push('/login')
  }

  return <button onClick={onLogout}>Выйти</button>
}
