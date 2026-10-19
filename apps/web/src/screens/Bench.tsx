import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { assemble, collectDevice, type BenchResult } from '../bench/device'
import {
  BENCH_HOUR,
  BENCH_PACK,
  BenchRunner,
  CANVAS,
  benchReports,
  cameraBearing,
  loadBenchScene,
  type BenchScene,
  quickPhases,
  PHASES,
  type PhaseId,
  type PhaseResult,
  type PhaseSpec,
} from '../bench/plan'
import { PageHeader } from '../layout/PageHeader'
import { useVersion } from '../lib/version'
import { qualityStore } from '../live/qualityStore'
import type { Tier, TierChoice } from '../live/quality'
import { heightAt } from '../live/terrain/heightAt'
import { loadTerrainPack } from '../live/terrain/loader'
import { EoScene } from '../live/views/eoScene'
import { webglAvailable } from '../live/views/webgl'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { EmptyState } from '../ui/States'
import { Table, type Column } from '../ui/Table'

type Phase =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'running'; phase: PhaseId; index: number; total: number }
  | { status: 'done'; result: BenchResult }
  | { status: 'error'; message: string }

/**
 * The benchmark harness (docs/04-engine.md): plays the reference scene through the real scene
 * code at 1080p for each quality tier and for the automatic controller, then shows the frame-rate
 * percentiles and lets the operator save them as JSON. A demo-mode route; it reads no session.
 */
