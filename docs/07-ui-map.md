# 07 · UI map and design-system direction

Platform: SUDARSHAN. Roles: **Trainee**, **Instructor** (also sees everything a trainee sees for their cohorts) and **Admin** (system only; sees no trainee scores unless also an instructor).

## Counts

| Role | Sidebar groups | Modules | Screens | Subscreens / panels |
|---|---|---|---|---|
| Trainee | 3 | 6 | 14 | 34 |
| Instructor | 4 | 10 | 19 | 41 |
| Admin | 3 | 8 | 10 | 17 |
| Shared (sign-in, system states) | 1 | 2 | 5 | 0 |
| **Total** | **11** | **26** | **48** | **92** |

Counts are generated from one source list (kept as `docs/ui-map.yaml` in the repo, so the counts never drift). Every screen needs four states: populated, empty, loading and error.

## Sidebar and screens

### Trainee — 3 groups · 6 modules · 14 screens · 34 subscreens

| Group | Module | Screen | Subscreens / panels |
|---|---|---|---|
| Train | Today | Today overview | Recommended drill, Skills due for review, Last session summary |
| Train | Drills | Curriculum | Course list, Course detail |
| Train | Drills | Quick drill | Difficulty and focus picker |
| Train | Drills | Session lobby | Briefing, Role and kit check |
| Train | Drills | Live session workspace | EO/IR view, Radar PPI, RF spectrum and waterfall, Acoustic spectrogram, Tactical map, Track table, Decision panel, Comms and event log |
| Train | Drills | Debrief | Score summary, First three lessons |
| Train | Recognition library | Threat catalogue | Class detail |
| Train | Recognition library | Clutter catalogue | Clutter detail |
| Train | Recognition library | Signature drills | Spaced-repetition card session |
| Review | My performance | Sessions | Session list, Session replay (seen vs truth), Decision-tree path, Confusion matrix |
| Review | My performance | Progress | Skill proficiency, Learning curves, Reaction-time trend |
| Review | My performance | Reports | PDF export |
| Account | Profile | Profile and preferences | Language, Theme, Accessibility |
| Account | Help | Help and SOPs | Keyboard shortcuts, Data and honesty notice |

### Instructor — 4 groups · 10 modules · 19 screens · 41 subscreens

| Group | Module | Screen | Subscreens / panels |
|---|---|---|---|
| Class | Cohorts | Cohort list | — |
| Class | Cohorts | Cohort detail | Members, Assigned curriculum, Drill sequence |
| Class | Trainees | Trainee list | — |
| Class | Trainees | Trainee profile | Skill model, Session history, Instructor notes |
| Run | Live sessions | Launch session | Scenario pick, Participants, Mode (assessed / practice) |
| Run | Live sessions | Live monitor | Class grid, Trainee drill-down (ground truth overlay), Inject events, Pause and resume, Annotate timeline |
| Run | Team exercise | Team setup | Role assignment, Sector split |
| Run | Team exercise | Team monitor | Handoff view |
| Content | Scenarios | Scenario library | Filters and tags |
| Content | Scenarios | Scenario editor | Terrain and site, Threat timeline, Sensors and degradations, Weather and light, Validation (solvability, diversity), Preview run |
| Content | Generator | Generator studio | Difficulty vector, Constraint set, Batch generate, Diversity report |
| Content | Rule packs | Rule-pack list | — |
| Content | Rule packs | Rule-pack editor | ROE rules, Scoring weights, Thresholds, Version diff |
| Content | Curricula | Curriculum list | — |
| Content | Curricula | Curriculum editor | Stages and gates |
| Review | Unit AAR | Unit dashboard | Cohort trends, Skill heat map, Miss-zone heat map |
| Review | Unit AAR | Compare trainees | — |
| Review | Unit AAR | Annotated replay | Seen vs truth, Decision path, Instructor annotations |
| Review | Reports | Report builder | PDF, CSV export |

### Admin — 3 groups · 8 modules · 10 screens · 17 subscreens

| Group | Module | Screen | Subscreens / panels |
|---|---|---|---|
| Administration | Users and roles | User list | — |
| Administration | Users and roles | User detail | Roles, Reset access |
| Administration | Organisation | Units | Unit detail |
| Administration | Packs | Pack manager | Terrain packs, Sensor profiles, Scenario packs, Import and export |
| Trust | Data register | Sources | Source detail and licence, Parameter provenance |
| Trust | Records | Audit log | — |
| Trust | Records | Record verification | Chain check, Signature check |
| System | Health | System health | Services, Performance, Storage |
| System | Settings | Instance settings | Mode (production / demo), Language defaults, Retention |
| System | Backup | Backup and restore | — |

### Shared — 1 group · 2 modules · 5 screens · 0 subscreens

| Group | Module | Screen | Subscreens / panels |
|---|---|---|---|
| Shell | Entry | Sign in | — |
| Shell | Entry | About and data notice | — |
| Shell | System states | Not found | — |
| Shell | System states | No access | — |
| Shell | System states | Offline or server unreachable | — |

## Live session workspace (the screen that sells the product)

The default layout is a fixed 12-column grid at 1920 × 1080 that degrades to 1366 × 768:

- **Top bar (32 px):** session clock (UTC and scenario time, monospace), weather and light state, ROE pack version, connection state, "FICTIONAL SCENARIO" label.
- **Left 7 columns:** EO/IR view (Three.js) with a reticle HUD, mode switch (day TV / NV / thermal white-hot / black-hot) and zoom ladder. The tactical map (MapLibre) sits as a toggle or a split below.
- **Right 5 columns, stacked:** radar PPI (round, phosphor persistence), then RF waterfall and acoustic spectrogram as tabs, then the track table.
- **Bottom strip (Decision panel):** for the selected track, Classify → Assess → Respond as three keyboard-driven steps (1–9 keys, Enter to commit). It shows the ROE rule that permits or forbids each response, live.
- **Keyboard first:** Tab cycles tracks, `C` classify, `A` assess, `R` respond, `H` hold fire, `Space` pauses (practice mode only), `?` shows shortcuts. Every action is also reachable by mouse.

