'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'

export default function Providers({ children }: { children: ReactNode }) {
  // Stable QueryClient per component instance (recommended pattern for Next.js App Router).
  // retry: false — don't retry on 404/4xx; staleTime: 60_000 — 1 min client-side freshness.
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, staleTime: 60_000 },
        },
      }),
  )

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
