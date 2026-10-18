# Design system

The rules every screen follows. The full direction, with the reasoning, is in [07-ui-map.md](07-ui-map.md); this file is the working reference and the guard against software that looks generated. Tokens are implemented in `apps/web/src/styles/tokens.css`; a unit test checks their contrast.

## Tokens

Dark operations theme is primary; the light theme is selected with `data-theme="light"` and is tested in CI.

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | #0B0E11 | #F5F6F7 | app background |
| `surface-1` | #12161A | #FFFFFF | panels |
| `surface-2` | #1A1F24 | #EEF0F2 | raised and inset |
| `border` | #272D34 | #D5D9DE | 1 px dividers |
| `text` | #E4E7EA | #14181C | primary text |
| `text-2` | #9BA4AE | #4F5862 | secondary text |
| `accent` | #4FB6C2 | #1F7480 | focus, selection, primary action; the only interactive hue |
| `signal` | #E0A526 | #9A6A00 | brand tick and warnings only |
| `track-hostile` | #E5484D | #C62B30 | track affiliation |
| `track-suspect` | #EE8A45 | #B85A14 | track affiliation |
| `track-unknown` | #E6C84F | #8C7400 | track affiliation |
| `track-neutral` | #5DB46E | #2E7D3E | track affiliation |
| `track-friend` | #5B9BD5 | #2F6EA8 | track affiliation |

Colour is never the only cue: pair it with a shape and a text label. Text pairs meet 4.5:1 and UI marks 3:1, in both themes.

## Type, space, shape

- IBM Plex Sans for the interface, IBM Plex Mono with tabular figures for numbers, clocks, coordinates and logs, Noto Sans Devanagari for Hindi. All three are self-hosted and bundled (sources and licences in [FONTS.md](FONTS.md)); system fonts are fallbacks only.
- Scale 11 / 12 / 13 / 14 / 16 / 20 (Tailwind `2xs` to `lg`); 13 px base on dense operations screens, 14 px elsewhere. Uppercase only for 11 px micro-labels with +6% tracking.
- 4 px grid (4, 8, 12, 16, 24, 32, 48). Controls have a 2 px radius, panels 4 px. Panels are separated by 1 px borders, not shadows.
- Icons: IBM Carbon only, 16 and 20 px, one stroke style. They appear where they carry meaning (alerts, empty and error states, sign out), not inside every button; navigation is text.
- Motion: 120–160 ms ease-out for state changes only, and none under `prefers-reduced-motion`.

## Shell and components (wave 2)

- **Frame.** A 40 px top bar (brand mark, role, account, language, theme, sign out), a 232 px sidebar grouped by the role's modules with a 2 px accent bar on the active item, a content area with a page header (path in mono, title at 20 px), and a status strip with the permanent scenario label, build version and an About link.
- **Brand mark.** A monogram in a ring-and-bearing frame; the letter comes from `brand.json`, so a rename follows.
- **Components** (`apps/web/src/ui/`): Button (primary, secondary, ghost), Input, Select, Checkbox, Panel, Table (28 px compact and 36 px comfortable rows), Tabs (arrow, Home and End keys), Dialog (native `<dialog>`), Badge, InlineAlert, Tooltip, Segmented, EmptyState, LoadingState, ErrorState. In demo mode `/dev/components` shows them all.
- **Sidebar source.** One list in `apps/web/src/nav/modules.ts` matches `07-ui-map.md` (trainee 3 groups and 6 modules, instructor 4 and 10, admin 3 and 8, plus a shared Account group); a test pins the counts. A module whose wave has not shipped shows an empty state naming that wave.
- **Honest content.** The first screen after sign-in is Status: the build, the session, and a table of the role's modules with the wave that delivers each.

## Rules for every screen

1. Populated, empty, loading and error states, each designed.
2. Keyboard-operable with a visible focus ring in the accent colour; skip link on every page.
3. WCAG AA; axe reports zero violations in English and Hindi, dark and light.
4. All strings through i18n with English and Hindi keys; a test fails on a missing key.
5. Domain nouns for labels ("Build status", "Track table"), written in short, exact operator language.
6. The label "Fictional scenarios · open-source parameters" is always visible, and seeded data is labelled "reference data".
7. Tailwind's default palette is removed; colours come from the tokens only.