export function Bench() {
  const { t } = useTranslation()
  const version = useVersion()
  const holder = useRef<HTMLDivElement>(null)
  const stop = useRef<(() => void) | null>(null)
  const [state, setState] = useState<Phase>({ status: 'idle' })
  const [webgl] = useState(() => webglAvailable())
  const [snapshot, setSnapshot] = useState<string | null>(null)

  useEffect(() => () => stop.current?.(), [])

  const run = useCallback(async () => {
    const wrap = holder.current
    if (!wrap) return
    setState({ status: 'loading' })
    setSnapshot(null)
    let pack
    let swarmScene: BenchScene
    try {
      ;[pack, swarmScene] = await Promise.all([loadTerrainPack(BENCH_PACK), loadBenchScene()])
    } catch (error) {
      setState({ status: 'error', message: error instanceof Error ? error.message : String(error) })
      return
    }
    // A fresh canvas per run: a context lost on teardown cannot be reused.
    const el = document.createElement('canvas')
    el.setAttribute('aria-hidden', 'true')
    el.className = 'block aspect-video w-full bg-surface-2'
    wrap.replaceChildren(el)
    let scene: EoScene
    try {
      scene = new EoScene(el, { tier: 'high', fixedPixelRatio: 1 })
    } catch {
      el.remove()
      setState({ status: 'error', message: t('bench.noWebgl') })
      return
    }
    const previousChoice: TierChoice = qualityStore.getState().choice
    scene.resize(CANVAS.width, CANVAS.height)
    scene.setWeather({})
    scene.setTimeOfDay(BENCH_HOUR)
    await scene.setTerrain(pack)
    const eye = { x: 0, y: 0, z: heightAt(pack, 0, 0) + 30 }
    let tier: Tier = 'high'
    const phases = new URLSearchParams(window.location.search).has('quick') ? quickPhases() : PHASES
    let interrupted = false
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') interrupted = true
    }
    document.addEventListener('visibilitychange', onVisibility)
    const runner = new BenchRunner(
      {
        begin: (spec: PhaseSpec) => {
          scene.setMode(spec.mode)
          if (spec.tier === null) {
            qualityStore.setChoice('auto')
            tier = qualityStore.getState().tier
          } else {
            tier = spec.tier
          }
          scene.setQuality(tier)
        },
        draw: (now, timeS) => {
          scene.update({
            position: eye,
            bearingDeg: cameraBearing(swarmScene, timeS, eye),
            elevationDeg: -1,
            fovDeg: 40,
            reports: benchReports(swarmScene, timeS, now, eye),
            nowMs: now,
          })
          scene.render(now)
        },
        autoFrame: (now) => {
          const event = qualityStore.frame(now)
          if (event) {
            tier = event.tier
            scene.setQuality(tier)
          }
          return event ? event.tier : null
        },
        tier: () => tier,
        interrupted: () => {
          const was = interrupted
          interrupted = false
          return was
        },
      },
      phases,
    )

    const startedAt = new Date().toISOString()
    let raf = 0
    let live = true
    const finish = (phases: PhaseResult[]) => {
      const info = version.state.status === 'ready' ? version.state.info : null
      const gl = scene.renderer.getContext()
      const result = assemble({
        startedAt,
        build: info ? { version: info.version, gitSha: info.gitSha, env: info.env } : null,
        device: collectDevice(gl),
        pack: {
          id: pack.id,
          version: pack.version,
          buildings: pack.buildings.length,
          trees: pack.trees.length / 3,
        },
        pixelRatio: scene.renderer.getPixelRatio(),
        stats: scene.stats(),
        phases,
      })
      // The last frame is still in the drawing buffer in this task; keep it as the preview.
      const preview = (() => {
        try {
          return el.toDataURL('image/jpeg', 0.85)
        } catch {
          return null
        }
      })()
      teardown()
      el.remove()
      setSnapshot(preview)
      setState({ status: 'done', result })
    }
    const teardown = () => {
      document.removeEventListener('visibilitychange', onVisibility)
      live = false
      cancelAnimationFrame(raf)
      qualityStore.setChoice(previousChoice)
      scene.dispose()
      stop.current = null
    }
    stop.current = () => {
      if (live) teardown()
    }
    const loop = (now: number) => {
      if (!live) return
      const s = runner.step(now)
      if (s.status === 'done') {
        finish(s.phases)
        return
      }
      setState((prev) =>
        prev.status === 'running' && prev.phase === s.phase
          ? prev
          : { status: 'running', phase: s.phase, index: s.index, total: s.total },
      )
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
  }, [t, version.state])

  const cancel = () => {
    stop.current?.()
    holder.current?.replaceChildren()
    setState({ status: 'idle' })
  }

  const download = (result: BenchResult) => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `bench-${result.startedAt.replace(/[:.]/g, '-')}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const busy = state.status === 'loading' || state.status === 'running'
  return (
    <>
      <PageHeader
        title={t('bench.title')}
        crumbs={['dev']}
        actions={
          <div className="flex gap-2">
            {busy ? (
              <Button onClick={cancel}>{t('bench.cancel')}</Button>
            ) : (
              <Button variant="primary" onClick={() => void run()} disabled={!webgl}>
                {state.status === 'done' ? t('bench.runAgain') : t('bench.run')}
              </Button>
            )}
            {state.status === 'done' && (
              <Button onClick={() => download(state.result)}>{t('bench.download')}</Button>
            )}
          </div>
        }
      />
      <div className="flex flex-col gap-4">
        {!webgl && <InlineAlert tone="warning">{t('bench.noWebgl')}</InlineAlert>}
        {state.status === 'error' && <InlineAlert tone="error">{state.message}</InlineAlert>}
        <div
          role="status"
          aria-live="polite"
          data-testid="bench-status"
          className="num text-sm text-ink-2"
        >
          {state.status === 'idle' && t('bench.idle')}
          {state.status === 'loading' && t('bench.loading')}
          {state.status === 'running' &&
            t('bench.running', {
              phase: t(`bench.phase.${state.phase}`),
              index: state.index + 1,
              total: state.total,
            })}
          {state.status === 'done' && t('bench.done')}
        </div>
        <Panel title={t('bench.scene')} flush>
          <div
            ref={holder}
            aria-hidden="true"
            className={`aspect-video w-full bg-surface-2 ${snapshot ? 'hidden' : ''}`}
          />
          {snapshot && (
            <img
              src={snapshot}
              alt={t('bench.canvas')}
              className="block aspect-video w-full bg-surface-2"
            />
          )}
        </Panel>
        {state.status === 'idle' && (
          <EmptyState title={t('bench.emptyTitle')} description={t('bench.emptyBody')} />
        )}
        {state.status === 'done' && <Results result={state.result} />}
      </div>
    </>
  )
}

function Results({ result }: { result: BenchResult }) {
  const { t } = useTranslation()
  const gate = result.gate
  const verdict = gate.pass === null ? 'unknown' : gate.pass ? 'pass' : 'fail'
  const columns: Column<PhaseResult>[] = [
    { key: 'phase', header: t('bench.col.phase'), render: (p) => t(`bench.phase.${p.id}`) },
    { key: 'mode', header: t('bench.col.mode'), render: (p) => t(`bench.mode.${p.mode}`) },
    { key: 'tier', header: t('bench.col.tier'), render: (p) => t(`bench.tier.${p.tier}`) },
    {
      key: 'median',
      header: t('bench.col.median'),
      render: (p) => p.fpsMedian.toFixed(1),
      align: 'right',
      mono: true,
    },
    {
      key: 'p5',
      header: t('bench.col.p5'),
      render: (p) => p.fps5th.toFixed(1),
      align: 'right',
      mono: true,
    },
    {
      key: 'p99',
      header: t('bench.col.p99'),
      render: (p) => p.p99Ms.toFixed(1),
      align: 'right',
      mono: true,
    },
    {
      key: 'frames',
      header: t('bench.col.frames'),
      render: (p) => p.frames,
      align: 'right',
      mono: true,
    },
    {
      key: 'slow',
      header: t('bench.col.slow'),
      render: (p) => p.slowFrames,
      align: 'right',
      mono: true,
    },
  ]
  const d = result.device
  return (
    <>
      <Panel
        title={t('bench.gate')}
        actions={
          <Badge tone={verdict === 'pass' ? 'accent' : verdict === 'fail' ? 'hostile' : 'neutral'}>
            {t(`bench.verdict.${verdict}`)}
          </Badge>
        }
      >
        <p className="m-0 text-sm text-ink-2">{t('bench.gateBody')}</p>
        <dl className="num m-0 mt-2 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-ink-2">{t('bench.fixedHigh')}</dt>
          <dd className="m-0">
            {gate.fixedHigh === null ? '-' : t(gate.fixedHigh ? 'bench.met' : 'bench.notMet')}
          </dd>
          <dt className="text-ink-2">{t('bench.autoHolds')}</dt>
          <dd className="m-0">
            {gate.autoHolds === null ? '-' : t(gate.autoHolds ? 'bench.met' : 'bench.notMet')}
          </dd>
        </dl>
      </Panel>
      <Panel title={t('bench.results')} flush>
        <Table
          caption={t('bench.results')}
          columns={columns}
          rows={result.phases}
          rowKey={(p) => p.id}
          dense
        />
      </Panel>
      <Panel title={t('bench.device')}>
        <dl className="num m-0 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-ink-2">{t('bench.gpu')}</dt>
          <dd className="m-0">{d.webgl.renderer ?? t('bench.unknown')}</dd>
          <dt className="text-ink-2">{t('bench.cpuCores')}</dt>
          <dd className="m-0">{d.hardwareConcurrency ?? t('bench.unknown')}</dd>
          <dt className="text-ink-2">{t('bench.memory')}</dt>
          <dd className="m-0">
            {d.deviceMemoryGb === null ? t('bench.unknown') : `${d.deviceMemoryGb} GB`}
          </dd>
          <dt className="text-ink-2">{t('bench.display')}</dt>
          <dd className="m-0">{`${d.screen.width} x ${d.screen.height} @ ${d.devicePixelRatio}`}</dd>
        </dl>
        <p className="m-0 mt-2 text-xs text-ink-2">{t('bench.notes')}</p>
      </Panel>
    </>
  )
}
