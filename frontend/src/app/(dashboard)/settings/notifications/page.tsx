'use client'

import { TelegramConnectCard } from '@/components/notifications/TelegramConnectCard'
import { WatchlistSettingsTable } from '@/components/notifications/WatchlistSettingsTable'

export default function NotificationsSettingsPage() {
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Настройки уведомлений</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Подключите Telegram для получения уведомлений о тендерах
        </p>
      </div>
      <TelegramConnectCard />
      <WatchlistSettingsTable />
    </div>
  )
}