## Design-system direction

**Palette (dark operations theme, primary).** Neutral graphite, never pure black, never blue-tinted.

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | #0B0E11 | #F5F6F7 | app background |
| `surface-1` | #12161A | #FFFFFF | panels |
| `surface-2` | #1A1F24 | #EEF0F2 | raised and inset |
| `border` | #272D34 | #D5D9DE | 1 px dividers |
| `text` | #E4E7EA | #14181C | primary text |
| `text-2` | #9BA4AE | #4F5862 | secondary |
| `accent` | #4FB6C2 | #1F7480 | focus, selection, primary action (the only interactive hue) |
| `signal` | #E0A526 | #9A6A00 | brand tick and warnings only |
| track: hostile | #E5484D | #C62B30 | |
| track: suspect | #EE8A45 | #B85A14 | |
| track: unknown | #E6C84F | #8C7400 | |
| track: neutral / civil | #5DB46E | #2E7D3E | |
| track: friend | #5B9BD5 | #2F6EA8 | |

- Track colours follow the affiliation convention of APP-6 / MIL-STD-2525 (red hostile, yellow unknown, green neutral, blue friend). The symbol frame shapes are drawn as our own simplified SVG set, and we do not claim compliance with either standard.
- Colour is never the only cue: shape frame plus a text label.
- All pairs are checked at WCAG AA (4.5:1 for text, 3:1 for UI) in CI with axe plus a token-contrast unit test.

**Type.**
- IBM Plex Sans for the UI, IBM Plex Mono for all numbers, clocks, coordinates and logs (`tabular-nums`), and Noto Sans Devanagari for Hindi. All fonts self-hosted under the OFL.
- Scale: 11 / 12 / 13 / 14 / 16 / 20 / 24 / 32, with a 13 px base in dense ops screens and 14 px elsewhere.
- Uppercase is used only for 11 px micro-labels with +6% tracking.

**Spacing and density.**
- A 4 px grid (4, 8, 12, 16, 24, 32, 48), with 2 px radius on controls and 4 px on panels.
- Table rows are 28 px in compact mode and 36 px in comfortable. Panels are separated by 1 px borders, not shadows.

**Icons.**
- IBM Carbon icons (Apache-2.0), 16 and 20 px, with a single stroke style throughout.
- A custom SVG set for track symbols and sensors.
- No emoji anywhere, and no mixing of icon families.

**Motion.** 120–160 ms ease-out for state changes only. No decorative animation. Respects `prefers-reduced-motion`.

**Charts (AAR).**
- Muted series colours from the token set, with a direct label or legend and real axis titles.
- Confusion matrix as a sequential single-hue heat map; heat maps use perceptually uniform maps (viridis / cividis).
- Every chart has a data-table alternative for accessibility.

**3D look.**
- Physically based materials, ACES tone mapping, and a time-of-day sky with sun and moon positions driving light.
- Exponential height fog for haze, rain as screen-space streaks plus reduced contrast, and wind visibly moving trees and drone drift.
- **Thermal:** a per-material temperature value goes into the shader, mapped white-hot or black-hot. Motors and batteries run hotter than the airframe. Sensor noise, mild blur and auto-gain "hunting" are added.
- **Night vision:** green-phosphor P43-style tint, scintillation noise and halo bloom on light sources.
- A **reticle HUD** in SVG over the canvas with range, bearing, elevation, zoom, a time code and a sensor-health indicator, styled like an instrument.
- Quality tiers (low / medium / high) are picked by an fps probe at session start.

**Sensor consoles.**
- **Radar PPI:** a rotating sweep with phosphor decay, range rings and bearing ticks, raw plots plus track symbols, and adjustable clutter gain.
- **RF:** a spectrum line plus a waterfall (inferno colormap), with band markers and hop patterns visible.
- **Acoustic:** a scrolling spectrogram with harmonic cursors.
- All of them are drawn on canvas at device pixel ratio and look like instruments rather than charts.

## What makes software look AI-generated (banned list)

1. Purple or blue gradient heroes, gradient text, glow borders, glassmorphism and frosted cards.
2. A "welcome back 👋" header, emoji as icons, and sparkle ✨ "AI" badges.
3. Three equal feature cards in a row, KPI tiles with big numbers and tiny up-arrows on every page, and the "bento grid".
4. Default Tailwind or shadcn look shipped unchanged: slate-on-white with `rounded-xl` and `shadow-lg` everywhere, Inter at every size, and indigo-600 buttons.
5. Lorem ipsum, "John Doe", round-number fake data (100, 50%, 1,000) and identical sparklines.
6. Mixed icon sets, icons inside every button, and illustrations of robots or drones in a cartoon style.
7. Huge padding and low density on operational screens, and centred layouts for tools.
8. Generic labels ("Dashboard", "Analytics", "Insights") instead of domain nouns ("Live monitor", "Unit AAR", "Track table").
9. Tooltips that restate the label, toast spam, and confetti.
10. Copy that sounds like marketing ("Revolutionise your training journey"). We write in operator language, which is short, exact and imperative.

The guard is a `docs/DESIGN.md` with tokens, plus a visual-regression snapshot set in Playwright for the 12 key screens, reviewed against this list each wave.
