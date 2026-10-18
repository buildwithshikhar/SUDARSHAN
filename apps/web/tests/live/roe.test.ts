import { describe, expect, it } from 'vitest'
import i18n from '../../src/i18n'
import { describeEvent } from '../../src/live/eventText'
import { evaluateRoe, MOCK_RULES } from '../../src/live/mock'
import {
  conditionLines,
  describeVerdict,
  effectorLabel,
  previewContext,
  ruleThatWouldPermit,
  zoneRoleAt,
  type Lang,
} from '../../src/live/roe'
import { toVerdictForTest } from './verdict'
import { event, track, verdictEvent, welcome } from './helpers'

const w = welcome()
const fixedT = (lang: Lang) => i18n.getFixedT(lang)

/** One verdict per code the server can send, with the detail it sends for it. */
const CODES: Record<string, Record<string, unknown>> = {
  permitted: { permitted: true, code: 'permitted', detail: { effector_class: 'ec-a' } },
  'default-hold': {
    action: 'hold',
    permitted: true,
    code: 'default-hold',
    rule_id: null,
    rule_title: null,
    authority: null,
    detail: {},
  },
  'no-rule': {
    permitted: false,
    code: 'no-rule',
    rule_id: null,
    rule_title: null,
    authority: null,
    detail: { action: 'engage' },
  },
  conditions: {},
  effector: {
    permitted: false,
    code: 'effector',
    effector_class: 'ec-b',
    detail: { effector_class: 'ec-b', allowed: ['ec-a'] },
  },
  authority: {
    permitted: false,
    code: 'authority',
    rule_id: 'hostile-inner-zone',
    authority: 'commander',
    detail: { required: 'commander' },
  },
}

