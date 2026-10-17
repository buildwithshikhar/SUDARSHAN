# Wave 2 UI review

Captured at 1440×900, full page, from the running demo stack on the final wave 2 build, signed in as the seeded demo instructor. The notes are written by the agent that built the screens, so they are not an independent review.

| Screen | Image |
|---|---|
| Status, EN dark | [status-en-dark.png](status-en-dark.png) |
| Status, HI dark | [status-hi-dark.png](status-hi-dark.png) |
| Status, EN light | [status-en-light.png](status-en-light.png) |
| Status, HI light | [status-hi-light.png](status-hi-light.png) |
| Sign in, EN dark | [sign-in-en-dark.png](sign-in-en-dark.png) |
| Module empty state (Cohorts), EN dark | [module-empty-en-dark.png](module-empty-en-dark.png) |

**Hindi is not verified or reviewed.** Every Hindi string in these images is a draft by Claude Code; the review sheet is [../../i18n/HI_REVIEW.md](../../i18n/HI_REVIEW.md) and Q-15 stays open.

## Wave 1 findings: what changed

| Wave 1 finding | State now |
|---|---|
| Fonts were system stacks | **Fixed.** IBM Plex Sans, Plex Mono and Noto Sans Devanagari are bundled; the images show Plex in Latin and Noto in Devanagari. Licences are in `docs/FONTS.md`. |
| Tabular numerals not guaranteed | **Fixed.** Values are set in Plex Mono and `tabular-nums` is on app-wide; the version, commit and timestamp columns align. |
| Page 75% empty, top-left-heavy | **Fixed for the signed-in screens.** A real shell (top bar, sidebar, content grid, status strip) with build and session panels and a modules table fills the canvas. The sign-in page is still sparse by nature (see below). |
| Redundant "Service" row | **Removed.** |
| No header mark | **Fixed.** A monogram in a ring-and-bearing frame, with the letter taken from `brand.json`. |
| Carbon icons in one weight | **Done.** Used only for alerts, empty and error states and sign out; navigation is text. |
| Error state named no endpoint or status | **Not done.** Still a generic message (follow-up). |

## What holds up

- **Palette and restraint.** Graphite neutrals, one teal for interaction, one amber that appears only on the brand frame and the tagline rule. No gradients, shadows, glow, cards or illustrations. Dark and light read as the same product.
- **Type hierarchy.** Page title 20 px, panel titles 13 px semibold, micro-labels 11 px uppercase for sidebar groups, values in mono. The hierarchy reads at a glance.
- **Density.** 28 px rows, 1 px borders, a 4 px grid. The modules table is dense but readable, and it is honest: every unbuilt module says which wave delivers it.
- **States.** Loading, error, empty and populated all exist, are covered by unit tests and are axe-clean. The empty state for an unbuilt module is a dashed box with an information icon and the wave number, not a marketing placeholder.
- **Colour is not the only cue.** Status squares are paired with words; badges carry text; the selected sidebar item has a bar as well as a fill.
- **Accessibility.** axe reports zero violations in English and Hindi, dark and light, for sign in, About, Not found, Offline, and (signed in) Status, a module page, Profile (both tabs), No access and the components page, for each role.

## Findings

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | **The sign-in page is mostly empty.** The identity block and the form sit in the middle of a 1440 px canvas with large dark margins. It is deliberate and quiet, but it is the least finished-looking screen. | Medium | Follow-up |
| 2 | **Status is informative but not yet useful to an operator.** Build and session panels are mostly for the maintainer; nothing on it is an operational state because there is nothing operational yet. It should be reworked when the first real modules exist. | Low | Accepted for wave 2 |
| 3 | **Raw values in mono mix with sentences.** The environment value (`demo`) and timestamps stay in English in the Hindi view by design (server values), which reads slightly uneven next to Devanagari labels. | Low | Accepted |
| 4 | **Hindi line height and weight.** Noto Sans Devanagari at 13 px reads smaller than Plex at the same size; row labels in Hindi look lighter than their English equivalents. | Low | Follow-up: consider 14 px for Hindi body text after a native reader has looked |
| 5 | **Language and theme controls are text segments.** Clear and keyboard-friendly, but four buttons in the top bar plus the account email make the bar busy at narrower widths. The sidebar and top bar are not yet responsive below about 1024 px. | Medium | Follow-up |
| 6 | **Brand mark is small at 24 px.** The monogram is legible at 48 px on the sign-in page but its bearing ticks blur at 24 px. | Low | Follow-up |
| 7 | **Error states do not name the failing request.** | Low | Follow-up (carried from wave 1) |
| 8 | **Visual baselines exist for macOS only.** The snapshot tests are excluded from the CI end-to-end job until Linux baselines are generated. | Medium | Follow-up |
| 9 | **No dense data components yet.** Table and Tabs exist, but sortable and filterable tables, which the track table needs, do not. | Info | Later waves |

## Does it look AI-generated?

Not by the checklist in `docs/DESIGN.md`: no gradients, glass, cards in threes, KPI tiles, emoji or default component-library look, and the copy is operator-style. The remaining risk is generic restraint: it could be any internal admin tool. What will make it unmistakably this product is the live session workspace, the sensor consoles and the recognition imagery in later waves, not more chrome here.

## Follow-ups logged

Items 1, 4, 5, 6, 7 and 8 are logged under Wave 2 in [../../BUILD_LOG.md](../../BUILD_LOG.md).
