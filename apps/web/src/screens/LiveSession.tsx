import { Play } from '@carbon/icons-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { Shell } from '../layout/Shell'
import { LiveProvider, useLive, useLiveSession } from '../live/context'
import { createTransport } from '../live/createTransport'
import { fmtElapsed, useLang } from '../live/format'
import { CLOSE } from '../live/protocol'
import { LiveSession } from '../live/session'
import { DecisionPanel } from '../live/panels/DecisionPanel'
import { EndDialog, RelabelDialog, ShortcutsDialog } from '../live/panels/Dialogs'
import { EventLog } from '../live/panels/EventLog'
import { SensorStatus } from '../live/panels/SensorStatus'
import { TopBar } from '../live/panels/TopBar'
import { TrackDetail } from '../live/panels/TrackDetail'
import { TrackTable } from '../live/panels/TrackTable'
import { VerdictPanel } from '../live/panels/VerdictPanel'
import { STAGE_ID, useWorkspaceControls } from '../live/useWorkspaceControls'
import { EoView } from '../live/views/EoView'
import { PpiView, ppiRangeMax } from '../live/views/PpiView'
import { localised } from '../live/restApi'
import { Button } from '../ui/Button'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { Segmented } from '../ui/Segmented'
import { ErrorState, LoadingState } from '../ui/States'
import { SessionEnded } from './SessionEnded'

/** Route /train/session/:id: opens the transport, then shows the workspace or why it cannot. */
export function LiveSessionPage() {
  const { id = '' } = useParams()
  const [session, setSession] = useState<LiveSession | null>(null)

  useEffect(() => {
    let cancelled = false
    let created: LiveSession | null = null
    void createTransport(id).then((transport) => {
      if (cancelled) return
      created = new LiveSession(transport)
      created.connect()
      setSession(created)
    })
    return () => {
      cancelled = true
      created?.leave()
      created?.dispose()
    }
  }, [id])

  if (!session) {
    return <LoadingScreen />
  }
  return (
    <LiveProvider session={session}>
      <SessionGate id={id} />
    </LiveProvider>
  )
}

function LoadingScreen() {
  const { t } = useTranslation()
  return (
    <div className="flex h-screen items-center justify-center bg-bg">
      <LoadingState label={t('live.state.connecting')} />
    </div>
  )
}

/** Failure screens inside the normal frame, for a session that never opened. */
function FailureScreen({ code, onRetry }: { code: number | null; onRetry: () => void }) {
  const { t } = useTranslation()
  const key =
    code === CLOSE.notSignedIn
      ? 'notSignedIn'
      : code === CLOSE.forbidden
        ? 'forbidden'
        : code === CLOSE.notFound
          ? 'notFound'
          : code === CLOSE.superseded
            ? 'superseded'
            : code === CLOSE.full
              ? 'full'
              : code === CLOSE.tooLarge
                ? 'tooLarge'
                : 'closed'
  return (
    <Shell>
      <div className="max-w-[640px]" data-testid="session-failure" data-code={code ?? ''}>
        <ErrorState
          offline
          title={t(`live.fail.${key}.title`)}
          description={t(`live.fail.${key}.body`, { code: code ?? '—' })}
          retryLabel={t('live.fail.retry')}
          onRetry={onRetry}
        />
        <p className="mt-4">
          <Link to="/train/lobby">{t('live.ended.back')}</Link>
        </p>
      </div>
    </Shell>
  )
}

