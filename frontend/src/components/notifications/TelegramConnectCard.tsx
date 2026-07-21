'use client'

import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Bell } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { buttonVariants } from '@/components/ui/button'

interface NotificationStatus {
  telegram_connected: boolean
  telegram_chat_id: number | null
}

export function TelegramConnectCard() {
  const [deepLink, setDeepLink] = useState<string | null>(null)
  const [pollingActive, setPollingActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const queryClient = useQueryClient()

  const { data: status, isLoading } = useQuery<NotificationStatus>({
    queryKey: ['notification-status'],
    queryFn: () => api.get<NotificationStatus>('/api/notifications/status'),
    refetchInterval: (query) => {
      if (!pollingActive) return false
      if (query.state.data?.telegram_connected) return false
      return 3000
    },
    staleTime: 0,
    retry: false,
  })

  const disconnectMutation = useMutation({
    mutationFn: () => api.delete('/api/notifications/telegram'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-status'] })
    },
    onError: (e: Error) => {
      setError(e.message)
    },
  })

  useEffect(() => {
    if (status?.telegram_connected && pollingActive) {
      setPollingActive(false)
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
      setDeepLink(null)
    }
  }, [status?.telegram_connected, pollingActive])

  async function handleConnectClick() {
    try {
      const result = await api.post<{ deep_link: string }>(
        '/api/notifications/telegram/link-token',
        {},
      )
      setDeepLink(result.deep_link)
      setPollingActive(true)
      timeoutRef.current = setTimeout(() => {
        setPollingActive(false)
        setDeepLink(null)
      }, 60_000)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <section aria-labelledby="telegram-connect-heading">
      <Card>
        <CardHeader>
          <CardTitle id="telegram-connect-heading" className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-primary" aria-hidden="true" />
            Telegram-уведомления
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading && (
            <p className="text-sm text-muted-foreground">Загрузка...</p>
          )}

          {!isLoading && status?.telegram_connected && (
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-green-600">Telegram подключён ✓</span>
              <button
                onClick={() => disconnectMutation.mutate()}
                disabled={disconnectMutation.isPending}
                className={cn(
                  buttonVariants({ variant: 'outline', size: 'sm' }),
                  'disabled:opacity-50',
                )}
              >
                {disconnectMutation.isPending ? 'Отключение...' : 'Отключить'}
              </button>
            </div>
          )}

          {!isLoading && !status?.telegram_connected && !deepLink && (
            <button
              onClick={handleConnectClick}
              className={cn(buttonVariants({ size: 'sm' }), 'disabled:opacity-50')}
            >
              Подключить Telegram
            </button>
          )}

          {!isLoading && !status?.telegram_connected && deepLink && (
            <div className="space-y-3">
              <a
                href={deepLink}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(buttonVariants({ size: 'sm' }), 'inline-flex')}
              >
                Открыть Telegram
              </a>
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-full bg-primary animate-pulse"
                  aria-hidden="true"
                />
                Ожидание подключения...
              </p>
            </div>
          )}

          {error && (
            <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-xs py-2">
              <div className="flex items-center justify-between gap-2">
                <span>{error}</span>
                <button
                  onClick={() => setError(null)}
                  className="text-xs underline shrink-0"
                >
                  Закрыть
                </button>
              </div>
            </Alert>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
