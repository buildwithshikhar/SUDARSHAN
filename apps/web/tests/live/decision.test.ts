import { describe, expect, it } from 'vitest'
import {
  commandFor,
  decide,
  initialDecision,
  keyToIntent,
  stepOptions,
  type DecisionState,
  type Intent,
} from '../../src/live/decision'
import { welcome } from './helpers'

const w = welcome()
const ctx = { welcome: w, track: 'T014' }

/** Press keys in order through the pure flow; returns the commands issued and the final state. */
function press(keys: string[], track: string | null = 'T014', eo: string | null = 'eo-1') {
  let state: DecisionState = initialDecision
  const commands: unknown[] = []
  for (const key of keys) {
    const intent = keyToIntent({ key })
    if (!intent) continue
    const result = decide(state, intent, { welcome: w, track }, eo)
    state = result.state
    if (result.command) commands.push(result.command)
  }
  return { state, commands }
}

describe('key map', () => {
  it.each([
    ['c', { kind: 'open', step: 'classify' }],
    ['A', { kind: 'open', step: 'assess' }],
    ['r', { kind: 'open', step: 'respond' }],
    ['h', { kind: 'hold' }],
    ['u', { kind: 'cue' }],
    ['l', { kind: 'relabel' }],
    ['m', { kind: 'merge' }],
    ['s', { kind: 'split' }],
    ['d', { kind: 'drop' }],
    ['x', { kind: 'dismiss' }],
    ['?', { kind: 'help' }],
    ['Enter', { kind: 'commit' }],
    ['Escape', { kind: 'cancel' }],
    ['5', { kind: 'choose', n: 5 }],
  ] as [string, Intent][])('maps %s', (key, intent) => {
    expect(keyToIntent({ key })).toEqual(intent)
  })

  it('maps Tab and Shift+Tab to cycling and leaves Space, 0 and modified keys alone', () => {
    expect(keyToIntent({ key: 'Tab' })).toEqual({ kind: 'cycle', direction: 1 })
    expect(keyToIntent({ key: 'Tab', shiftKey: true })).toEqual({ kind: 'cycle', direction: -1 })
    expect(keyToIntent({ key: ' ' })).toBeNull()
    expect(keyToIntent({ key: '0' })).toBeNull()
    expect(keyToIntent({ key: 'c', ctrlKey: true })).toBeNull()
    expect(keyToIntent({ key: 'r', metaKey: true })).toBeNull()
  })
})

describe('options', () => {
  it('come from the welcome vocabularies and the rule pack effector classes', () => {
    expect(stepOptions('classify', w).map((o) => o.value)).toEqual(w.operator_classes)
    expect(stepOptions('assess', w).map((o) => o.value)).toEqual(w.identities)
    expect(stepOptions('respond', w)).toEqual([
      { kind: 'engage', value: 'ec-a' },
      { kind: 'engage', value: 'ec-b' },
      { kind: 'report', value: 'report' },
      { kind: 'hold', value: 'hold' },
    ])
  })

  it('leave out Report when the server does not offer it', () => {
    const noReport = { ...w, actions: w.actions.filter((a) => a !== 'report') }
    expect(stepOptions('respond', noReport).map((o) => o.kind)).toEqual([
      'engage',
      'engage',
      'hold',
    ])
  })

  it('turn into exactly one protocol command naming only a track', () => {
    expect(commandFor({ kind: 'class', value: 'bird' }, 'T1')).toEqual({
      action: 'classify',
      payload: { track: 'T1', class_id: 'bird' },
    })
    expect(commandFor({ kind: 'identity', value: 'hostile' }, 'T1')).toEqual({
      action: 'assess',
      payload: { track: 'T1', identity: 'hostile' },
    })
    expect(commandFor({ kind: 'engage', value: 'ec-b' }, 'T1')).toEqual({
      action: 'engage',
      payload: { track: 'T1', effector_class: 'ec-b' },
    })
    expect(commandFor({ kind: 'report', value: 'report' }, 'T1').payload).toEqual({ track: 'T1' })
    expect(commandFor({ kind: 'hold', value: 'hold' }, 'T1').payload).toEqual({ track: 'T1' })
  })
})

