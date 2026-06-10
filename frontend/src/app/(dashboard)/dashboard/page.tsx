'use client'

import Link from 'next/link'
import { Search, Building2, ChevronRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import DashboardWatchlist from '@/components/tenders/DashboardWatchlist'

const quickActions = [
  {
    href: '/tenders',
    icon: Search,
    title: 'Поиск тендеров',
    description: 'Найдите тендер по номеру объявления',
  },
  {
    href: '/profile',
    icon: Building2,
    title: 'Профиль компании',
    description: 'БИН, наименование и юридический адрес',
  },
]

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Обзор</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Добро пожаловать в TenderIt
        </p>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {quickActions.map(({ href, icon: Icon, title, description }) => (
          <Link key={href} href={href} className="group block">
            <Card className="hover:ring-primary/40 transition-all">
              <CardContent className="flex items-center gap-4 py-4">
                <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">
                    {description}
                  </p>
                </div>
                <ChevronRight
                  className="h-4 w-4 text-muted-foreground shrink-0 group-hover:text-primary transition-colors"
                  aria-hidden="true"
                />
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Watchlist */}
      <DashboardWatchlist />
    </div>
  )
}
