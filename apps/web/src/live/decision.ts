/**
 * The decision panel's keyboard flow as pure functions: a key becomes an intent, an intent moves
 * the Classify -> Assess -> Respond state, and a commit becomes one protocol command.
 * Keys: C A R open a step, 1-9 choose, Enter commits, Esc cancels, H holds fire,
 * U cues the EO sensor, L relabel, M merge, S split, D drop, X dismisses the rules verdict,
 * Tab / Shift+Tab cycle tracks, ? help.
 * Space is not used in this wave.
 */
import type { ClientAction, Welcome } from './protocol'

export type Step = 'classify' | 'assess' | 'respond'
export const STEPS: readonly Step[] = ['classify', 'assess', 'respond']

export type OptionKind = 'class' | 'identity' | 'engage' | 'report' | 'hold'

export interface Option {
  kind: OptionKind
  /** class id, identity, effector class id, or the action name for report and hold. */
  value: string
}

export interface Command {
  action: ClientAction
  payload: Record<string, unknown>
}

export interface DecisionState {
  step: Step | null
  /** Zero-based index of the chosen option, or null before one is chosen. */
  chosen: number | null
  /** A track waiting for the operator to confirm dropping it. */
  confirmDrop: string | null
}

export const initialDecision: DecisionState = { step: null, chosen: null, confirmDrop: null }

export type Intent =
  | { kind: 'cycle'; direction: 1 | -1 }
  | { kind: 'open'; step: Step }
  | { kind: 'choose'; n: number }
  | { kind: 'commit' }
  | { kind: 'cancel' }
  | { kind: 'hold' }
  | { kind: 'cue' }
  | { kind: 'relabel' }
  | { kind: 'merge' }
  | { kind: 'split' }
  | { kind: 'drop' }
  | { kind: 'help' }
  | { kind: 'dismiss' }

export interface KeyLike {
  key: string
  shiftKey?: boolean
  ctrlKey?: boolean
  metaKey?: boolean
  altKey?: boolean
}

/** Map a key press to an intent, or null when the key is not ours. Space is deliberately unmapped. */
export function keyToIntent(event: KeyLike): Intent | null {
  if (event.ctrlKey || event.metaKey || event.altKey) return null
  const key = event.key
  if (key === 'Tab') return { kind: 'cycle', direction: event.shiftKey ? -1 : 1 }
  if (key === 'Enter') return { kind: 'commit' }
  if (key === 'Escape') return { kind: 'cancel' }
  if (key === '?') return { kind: 'help' }
  if (/^[1-9]$/.test(key)) return { kind: 'choose', n: Number(key) }
  switch (key.toLowerCase()) {
    case 'c':
      return { kind: 'open', step: 'classify' }
    case 'a':
      return { kind: 'open', step: 'assess' }
    case 'r':
      return { kind: 'open', step: 'respond' }
    case 'h':
      return { kind: 'hold' }
    case 'u':
      return { kind: 'cue' }
    case 'l':
      return { kind: 'relabel' }
    case 'm':
      return { kind: 'merge' }
    case 's':
      return { kind: 'split' }
    case 'd':
      return { kind: 'drop' }
    case 'x':
      return { kind: 'dismiss' }
    default:
      return null
  }
}

/** The options of a step, from the welcome vocabularies and the rule pack's effector classes. */
export function stepOptions(step: Step, welcome: Welcome): Option[] {
  switch (step) {
    case 'classify':
      return welcome.operator_classes.map((value) => ({ kind: 'class', value }))
    case 'assess':
      return welcome.identities.map((value) => ({ kind: 'identity', value }))
    case 'respond': {
      const options: Option[] = welcome.rules.effector_classes.map((e) => ({
        kind: 'engage' as const,
        value: e.id,
      }))
      if (welcome.actions.includes('report')) options.push({ kind: 'report', value: 'report' })
      options.push({ kind: 'hold', value: 'hold' })
      return options
    }
  }
}

export function commandFor(option: Option, track: string): Command {
  switch (option.kind) {
    case 'class':
      return { action: 'classify', payload: { track, class_id: option.value } }
    case 'identity':
      return { action: 'assess', payload: { track, identity: option.value } }
    case 'engage':
      return { action: 'engage', payload: { track, effector_class: option.value } }
    case 'report':
      return { action: 'report', payload: { track } }
    case 'hold':
      return { action: 'hold', payload: { track } }
  }
}

export interface DecisionContext {
  welcome: Welcome
  /** The selected track, or null. */
  track: string | null
}

export interface DecisionResult {
  state: DecisionState
  command: Command | null
}

const nextStep = (step: Step): Step | null => STEPS[STEPS.indexOf(step) + 1] ?? null

/**
 * Apply an intent to the decision state. Commands for the track-management keys (cue, split,
 * drop, hold) are produced here too, so the whole keyboard contract is testable without a DOM.
 * Relabel, merge and help need UI (a text field, a second selection, a dialog) and are left to the
 * caller. Without a selected track, only help and cancel do anything.
 */
export function decide(
  state: DecisionState,
  intent: Intent,
  ctx: DecisionContext,
  eoSensor: string | null,
): DecisionResult {
  const keep: DecisionResult = { state, command: null }
  const { track } = ctx
  switch (intent.kind) {
    case 'cancel':
      return { state: initialDecision, command: null }
    case 'open':
      if (!track) return keep
      return { state: { step: intent.step, chosen: null, confirmDrop: null }, command: null }
    case 'choose': {
      if (state.confirmDrop || !state.step) return keep
      const options = stepOptions(state.step, ctx.welcome)
      if (intent.n > options.length) return keep
      return { state: { ...state, chosen: intent.n - 1 }, command: null }
    }
    case 'commit': {
      if (state.confirmDrop) {
        return {
          state: initialDecision,
          command: { action: 'track-drop', payload: { track: state.confirmDrop } },
        }
      }
      if (!track || !state.step || state.chosen === null) return keep
      const option = stepOptions(state.step, ctx.welcome)[state.chosen]
      if (!option) return keep
      const following = nextStep(state.step)
      return {
        // Classify and Assess lead on to the next step; Respond closes the panel.
        state: following ? { step: following, chosen: null, confirmDrop: null } : initialDecision,
        command: commandFor(option, track),
      }
    }
    case 'hold':
      if (!track) return keep
      return { state: initialDecision, command: { action: 'hold', payload: { track } } }
    case 'cue':
      if (!track || !eoSensor) return keep
      return {
        state,
        command: { action: 'sensor-cue', payload: { sensor: eoSensor, track, narrow: true } },
      }
    case 'split':
      if (!track) return keep
      return { state, command: { action: 'track-split', payload: { track } } }
    case 'drop':
      if (!track) return keep
      return { state: { step: null, chosen: null, confirmDrop: track }, command: null }
    default:
      return keep
  }
}