describe.each(['en', 'hi'] as const)('verdict text in %s', (lang) => {
  const t = fixedT(lang)

  it.each(Object.keys(CODES))(
    'renders the %s code with a headline, a reason and no raw placeholders',
    (code) => {
      const text = describeVerdict(toVerdictForTest(verdictEvent(1, CODES[code])), w.rules, t, lang)
      expect(text.headline).toBe(t(text.permitted ? 'live.roe.permitted' : 'live.roe.blocked'))
      expect(text.reason.length).toBeGreaterThan(8)
      for (const s of [
        text.headline,
        text.reason,
        ...text.unmet.flatMap((u) => [u.field, u.required, u.actual]),
      ]) {
        expect(s).not.toMatch(/{{|live\.roe|undefined/)
      }
      // the pack id and version always travel with the verdict
      expect(text.pack).toBe('training-baseline 1.0.0')
    },
  )

  it('names the rule in the current language for every code that cites one', () => {
    const expected =
      lang === 'en' ? 'Suspect contact in the outer zone' : 'बाहरी क्षेत्र में संदिग्ध संपर्क'
    for (const code of ['permitted', 'conditions', 'effector'] as const) {
      const text = describeVerdict(toVerdictForTest(verdictEvent(1, CODES[code])), w.rules, t, lang)
      expect(text.rule).toContain(expected)
    }
    expect(
      describeVerdict(toVerdictForTest(verdictEvent(1, CODES['no-rule'])), w.rules, t, lang).rule,
    ).toBeNull()
  })

  it('lists each unmet condition with its field, requirement and actual value', () => {
    const text = describeVerdict(toVerdictForTest(verdictEvent(1)), w.rules, t, lang)
    expect(text.unmet).toHaveLength(2)
    expect(text.unmet[0]!.field).toBe(t('live.roe.field.identity'))
    expect(text.unmet[0]!.required).toBe(
      `${t('live.identity.suspect')} / ${t('live.identity.hostile')}`,
    )
    expect(text.unmet[0]!.actual).toBe(t('live.roe.notSet'))
    expect(text.unmet[1]!.field).toBe(t('live.roe.field.confidence'))
    expect(text.unmet[1]!.required).toBe(t('live.roe.atLeast', { value: '60%' }))
    expect(text.unmet[1]!.actual).toBe('40%')
  })

  it('names the effector and the allowed ones for an effector gap', () => {
    const text = describeVerdict(
      toVerdictForTest(verdictEvent(1, CODES.effector)),
      w.rules,
      t,
      lang,
    )
    expect(text.reason).toContain(effectorLabel('ec-b', w.rules, lang))
    expect(text.reason).toContain(effectorLabel('ec-a', w.rules, lang))
  })

  it('names the authority for an authority gap', () => {
    const text = describeVerdict(
      toVerdictForTest(verdictEvent(1, CODES.authority)),
      w.rules,
      t,
      lang,
    )
    expect(text.reason).toContain(t('live.roe.authority.commander'))
  })

  it('falls back to a plain line for a code this client does not know', () => {
    const text = describeVerdict(
      toVerdictForTest(verdictEvent(1, { code: 'future-code' })),
      w.rules,
      t,
      lang,
    )
    expect(text.reason).toContain('future-code')
  })

  it('has a line for every kind of trainee event, with no raw placeholders', () => {
    const events = [
      event(1, 'session.start'),
      event(2, 'session.end'),
      event(3, 'track.init', { track: 'T1' }),
      event(4, 'track.confirm', { track: 'T1' }),
      event(5, 'track.coast', { track: 'T1' }),
      event(6, 'track.resume', { track: 'T1' }),
      event(7, 'track.drop', { track: 'T1', reason: 'operator' }),
      event(8, 'track.relabel', { track: 'T1', label: 'A', previous: 'T1' }),
      event(9, 'track.relabel', { track: 'T1', label: 'A', previous: 'T1', exchanged_with: 'T2' }),
      event(10, 'track.merge', { survivor: 'T1', absorbed: 'T2' }),
      event(11, 'track.split', { source: 'T1', new: 'T3' }),
      event(12, 'sensor.cue', {
        sensor: 'eo-1',
        track: 'T1',
        accepted: true,
        bearing_deg: 41.2,
        fov_deg: 4.3,
      }),
      event(13, 'sensor.cue', {
        sensor: 'radar-1',
        track: 'T1',
        accepted: false,
        reason: 'cannot be cued',
      }),
      event(14, 'action.rejected', {
        action: 'track-relabel',
        reason: 'label in use',
        payload: {},
      }),
      verdictEvent(15),
      event(16, 'action.classify', { track: 'T1', class_id: 'bird' }),
      event(17, 'action.assess', { track: 'T1', identity: 'friend' }),
      event(18, 'action.engage', { track: 'T1', effector_class: 'ec-a' }),
      event(19, 'action.hold', { track: 'T1' }),
      event(20, 'action.report', { track: 'T1' }),
      event(21, 'action.designate', { track: 'T1' }),
      event(22, 'action.sensor_cue', { sensor: 'eo-1', track: 'T1' }),
    ]
    for (const e of events) {
      const line = describeEvent(e, t, lang)
      expect(line.text, e.type).not.toMatch(/{{|live\.event|undefined/)
      expect(line.text.length).toBeGreaterThan(3)
    }
    expect(describeEvent(verdictEvent(1), t, lang).tone).toBe('blocked')
    expect(
      describeEvent(event(2, 'action.rejected', { action: 'x', reason: 'y' }), t, lang).tone,
    ).toBe('refused')
    expect(describeEvent(event(3, 'sensor.cue', { accepted: false }), t, lang).tone).toBe('refused')
  })
})

describe('rule preview', () => {
  it('finds the rule that would permit a response, with the effector class it lists', () => {
    expect(ruleThatWouldPermit(w.rules, 'engage', 'ec-a')?.id).toBe('suspect-outer-zone')
    expect(ruleThatWouldPermit(w.rules, 'engage', 'ec-b')?.id).toBe('hostile-inner-zone')
    expect(ruleThatWouldPermit(w.rules, 'engage', null)).toBeNull()
    expect(ruleThatWouldPermit(w.rules, 'report', null)?.id).toBe('track-everything')
    expect(ruleThatWouldPermit(w.rules, 'fire-at-will', null)).toBeNull()
  })

  it('finds the zone of the smallest circle that holds a position', () => {
    expect(zoneRoleAt(w.briefing, { x: 100, y: 100, z: 0 })).toBe('inner')
    expect(zoneRoleAt(w.briefing, { x: 2000, y: 100, z: 0 })).toBe('outer')
    expect(zoneRoleAt(w.briefing, { x: 5000, y: 5000, z: 0 })).toBeNull()
  })

  it('marks each condition met or unmet from what the operator has set', () => {
    const t = fixedT('en')
    const rule = w.rules.rules[1]!
    const outer = track('T1', { position: { x: 1500, y: 0, z: 40 }, class_support: 0.72 })
    const ctx = previewContext(outer, w.briefing, { T1: 'hostile' }, {})
    expect(conditionLines(rule, ctx, t).map((l) => [l.field, l.status])).toEqual([
      ['identity', 'met'],
      ['zone', 'met'],
      ['confidence', 'met'],
    ])
    const weak = previewContext(track('T1', { class_support: 0.3 }), w.briefing, {}, {})
    expect(
      conditionLines(rule, weak, t)
        .filter((l) => l.status === 'unmet')
        .map((l) => l.field),
    ).toEqual(['identity', 'confidence'])
  })
})

describe('the mock applies the same rule as the server', () => {
  const ctx = {
    identity: 'hostile',
    classification: 'rotary-small',
    zone_role: 'outer',
    confidence: 0.82,
  }

  it('permits a response that a rule allows, with that rule', () => {
    const v = evaluateRoe(MOCK_RULES, 'engage', ctx, 'ec-a')
    expect([v.permitted, v.code, v.rule?.id]).toEqual([true, 'permitted', 'suspect-outer-zone'])
  })

  it('reports unmet conditions of the closest rule', () => {
    const v = evaluateRoe(
      MOCK_RULES,
      'engage',
      { ...ctx, identity: 'neutral', confidence: 0.4 },
      'ec-a',
    )
    expect(v.code).toBe('conditions')
    expect((v.detail.unmet as { field: string }[]).map((u) => u.field)).toEqual([
      'identity',
      'confidence',
    ])
  })

  it('reports an effector gap, an authority gap, no rule and default hold', () => {
    expect(evaluateRoe(MOCK_RULES, 'engage', ctx, 'ec-b').code).toBe('effector')
    expect(
      evaluateRoe(MOCK_RULES, 'engage', { ...ctx, zone_role: 'inner', confidence: 0.9 }, 'ec-b')
        .code,
    ).toBe('authority')
    expect(evaluateRoe(MOCK_RULES, 'jam', ctx, null).code).toBe('no-rule')
    expect(evaluateRoe({ ...MOCK_RULES, rules: [] }, 'hold', ctx, null).code).toBe('default-hold')
  })
})
