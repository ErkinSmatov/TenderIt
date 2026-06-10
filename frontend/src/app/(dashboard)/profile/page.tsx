'use client'

import { useEffect, useState } from 'react'
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
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Профиль компании</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Данные вашей организации для тендерных заявок
        </p>
      </div>

      {loading && (
        <p className="text-sm text-muted-foreground">Загрузка...</p>
      )}

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {!loading && !error && profile && (
        <CompanyProfileForm initialData={profile} />
      )}
    </div>
  )
}