## Banned

1. Purple or blue gradient heroes, gradient text, glow borders, glassmorphism, frosted cards.
2. A "welcome back" header, emoji as icons, sparkle "AI" badges.
3. Three equal feature cards, KPI tiles with tiny up-arrows on every page, bento grids.
4. Default Tailwind or shadcn look shipped unchanged (slate on white, `rounded-xl`, `shadow-lg`, Inter at every size, indigo buttons).
5. Lorem ipsum, "John Doe", round-number fake data, identical sparklines.
6. Mixed icon sets, an icon in every button, cartoon illustrations of robots or drones.
7. Large padding and low density on operational screens; centred layouts for tools.
8. Generic labels ("Dashboard", "Analytics", "Insights") in place of domain nouns.
9. Tooltips that restate the label, toast spam, confetti.
10. Marketing copy.

## Workspace (wave 5)

The live session workspace (`apps/web/src/screens/LiveSession.tsx`, panels and views in `apps/web/src/live/`) is a full-screen frame without the sidebar. It is a fixed 12-column grid: EO view in 7 columns on the left; radar PPI and track table in 5 on the right; a decision strip across the bottom. At 1366 × 768 the strip is 208 px, the PPI takes half the right column, and some figures drop out (weather and light in the top bar, heading and sensor columns in the track table, icon-only End and Leave) rather than wrapping.

- **Top bar (32 px).** UTC and scenario time, light, weather, ROE pack id and version, link state with latency, and the permanent label. No preference switches here: language and theme are set before the session.
- **EO view.** Three.js `WebGLRenderer`, drawn from EO and IR reports only, each held for 0.4 s. A report has bearing, elevation and apparent pixels, never a range, so the model is placed on a drawing sphere around the camera at the angular size `apparent_px × fov / 1920`, never at a distance. Below recognition the mesh is a generic point. The reticle, angular scale and zoom ladder are SVG; marks are drawn twice (dark underlay, light mark) so they read on both sky and ground. Zoom is the sensor's real field of view: it narrows only through a `sensor-cue` action.
- **Radar PPI.** Canvas at device pixel ratio. The sweep turns once per 1.2 s radar period from the scenario clock; a plot is painted when the beam passes its bearing and fades with a 1.5 s time constant. Scope range is the outer zone plus a quarter in 500 m steps; rings are labelled in km.
- **Track symbols.** One frame shape per assessed identity, drawn by us and not APP-6 or MIL-STD-2525: friend rectangle, neutral square, hostile diamond, suspect dashed diamond, unknown quatrefoil. A tentative track is dashed, a coasting one has a bar, a selected one has corner brackets. A track is unknown until the operator assesses it.
- **Reference data.** Every track row carries a `REF` marker and the table footer says what it means. The same marker sits in the selected-track detail.
- **Blocked response.** The verdict panel shows BLOCKED in words, with a stop icon and a heavy outline, the rule title in the interface language, the pack id and version, and a table of each unmet condition (condition, required, actual). It stays until dismissed (button or `X`) or replaced by the next response verdict; classify and assess verdicts do not replace it.
- **Keyboard.** `C A R` open the steps, `1`–`9` choose, `Enter` commits, `Esc` cancels, `H` holds fire, `U` cues the EO sensor, `L M S D` relabel, merge, split and drop (drop asks first), `X` dismisses the verdict, `?` lists them. Space is unused. `Tab` and `Shift+Tab` step through the tracks only while no control has focus, and give `Tab` back to the browser at either end of the list so the keys never trap a keyboard user; an idle `Esc` returns focus to the workspace.
- **Reduced motion.** The sweep is a measuring instrument, so it keeps turning. Under `prefers-reduced-motion` the decorative persistence wedge behind it is dropped and no state change is eased.
- **Light theme.** The canvas views read the same tokens as the rest of the interface (`theme.ts`) and redraw when the theme changes.

## Review

From wave 2 a Playwright visual-snapshot set covers the 12 key screens and is reviewed against this list every wave.
