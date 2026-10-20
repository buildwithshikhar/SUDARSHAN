import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Checkbox, Select } from '../../ui/Field'
import { Button } from '../../ui/Button'
import { Panel } from '../../ui/Panel'
import { Table, type Column } from '../../ui/Table'
import {
  CLASSES,
  COHORTS,
  SKILLS,
  TRAINEES,
  at,
  latestSkill,
  lastSession,
  mean,
  rankings,
  round,
  scenarioById,
  type Trainee,
} from '../../mock'
import { csvFor, pct, shortDate } from './format'
import { Bar } from './kit'
import { ConfusionPanel, MissZonePanel } from './aar'

type ReportSection = 'summary' | 'sessions' | 'skills' | 'confusion' | 'missZone'
const REPORT_SECTIONS: ReportSection[] = ['summary', 'sessions', 'skills', 'confusion', 'missZone']

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** The report view: a document preview with section choices and CSV and print export. */
export function ReportBuilder({ fixedTrainee }: { fixedTrainee?: Trainee }) {
  const { t } = useTranslation()
  const [scope, setScope] = useState(fixedTrainee ? fixedTrainee.id : 'co-kestrel')
  const [sections, setSections] = useState<Record<ReportSection, boolean>>({
    summary: true,
    sessions: true,
    skills: true,
    confusion: true,
    missZone: false,
  })
  const trainees = useMemo<Trainee[]>(() => {
    if (fixedTrainee) return [fixedTrainee]
    const cohort = COHORTS.find((c) => c.id === scope)
    if (cohort) return TRAINEES.filter((tr) => cohort.traineeIds.includes(tr.id))
    if (scope === 'all') return TRAINEES
    return TRAINEES.filter((tr) => tr.id === scope)
  }, [scope, fixedTrainee])

  const scopeName = fixedTrainee
    ? fixedTrainee.name
    : (COHORTS.find((c) => c.id === scope)?.name ??
      (scope === 'all'
        ? t('m.report.allUnits')
        : (TRAINEES.find((x) => x.id === scope)?.name ?? '')))

  const summaryRows = rankings(trainees)
  const columns: Column<(typeof summaryRows)[number]>[] = [
    { key: 'rank', header: '#', mono: true, render: (r) => r.rank },
    {
      key: 'name',
      header: t('m.common.trainee'),
      render: (r) => `${r.trainee.name} (${r.trainee.callSign})`,
    },
    {
      key: 'score',
      header: t('m.common.score'),
      align: 'right',
      mono: true,
      render: (r) => r.score.toFixed(1),
    },
    {
      key: 'delta',
      header: t('m.common.change'),
      align: 'right',
      mono: true,
      render: (r) => `${r.delta >= 0 ? '+' : ''}${r.delta.toFixed(1)}`,
    },
    {
      key: 'acc',
      header: t('m.common.accuracy'),
      align: 'right',
      mono: true,
      render: (r) => pct(r.accuracy),
    },
    {
      key: 'det',
      header: t('m.common.detectTime'),
      align: 'right',
      mono: true,
      render: (r) => `${r.detectTimeS.toFixed(1)} s`,
    },
  ]

  const scopeOptions = fixedTrainee
    ? []
    : [
        ...COHORTS.map((c) => ({ value: c.id, label: c.name })),
        { value: 'all', label: t('m.report.allUnits') },
        ...TRAINEES.map((x) => ({ value: x.id, label: x.name })),
      ]

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
      <Panel title={t('m.report.options')}>
        <div className="flex flex-col gap-4">
          {!fixedTrainee && (
            <Select
              label={t('m.report.scope')}
              value={scope}
              options={scopeOptions}
              onChange={(e) => setScope(e.target.value)}
            />
          )}
          <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
            <legend className="mb-1 p-0 text-sm text-ink-2">{t('m.report.sections')}</legend>
            {REPORT_SECTIONS.map((s) => (
              <Checkbox
                key={s}
                label={t(`m.report.section.${s}`)}
                checked={sections[s]}
                onChange={(e) => setSections({ ...sections, [s]: e.target.checked })}
              />
            ))}
          </fieldset>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={() => window.print()}>
              {t('m.report.exportPdf')}
            </Button>
            <Button onClick={() => download('report.csv', csvFor(trainees))}>
              {t('m.report.exportCsv')}
            </Button>
          </div>
        </div>
      </Panel>

      <Panel title={t('m.report.preview')}>
        <article aria-label={t('m.report.preview')} className="flex flex-col gap-4">
          <header className="border-b border-line pb-3">
            <h2 className="m-0 text-md font-semibold">
              {t('m.report.title', { scope: scopeName })}
            </h2>
            <p className="num m-0 text-xs text-ink-2">
              {t('m.report.period', {
                from: shortDate(at(TRAINEES, 0).sessions[0]?.date ?? ''),
                to: shortDate(lastSession(at(TRAINEES, 0)).date),
              })}
            </p>
          </header>
          {sections.summary && (
            <section>
              <h3 className="micro-label m-0 mb-2">{t('m.report.section.summary')}</h3>
              <Table
                caption={t('m.report.section.summary')}
                columns={columns}
                rows={summaryRows}
                rowKey={(r) => r.trainee.id}
              />
              <p className="num m-0 mt-2 text-xs text-ink-2">
                {t('m.report.means', {
                  score: round(mean(trainees.map((x) => lastSession(x).score)), 1),
                  accuracy: pct(mean(trainees.map((x) => lastSession(x).classifyAccuracy))),
                })}
              </p>
            </section>
          )}
          {sections.sessions && (
            <section>
              <h3 className="micro-label m-0 mb-2">{t('m.report.section.sessions')}</h3>
              <Table
                caption={t('m.report.section.sessions')}
                columns={[
                  {
                    key: 'date',
                    header: t('m.common.date'),
                    mono: true,
                    render: (r: { date: string }) => r.date,
                  },
                  {
                    key: 'tr',
                    header: t('m.common.trainee'),
                    render: (r: { name: string }) => r.name,
                  },
                  {
                    key: 'sc',
                    header: t('m.common.scenario'),
                    render: (r: { scenario: string }) => r.scenario,
                  },
                  {
                    key: 'score',
                    header: t('m.common.score'),
                    align: 'right',
                    mono: true,
                    render: (r: { score: number }) => r.score.toFixed(1),
                  },
                ]}
                rows={trainees.slice(0, 6).flatMap((tr) =>
                  tr.sessions.slice(2).map((s) => ({
                    key: s.id,
                    date: s.date,
                    name: tr.name,
                    scenario: scenarioById(s.scenarioId).name,
                    score: s.score,
                  })),
                )}
                rowKey={(r) => r.key}
              />
            </section>
          )}
          {sections.skills && (
            <section>
              <h3 className="micro-label m-0 mb-2">{t('m.report.section.skills')}</h3>
              {SKILLS.map((k) => (
                <Bar
                  key={k}
                  label={t(`m.skill.${k}`)}
                  value={latestSkill(trainees, k)}
                  text={pct(latestSkill(trainees, k))}
                />
              ))}
            </section>
          )}
          {sections.confusion && (
            <ConfusionPanel trainees={trainees} title={t('m.aar.confusion')} />
          )}
          {sections.missZone && <MissZonePanel trainees={trainees} />}
          <footer className="num border-t border-line pt-2 text-xs text-ink-2">
            {t('m.report.footer', { classes: CLASSES.length, trainees: trainees.length })}
          </footer>
        </article>
      </Panel>
    </div>
  )
}
