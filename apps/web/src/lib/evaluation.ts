/** The public evaluation build (docs/DEPLOY.md "Evaluation deployment"): set at image build time. */
export const EVALUATION_MODE = import.meta.env.VITE_EVALUATION_MODE === 'true'

export type EvaluationSeat = 'operator' | 'commander' | 'instructor' | 'admin'

/** The seat ids the sign-in page offers, in order, and the id the API's evaluation entry takes. */
export const EVALUATION_SEATS: { id: EvaluationSeat; api: string }[] = [
  { id: 'operator', api: 'trainee' },
  { id: 'commander', api: 'commander' },
  { id: 'instructor', api: 'instructor' },
  { id: 'admin', api: 'admin' },
]