describe('Classify, Assess, Respond from the keyboard', () => {
  it('walks the three steps, each committed with Enter, and issues three commands', () => {
    const { commands, state } = press(['c', '1', 'Enter', '1', 'Enter', '1', 'Enter'])
    expect(commands).toEqual([
      { action: 'classify', payload: { track: 'T014', class_id: 'rotary-small' } },
      { action: 'assess', payload: { track: 'T014', identity: 'hostile' } },
      { action: 'engage', payload: { track: 'T014', effector_class: 'ec-a' } },
    ])
    expect(state).toEqual(initialDecision)
  })

  it('opens a step with C, A or R and starts with nothing chosen', () => {
    expect(press(['c']).state).toEqual({ step: 'classify', chosen: null, confirmDrop: null })
    expect(press(['a']).state.step).toBe('assess')
    expect(press(['r']).state.step).toBe('respond')
  })

  it('does not commit before an option is chosen', () => {
    const { commands, state } = press(['r', 'Enter'])
    expect(commands).toEqual([])
    expect(state.step).toBe('respond')
  })

  it('lets the digit change the choice until Enter', () => {
    const { commands } = press(['r', '1', '2', 'Enter'])
    expect(commands).toEqual([
      { action: 'engage', payload: { track: 'T014', effector_class: 'ec-b' } },
    ])
  })

  it('ignores a digit beyond the options', () => {
    expect(press(['c', '9']).state.chosen).toBeNull()
  })

  it('cancels a step with Escape and keeps everything else untouched', () => {
    const { commands, state } = press(['c', '2', 'Escape'])
    expect(state).toEqual(initialDecision)
    expect(commands).toEqual([])
  })

  it('moves on to the next step after Classify and Assess, and closes after Respond', () => {
    expect(press(['c', '1', 'Enter']).state.step).toBe('assess')
    expect(press(['a', '1', 'Enter']).state.step).toBe('respond')
    expect(press(['r', '4', 'Enter']).state.step).toBeNull()
  })

  it('holds fire at once with H, without a step', () => {
    const { commands, state } = press(['h'])
    expect(commands).toEqual([{ action: 'hold', payload: { track: 'T014' } }])
    expect(state).toEqual(initialDecision)
  })

  it('does nothing without a selected track', () => {
    expect(press(['c', '1', 'Enter', 'h', 'u', 's', 'd'], null)).toEqual({
      state: initialDecision,
      commands: [],
    })
  })
})

describe('track management keys', () => {
  it('cues the EO sensor onto the selected track with a narrow cue', () => {
    expect(press(['u']).commands).toEqual([
      { action: 'sensor-cue', payload: { sensor: 'eo-1', track: 'T014', narrow: true } },
    ])
    expect(press(['u'], 'T014', null).commands).toEqual([])
  })

  it('splits at once and asks before dropping', () => {
    expect(press(['s']).commands).toEqual([{ action: 'track-split', payload: { track: 'T014' } }])
    const asked = press(['d'])
    expect(asked.commands).toEqual([])
    expect(asked.state.confirmDrop).toBe('T014')
    expect(press(['d', 'Enter']).commands).toEqual([
      { action: 'track-drop', payload: { track: 'T014' } },
    ])
    expect(press(['d', 'Escape']).commands).toEqual([])
  })

  it('ignores digits while a drop waits for confirmation', () => {
    expect(press(['d', '1']).state.confirmDrop).toBe('T014')
  })

  it('keeps relabel, merge and help for the interface (they need a field, a second track, a dialog)', () => {
    for (const key of ['l', 'm', '?']) {
      const intent = keyToIntent({ key })!
      expect(decide(initialDecision, intent, ctx, 'eo-1')).toEqual({
        state: initialDecision,
        command: null,
      })
    }
  })
})
