# Wave 1 UI review

Screens reviewed at 1440×900, full page, captured from the running demo stack (nginx and Postgres) on the final wave 1 build:

| State | Image |
|---|---|
| EN dark | [status-en-dark.png](status-en-dark.png) |
| HI dark | [status-hi-dark.png](status-hi-dark.png) |
| EN light | [status-en-light.png](status-en-light.png) |
| HI light | [status-hi-light.png](status-hi-light.png) |
| Loading (EN dark) | [state-loading-en-dark.png](state-loading-en-dark.png) |
| Error (EN dark) | [state-error-en-dark.png](state-error-en-dark.png) |

Reviewed against the quality bar in CLAUDE.md and `docs/DESIGN.md`. This is one placeholder screen, so the review is about the foundations, not the product. The images are the evidence; the notes are the reviewer's, written by the same agent that built the screen, so they are not independent.

## What holds up

- **Palette.** Graphite neutrals, one interactive hue (teal) for selection and focus, one amber tick that is used for nothing else. No gradients, glow, shadows or default Tailwind colours. Dark and light both read as the same product.
- **No template look.** There are no cards, KPI tiles, hero, icons or illustrations. Labels are domain wording ("Build status", "Environment").
- **Density and rhythm.** 28 px rows, 1 px borders, 4 px grid, 40 px top bar. Row labels and values align on one baseline column.
- **States.** Loading shows six labelled placeholder rows with short bars, error shows a clear message with one action, populated shows the data. The "empty" state does not apply to this screen.
- **Colour is not the only cue.** The API status pairs a square with the word "Reachable".

## Findings

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | **The screen is 75% empty and left-weighted.** The panel sits in the top-left corner of a 1440 px canvas. It reads as unfinished rather than as a deliberate minimal page. | Medium | Follow-up (wave 2: the real shell gives the canvas a structure) |
| 2 | **Type hierarchy was flat.** The only heading was an 11 px uppercase micro-label, the smallest text on the page. | Medium | **Fixed**: the heading is now 16 px semibold |
| 3 | **Fonts are system stacks, not IBM Plex.** Latin text renders in the platform UI font and values in the platform monospace; Hindi falls back to whichever Devanagari font the OS has, so the three scripts do not share a visual weight. | High for the quality bar | Follow-up (wave 2: self-hosted Plex Sans, Plex Mono and Noto Sans Devanagari) |
| 4 | **Hindi micro-labels were 11 px with tracking.** Matras are hard to read at that size. | Medium | **Fixed**: Hindi labels are 13 px with no tracking |
| 5 | **Loading placeholders spanned the full row width** (a missing size class), which looks like a progress bar rather than a pending value. | Low | **Fixed**: 96 px placeholders |
| 6 | **Tabular numerals.** Values use the platform monospace, which is tabular, so the version, commit and timestamp columns align. This only becomes a guarantee once Plex Mono is bundled with `tabular-nums`. The Latin sans text has no tabular setting. | Low | Follow-up (wave 2, with the fonts) |
| 7 | **The "Service" row repeats the name and descriptor already in the top bar.** "API status: Reachable" is also implied by the row data being there at all. | Low | Follow-up (wave 2: replace with real shell content) |
| 8 | **No logo mark in the header.** The favicon and the README banner carry a ring-and-bearing mark; the header has only a 2 px amber tick, so the identity is inconsistent. | Low | Follow-up (wave 2: add the mark as inline SVG) |
| 9 | **Icon approach.** None are used, which is consistent with "Carbon only". The language and theme controls are text segments, which is fine, but the first Carbon icons arrive in wave 2 and must be a single family and weight. | Info | Follow-up (wave 2) |
| 10 | **Error state is generic.** It does not say which request failed or show a status code. Acceptable for a placeholder; operators will want the endpoint and time. | Low | Follow-up (wave 2) |
| 11 | **Contrast.** Token contrast is unit-tested (text 4.5:1, UI 3:1) in both themes and axe reports zero violations in EN/HI × dark/light. The segmented-control borders in the light theme are faint, but the selected state is carried by text colour and background as well. | Info | No action |

## Does it look AI-generated?

Not in the usual ways (no gradients, glass, cards, emoji or stock icons). The remaining risk is the opposite one: with system fonts and a single table it looks like an unstyled admin page. The fixes that change that are the fonts and the shell, both in wave 2, and the review should be repeated on the wave 2 screens with the 12-screen visual snapshots.

## Follow-ups logged

Items 1, 3, 6, 7, 8, 9 and 10 are logged under Wave 1 in [../../BUILD_LOG.md](../../BUILD_LOG.md).
