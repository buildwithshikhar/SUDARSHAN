import type { TraineeEvent } from '../../src/live/protocol'
import { initialState, reduce } from '../../src/live/store'
import { frame } from './helpers'

/** Run a response roe.verdict event through the store, as the app does, and return the stored verdict. */
export function toVerdictForTest(e: TraineeEvent) {
  const state = reduce(initialState(), { type: 'message', message: frame({ events: [e] }), at: 0 })
  if (!state.verdict) throw new Error('not a response verdict event')
  return state.verdict
}
