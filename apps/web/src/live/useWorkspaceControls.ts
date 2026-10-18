import { useCallback, useEffect, useState } from 'react'
import { decide, initialDecision, keyToIntent, type DecisionState, type Intent } from './decision'
import type { LiveSession } from './session'
import { useLatest } from './useLatest'

export const STAGE_ID = 'workspace-stage'

export interface WorkspaceControls {
  decision: DecisionState
  /** A track whose label the operator is editing, or null. */
  relabelFor: string | null
  setRelabelFor: (track: string | null) => void
  /** A track whose contact report the operator is filling in, or null. */
  reportFor: string | null
  setReportFor: (track: string | null) => void
  run: (intent: Intent) => void
  /** Choose an option by index (mouse), as the digit keys do. */
  choose: (index: number) => void
}

function inTextField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return (
    target.isContentEditable ||
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.tagName === 'SELECT'
  )
}

/**
 * Wires the decision panel's keys to the session. Tab and Shift+Tab step through the tracks
 * only while no control has focus (focus on the page or the stage), and hand focus back to the
 * browser at either end of the list, so the keys never trap a keyboard user.
 */
export function useWorkspaceControls(
  session: LiveSession,
  options: { onHelp: () => void; enabled: boolean },
): WorkspaceControls {
  const [decision, setDecision] = useState<DecisionState>(initialDecision)
  const [relabelFor, setRelabelFor] = useState<string | null>(null)
  const [reportFor, setReportFor] = useState<string | null>(null)
  const decisionRef = useLatest(decision)
  const helpRef = useLatest(options.onHelp)

  const run = useCallback(
    (intent: Intent): boolean => {
      const state = session.store.getState()
      const welcome = state.welcome
      if (!welcome) return false
      const track = state.selected
      const eo =
        state.frame?.sensors.find(
          (s) => (s.modality === 'eo' || s.modality === 'ir') && s.supports_cue,
        )?.id ?? null
      switch (intent.kind) {
        case 'help':
          helpRef.current()
          return true
        case 'dismiss':
          session.store.dispatch({ type: 'dismiss-verdict' })
          return true
        case 'cycle': {
          const ids = (state.frame?.tracks ?? []).map((t) => t.id).sort()
          if (ids.length === 0) return false
          const at = track ? ids.indexOf(track) : -1
          const next =
            at === -1 ? (intent.direction === 1 ? 0 : ids.length - 1) : at + intent.direction
          // Past either end the key is left to the browser.
          if (next < 0 || next >= ids.length) return false
          session.store.dispatch({ type: 'select', id: ids[next] ?? null })
          setDecision((d) => ({ ...d, chosen: null }))
          return true
        }
        case 'relabel':
          if (!track) return false
          setRelabelFor(track)
          return true
        case 'merge': {
          if (!track) return false
          if (state.mergeFrom === null) {
            session.store.dispatch({ type: 'merge-from', id: track })
          } else if (state.mergeFrom === track) {
            session.store.dispatch({ type: 'merge-from', id: null })
          } else {
            session.act('track-merge', { tracks: [state.mergeFrom, track] })
            session.store.dispatch({ type: 'merge-from', id: null })
          }
          return true
        }
        case 'cancel': {
          if (state.mergeFrom !== null && decisionRef.current.step === null) {
            session.store.dispatch({ type: 'merge-from', id: null })
            return true
          }
          const result = decide(decisionRef.current, intent, { welcome, track }, eo)
          setDecision(result.state)
          return true
        }
        default: {
          const result = decide(decisionRef.current, intent, { welcome, track }, eo)
          const moved = result.state !== decisionRef.current
          setDecision(result.state)
          // "Report up the chain" opens the report form; the form sends the command.
          if (result.command?.action === 'report') {
            setReportFor(String(result.command.payload.track))
            return true
          }
          if (result.command) session.act(result.command.action, result.command.payload)
          return moved || result.command !== null
        }
      }
    },
    [session, decisionRef, helpRef],
  )

  const choose = useCallback((index: number) => void run({ kind: 'choose', n: index + 1 }), [run])

  useEffect(() => {
    if (!options.enabled) return
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.repeat) return
      if (document.querySelector('dialog[open]')) return
      if (inTextField(event.target)) return
      const intent = keyToIntent(event)
      if (!intent) return
      const target = event.target instanceof HTMLElement ? event.target : null
      const onPage = !target || target === document.body || target.id === STAGE_ID
      const onOption = !!target?.closest('[data-decision-option]')
      // Controls keep their own Tab and Enter; the stage owns them.
      if (intent.kind === 'cycle' && !onPage) return
      if (intent.kind === 'commit' && !onPage && !onOption) return
      if (intent.kind === 'cancel' && onPage && decisionRef.current.step === null) {
        // Nothing to cancel: an idle Escape puts focus back on the stage.
        document.getElementById(STAGE_ID)?.focus()
      }
      if (run(intent)) event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [options.enabled, run, decisionRef])

  return {
    decision,
    relabelFor,
    setRelabelFor,
    reportFor,
    setReportFor,
    run: (i) => void run(i),
    choose,
  }
}
