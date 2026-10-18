/**
 * DEV-ONLY scored record for the scripted session. Loaded by `getScore` behind
 * `import.meta.env.DEV` and `?mock=1`, so it is absent from production builds
 * (tests/live/prodBuild.test.ts checks this). Playwright serves the same object from route fixtures.
 *
 * Every figure is invented reference data in a fictional scenario. The shape follows
 * `score-result.v1`; the numbers follow the rules in docs/SCORING.md and the training-baseline
 * weights, so they add up, but nothing here was measured.
 */
import type { SessionScore } from '../contracts/score-result.v1'

export const MOCK_SCORE_MARKER = 'scripted-score-marker-2b9d44'

/** The score of a session in which one hostile contact was worked well and a civil one engaged. */
export const MOCK_SCORE: SessionScore = {
  contract: 'score-result.v1',
  scenario: { id: 'harrier-field-afternoon-watch', version: '0.3.1-mock' },
  rule_pack: { id: 'training-baseline', version: '1.0.0' },
  seed: 240117,
  ticks: 1280,
  duration_s: 64.0,
  event_head: 'c41f09a7d3e85b62f01a9c7e3d54b8a60e2f719cd8350a46b7e91f2c05d38a14',
  score: 0.3464,
  decision_score: 0.4184,
  report_score: 0.8768,
  sdt: {
    hits: 1,
    misses: 0,
    false_alarms: 1,
    correct_rejections: 1,
    signal_trials: 1,
    noise_trials: 2,
    hit_rate: 1,
    false_alarm_rate: 0.5,
    hit_rate_used: 0.75,
    false_alarm_rate_used: 0.5,
    d_prime: 0.6745,
    criterion: -0.3372,
    corrected: true,
  },
  threats: [
    {
      threat_id: 'th-quad',
      label: { en: 'quad', hi: 'क्वाड' },
      class_id: 'rotary-small',
      disposition: 'hostile',
      presented: true,
      worked: true,
      first_report_s: 4.3,
      hard_fail: false,
      decision: 0.8368,
      score: 0.6928,
      nodes: [
        {
          node: 'detect',
          weight: 0.25,
          score: 1,
          reason: 'detect.band',
          params: { seconds: 6.8, standard: 12, first_action: 'sensor-cue', track: 'T014' },
        },
        {
          node: 'classify',
          weight: 0.25,
          score: 0.925,
          reason: 'classify.correct',
          params: { class: 'rotary-small', seconds: 31.4, standard: 25, timing: 0.75, changes: 1 },
        },
        {
          node: 'assess',
          weight: 0.15,
          score: 0.5,
          reason: 'assess.partial',
          params: { given: 'suspect', actual: 'hostile' },
        },
        {
          node: 'respond',
          weight: 0.2,
          score: 0.775,
          reason: 'respond.engage',
          params: {
            seconds: 52.7,
            standard: 45,
            timing: 0.75,
            blocked_attempts: 1,
            effector: 'ec-a',
          },
        },
      ],
      findings: [
        {
          kind: 'blocked-attempt',
          reason: 'finding.blocked-attempt',
          params: { attempts: 1 },
          cost: 0.15,
        },
        {
          kind: 'track-error',
          reason: 'finding.track-error.swap',
          params: { error_id: 'swap-1', t: 37.6 },
          cost: 0.15,
        },
      ],
      report: {
        filed: true,
        reports_filed: 2,
        quality: 0.846,
        timeliness: 1,
        score: 0.8768,
        reason: 'report.filed',
        params: { worst_field: 'count', seconds: 38.5, standard: 40, timeliness: 1 },
        fields: [
          {
            field: 'what',
            weight: 0.3,
            score: 1,
            reason: 'report.what.ok',
            params: { given: 'rotary-small', actual: 'rotary-small' },
          },
          {
            field: 'where',
            weight: 0.25,
            score: 0.793,
            reason: 'report.where.partial',
            params: { error_m: 212, tolerance_m: 150 },
          },
          {
            field: 'count',
            weight: 0.15,
            score: 0.5,
            reason: 'report.count.partial',
            params: { given: 1, actual: 2 },
          },
          {
            field: 'heading',
            weight: 0.15,
            score: 0.825,
            reason: 'report.heading.partial',
            params: { error_deg: 27, tolerance_deg: 20 },
          },
          {
            field: 'calibration',
            weight: 0.15,
            score: 0.9936,
            reason: 'report.calibration.ok',
            params: { stated: 0.9, achieved: 0.82 },
          },
        ],
      },
    },
    {
      threat_id: 'th-survey',
      label: { en: 'survey', hi: 'सर्वे' },
      class_id: 'rotary-small',
      disposition: 'civil-permitted',
      presented: true,
      worked: true,
      first_report_s: 1.9,
      hard_fail: true,
      decision: 0.75,
      score: 0,
      nodes: [
        {
          node: 'detect',
          weight: 0.25,
          score: 0.75,
          reason: 'detect.band',
          params: { seconds: 17.9, standard: 12, first_action: 'designate', track: 'T021' },
        },
        {
          node: 'classify',
          weight: 0.25,
          score: 1,
          reason: 'classify.correct',
          params: { class: 'rotary-small', seconds: 22.4, standard: 25, timing: 1, changes: 0 },
        },
        {
          node: 'assess',
          weight: 0.15,
          score: 0,
          reason: 'assess.wrong',
          params: { given: 'suspect', actual: 'civil-permitted' },
        },
        {
          node: 'respond',
          weight: 0.2,
          score: 1,
          reason: 'respond.hold-fire',
          params: { blocked_attempts: 0 },
        },
      ],
      findings: [
        {
          kind: 'hard-fail',
          reason: 'finding.hard-fail.engaged-non-hostile',
          params: { t: 58.4, track: 'T021', actual: 'civil-permitted' },
          cost: 0.75,
        },
      ],
      report: null,
    },
    {
      threat_id: 'th-flock',
      label: { en: 'flock', hi: 'झुंड' },
      class_id: 'bird',
      disposition: 'clutter',
      presented: true,
      worked: false,
      first_report_s: 3.2,
      score: null,
      findings: [{ kind: 'not-worked', reason: 'finding.not-worked' }],
    },
    {
      threat_id: 'th-wing',
      label: { en: 'wing', hi: 'विंग' },
      class_id: 'fixed-wing-small',
      disposition: 'hostile',
      presented: false,
      findings: [{ kind: 'not-presented', reason: 'finding.not-presented' }],
    },
  ],
  findings: [],
  lessons: [
    {
      key: 'lesson.hard-fail.engaged-non-hostile',
      threat_id: 'th-survey',
      cost: 0.75,
      params: {
        threat: { en: 'survey', hi: 'सर्वे' },
        t: 58.4,
        track: 'T021',
        actual: 'civil-permitted',
      },
    },
    {
      key: 'lesson.blocked-attempt',
      threat_id: 'th-quad',
      cost: 0.15,
      params: { threat: { en: 'quad', hi: 'क्वाड' }, attempts: 1 },
    },
    {
      key: 'lesson.track-error',
      threat_id: 'th-quad',
      cost: 0.15,
      params: { threat: { en: 'quad', hi: 'क्वाड' }, error_id: 'swap-1', t: 37.6 },
    },
  ],
}

/** The same record with no contact presented: the empty state. */
export const MOCK_SCORE_EMPTY: SessionScore = {
  ...MOCK_SCORE,
  score: null,
  decision_score: null,
  report_score: null,
  sdt: {
    hits: 0,
    misses: 0,
    false_alarms: 0,
    correct_rejections: 0,
    signal_trials: 0,
    noise_trials: 0,
    hit_rate: null,
    false_alarm_rate: null,
    hit_rate_used: null,
    false_alarm_rate_used: null,
    d_prime: null,
    criterion: null,
    corrected: false,
  },
  threats: MOCK_SCORE.threats.map((t) => ({
    threat_id: t.threat_id,
    label: t.label,
    class_id: t.class_id,
    disposition: t.disposition,
    presented: false,
    findings: [{ kind: 'not-presented', reason: 'finding.not-presented' }],
  })),
  findings: [],
  lessons: [],
}
