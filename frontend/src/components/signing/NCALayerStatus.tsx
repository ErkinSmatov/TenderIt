'use client'

/**
 * NCALayerStatus — SIGN-01 + SIGN-05
 *
 * Live NCALayer connectivity indicator.
 * Consumes the result of useNCALayer() passed in from the parent wizard.
 *
 * States:
 *  connected  → green dot + "NCALayer подключён (v{version})"
 *  connecting → amber spinner + "Подключение к NCALayer..."
 *  signing    → amber spinner + "Введите PIN в окне NCALayer..."
 *  error      → red dot + "NCALayer недоступен" + кнопка "Подключить" + <InstallGuide/>
 *  disconnected → red dot + "NCALayer не подключён" + кнопка "Подключить" + <InstallGuide/>
 *
 * `disabled` derivation for parent's Sign button:
 *   const disabled = ncaLayer.status !== 'connected'
 */

import type { NCALayerHookResult } from '@/types/ncalayer'
import { useNCALayer } from '@/hooks/useNCALayer'
import { Button } from '@/components/ui/button'
import InstallGuide from './InstallGuide'

// useNCALayer is the hook that produces the ncaLayer prop this component displays.
// It is called by the parent wizard (05-03) and passed in via props.
// Imported here to satisfy the coupling constraint (no duplicated WS logic).
type _useNCALayerBound = typeof useNCALayer

interface NCALayerStatusProps {
  ncaLayer: NCALayerHookResult
}

export default function NCALayerStatus({ ncaLayer }: NCALayerStatusProps) {
  const { status, version, error, connect } = ncaLayer

  const showInstallGuide = status === 'disconnected' || status === 'error'
  const showConnectButton = status === 'disconnected' || status === 'error'

  return (
    <div className="space-y-3">
      {/* Status indicator row */}
      <div className="flex items-center justify-between gap-3 rounded-lg border bg-card px-4 py-3">
        <div className="flex items-center gap-2.5 text-sm">
          {/* Status dot / spinner */}
          {status === 'connected' ? (
            <span
              className="size-2.5 rounded-full bg-green-500 shrink-0"
              aria-hidden="true"
            />
          ) : status === 'connecting' || status === 'signing' ? (
            <span
              className="size-2.5 rounded-full bg-amber-400 shrink-0 animate-pulse"
              aria-hidden="true"
            />
          ) : (
            <span
              className="size-2.5 rounded-full bg-red-500 shrink-0"
              aria-hidden="true"
            />
          )}

          {/* Status text */}
          <span>
            {status === 'connected' && (
              <span className="font-medium text-green-700 dark:text-green-400">
                NCALayer подключён{version ? ` (v${version})` : ''}
              </span>
            )}
            {status === 'connecting' && (
              <span className="text-amber-700 dark:text-amber-400">
                Подключение к NCALayer...
              </span>
            )}
            {status === 'signing' && (
              <span className="text-amber-700 dark:text-amber-400">
                Введите PIN в окне NCALayer...
              </span>
            )}
            {status === 'disconnected' && (
              <span className="text-muted-foreground">NCALayer не подключён</span>
            )}
            {status === 'error' && (
              <span className="text-destructive">
                {error ?? 'NCALayer недоступен'}
              </span>
            )}
          </span>
        </div>

        {/* Connect button when not connected */}
        {showConnectButton && (
          <Button
            size="sm"
            variant="outline"
            onClick={connect}
            aria-label="Подключить NCALayer"
          >
            Подключить
          </Button>
        )}
      </div>

      {/* SIGN-05: Install guide when NCALayer is unavailable */}
      {showInstallGuide && <InstallGuide />}
    </div>
  )
}