function SessionGate({ id }: { id: string }) {
  const welcome = useLive((s) => s.welcome)
  const connection = useLive((s) => s.connection)
  const ended = useLive((s) => s.ended)
  const status = useLive((s) => s.status)
  const { t } = useTranslation()

  // The server refuses a finished session with 4409: its log is still readable.
  if (ended || connection.closeCode === CLOSE.ended || status === 'ended') {
    return (
      <Shell>
        <SessionEnded id={id} summary={ended} />
      </Shell>
    )
  }
  if (!welcome) {
    if (connection.state === 'closed') {
      return <FailureScreen code={connection.closeCode} onRetry={() => window.location.reload()} />
    }
    return (
      <div className="flex h-screen items-center justify-center bg-bg">
        <LoadingState
          label={
            connection.state === 'reconnecting'
              ? t('live.state.reconnecting', { attempt: connection.attempt })
              : t('live.state.connecting')
          }
        />
      </div>
    )
  }
  return <Workspace />
}

function Workspace() {
  const { t } = useTranslation()
  const lang = useLang()
  const session = useLiveSession()
  const welcome = useLive((s) => s.welcome)
  const connection = useLive((s) => s.connection)
  const status = useLive((s) => s.status)
  const selected = useLive((s) => s.selected)
  const frame = useLive((s) => s.frame)
  const [help, setHelp] = useState(false)
  const [confirmEnd, setConfirmEnd] = useState(false)
  const controls = useWorkspaceControls(session, {
    onHelp: () => setHelp(true),
    enabled: true,
  })

  if (!welcome) return null
  const briefing = welcome.briefing
  const eo = frame?.sensors.find((s) => s.modality === 'eo') ?? null
  const eoId = eo?.id ?? briefing.sensors.find((s) => s.modality === 'eo')?.id ?? null
  const track = frame?.tracks.find((x) => x.id === selected)
  const reconnecting =
    connection.state === 'reconnecting' || (connection.state === 'closed' && status !== 'ended')

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-bg text-ink">
      <a
        href={`#${STAGE_ID}`}
        className="absolute left-2 top-2 z-30 -translate-y-12 bg-surface-2 px-3 py-2 text-sm focus:translate-y-0"
      >
        {t('app.skip')}
      </a>
      <TopBar onHelp={() => setHelp(true)} onEnd={() => setConfirmEnd(true)} />
      {reconnecting && (
        <div className="shrink-0 border-b border-line bg-surface-1 px-3 py-1">
          <InlineAlert tone="warning">
            {connection.state === 'closed'
              ? t('live.banner.closed', { code: connection.closeCode ?? '—' })
              : t('live.banner.reconnecting', { attempt: connection.attempt })}
          </InlineAlert>
        </div>
      )}
      <main
        id={STAGE_ID}
        tabIndex={-1}
        aria-label={t('live.workspace.title')}
        className="grid min-h-0 flex-1 grid-cols-12 grid-rows-[minmax(0,1fr)_auto] gap-px bg-line outline-offset-[-2px]"
      >
        <Panel
          title={eoId ? t('live.eo.title', { sensor: eoId }) : t('live.eo.titlePlain')}
          className="col-span-7 flex min-h-0 flex-col"
          bodyClassName="relative min-h-0 flex-1"
          flush
          actions={
            <div className="flex items-center gap-2">
              <Segmented
                label={t('live.eo.mode')}
                value="tv"
                options={[{ value: 'tv', label: t('live.eo.modeTv') }]}
                onChange={() => undefined}
              />
              <Button
                disabled={!track || !eo?.supports_cue || status !== 'running'}
                onClick={() => controls.run({ kind: 'cue' })}
              >
                {t('live.eo.cue')} <kbd className="num text-2xs">U</kbd>
              </Button>
              <Button
                disabled={!track || !eo?.supports_cue || status !== 'running'}
                onClick={() => {
                  if (track && eo)
                    session.act('sensor-cue', { sensor: eo.id, track: track.id, narrow: false })
                }}
              >
                {t('live.eo.slew')}
              </Button>
            </div>
          }
        >
          <EoView sensorId={eoId} />
          {status === 'lobby' && <ReadyCard />}
        </Panel>

        <div className="col-span-5 flex min-h-0 flex-col gap-px">
          <Panel
            title={t('live.ppi.title')}
            className="flex h-[50%] min-h-0 shrink-0 flex-col"
            bodyClassName="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_168px] gap-px bg-line"
            flush
            actions={
              <span className="num text-xs text-ink-2">
                {t('live.ppi.scale', {
                  range: (ppiRangeMax(briefing) / 1000).toFixed(1),
                  period: '1.2',
                })}
              </span>
            }
          >
            <PpiView lang={lang} />
            <div className="min-h-0 bg-surface-1">
              <SensorStatus />
            </div>
          </Panel>
          <Panel
            title={t('live.table.title')}
            className="flex min-h-0 flex-1 flex-col"
            bodyClassName="flex min-h-0 flex-1 flex-col"
            flush
          >
            <TrackTable />
          </Panel>
        </div>

        <div className="col-span-12 grid h-[clamp(208px,28vh,300px)] grid-cols-12 gap-px bg-line">
          <Panel
            title={t('live.detail.title')}
            className="col-span-3 flex min-h-0 flex-col"
            bodyClassName="min-h-0 flex-1 overflow-hidden"
            flush
          >
            <TrackDetail welcome={welcome} />
          </Panel>
          <Panel
            title={t('live.decision.title')}
            className="col-span-5 flex min-h-0 flex-col"
            bodyClassName="min-h-0 flex-1"
            flush
          >
            <DecisionPanel welcome={welcome} controls={controls} />
          </Panel>
          <div className="col-span-4 flex min-h-0 flex-col gap-px">
            <Panel
              title={t('live.verdict.title')}
              className="flex min-h-0 flex-[3] flex-col"
              bodyClassName="min-h-0 flex-1"
              flush
            >
              <VerdictPanel welcome={welcome} />
            </Panel>
            <Panel
              title={t('live.log.title')}
              className="flex min-h-0 flex-[2] flex-col"
              bodyClassName="min-h-0 flex-1"
              flush
            >
              <EventLog />
            </Panel>
          </div>
        </div>
      </main>

      <ShortcutsDialog open={help} onClose={() => setHelp(false)} />
      <EndDialog
        open={confirmEnd}
        onClose={() => setConfirmEnd(false)}
        onConfirm={() => {
          setConfirmEnd(false)
          session.end()
        }}
      />
      <RelabelDialog
        track={controls.relabelFor}
        current={frame?.tracks.find((x) => x.id === controls.relabelFor)?.label ?? ''}
        onClose={() => controls.setRelabelFor(null)}
        onSubmit={(label, exchange) => {
          if (controls.relabelFor)
            session.act('track-relabel', {
              track: controls.relabelFor,
              label,
              ...(exchange ? { exchange: true } : {}),
            })
          controls.setRelabelFor(null)
        }}
      />
    </div>
  )
}

/** Before `start`: the briefing in brief, and the one button that begins the session. */
function ReadyCard() {
  const { t } = useTranslation()
  const lang = useLang()
  const session = useLiveSession()
  const welcome = useLive((s) => s.welcome)
  if (!welcome) return null
  const b = welcome.briefing
  return (
    <section
      aria-labelledby="ready-h"
      className="absolute bottom-4 left-4 z-10 w-[420px] max-w-[calc(100%-32px)] border border-line bg-surface-1 p-4"
    >
      <h3 id="ready-h" className="m-0 text-md font-semibold">
        {localised(b.title, lang)}
      </h3>
      <p className="mb-3 mt-1 text-sm text-ink-2">{localised(b.summary, lang)}</p>
      <p className="num m-0 mb-3 text-xs text-ink-2">
        {t('live.ready.facts', {
          duration: fmtElapsed(b.duration_s),
          rules: `${welcome.rules.id} ${welcome.rules.version}`,
        })}
      </p>
      <Button variant="primary" autoFocus onClick={() => session.start()}>
        <Play size={16} aria-hidden="true" />
        {t('live.ready.begin')}
      </Button>
    </section>
  )
}
