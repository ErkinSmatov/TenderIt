'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import CompanyProfileForm from '@/components/profile/CompanyProfileForm'

interface CompanyProfileData {
  bin: string | null
  company_name: string | null
  legal_address: string | null
  updated_at: string | null
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<CompanyProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    api.get<CompanyProfileData>('/api/company/profile')
      .then((data) => {
        setProfile(data)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Ошибка загрузки профиля')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-6">
        <Link href="/dashboard" className="text-blue-600 text-sm hover:underline">
          ← Личный кабинет
        </Link>
      </div>

      <h1 className="text-2xl font-bold mb-6">Профиль компании</h1>

      {loading && <p className="text-gray-500">Загрузка...</p>}

      {error && <p className="text-red-500">{error}</p>}

      {!loading && !error && profile && (
        <CompanyProfileForm initialData={profile} />
      )}
    </div>
  )
}
