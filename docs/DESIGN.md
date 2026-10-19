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

## Debrief (wave 6)

The Debrief (`apps/web/src/screens/Debrief.tsx`, route `/train/session/:id/debrief`) opens from the session-ended view and reads `GET /sessions/{id}/score`. It is a records screen inside the normal frame, not a dashboard: tables with captions, monospace tabular figures, 1 px borders, no tiles, charts, gradients or donuts.

- **Order.** The reference-scoring note and the ground-truth note first; then the score summary (session, decision and report score; d′, criterion, hit and false-alarm rates with counts, and the log-linear correction note when it was applied) beside the first three lessons and the record (scenario, versions, seed, rule pack); then one section per scored contact; then a quiet "Not scored" group.
- **Contact.** The heading names the real class and disposition ("Contact quad: Small rotary, hostile"), the only place ground truth is shown. A table gives each node's weight, points, mark and the reason as a sentence from the `scoring.*` templates (EN and HI), then the findings, then the report grades (reported against real, tolerance, weight, mark, reason).
- **Hard fail.** A banner with a heavy outline, a stop icon and the breach in words, above the path, with the contact score stated as 0. Colour reinforces it and is never the only cue.
- **Reasons.** `apps/web/src/live/scoring.ts` renders a key and its parameters by the rules in SCORING.md; a parameter the evaluator did not send shows as a dash. A test reads `services/api/app/scoring/keys.py` and fails when any key lacks an English or Hindi template.
- **States.** Loading, empty (no contact presented), 409 session not ended, 404 no record, network failure and a generic error, each with its own text.

The contact-report form is a dialog opened by "Report up the chain" in the Respond step: class (keys 1 to 4, 0 clears), bearing and range from the site, count, heading and confidence in percent. Position and heading start from the selected track. Fields are optional and checked against the simulation's ranges; "Skip details" files a bare report.

## RF and acoustic consoles (wave 8)

### RF and acoustic consoles (wave 8, Q-23)

Fragment for merging into `docs/DESIGN.md` under "Workspace". Code: `apps/web/src/live/consoles/` (models, drawing, feed), `apps/web/src/live/panels/SensorConsoles.tsx` (tabs and states).

**Place.** Two tabs directly under the radar PPI in the right column, above the track table: "RF spectrum" and "Acoustic spectrogram". The right column is 40 / 32 / remainder at 1080 px height and 38 / 34 / remainder at 900 px or less. The tab list is a real ARIA tablist (Left, Right, Home, End). Each console is a dark instrument plot on the left and a scrollable readout column on the right (a keyboard stop, because it scrolls), with a footer that always carries the honesty text. The plot is a dark recessed display in both themes; everything around it follows the theme.

**What is drawn, and from what.** The server sends no raw spectra. A frame's `reports` are the only input, and only what a report carries is used: no bearing, class or identity ground truth, and no list of RF "drone names". Each report keeps painting for a short hold (RF 1.25 s, acoustic 0.75 s), and the display advances in scenario time at 4 rows per second (0.25 s per row, 30 s shown, newest row at the top). Rows advance on each frame whether or not the tab is showing, so history is complete after a tab switch. Pausing or losing frames stops the scroll, because it follows `time_s`.

- **RF.** Five equal band windows side by side in ascending frequency (433 MHz, 900 MHz, 1.2-1.3 GHz, 2.4 GHz, 5.8 GHz; centres from `services/api/sim/sensors/rf.py` `BANDS`), not one continuous axis. Above, a spectrum line in dBm from -100 to -50 with a dashed noise floor at -95 dBm and a falling peak-hold trace; below, a waterfall through the inferno map. A fixed link is a narrow carrier at `rssi_dbm` in its window. A hopping link steps across 16 hop positions at `hop_rate_hz` (at most 12 hops drawn per row; 8 Hz if the report says "hopping" without a rate), which smears across the window in the peak-hold trace and the waterfall. A band label the display has no window for is listed in the table and not drawn.
- **Acoustic.** A spectrogram from 0 to 2000 Hz, linear, 5 Hz bins, through the same inferno map. Lines at `blade_pass_hz` and k times it up to `harmonics` (and up to 2 kHz), each 3 dB weaker per order, intensity from `snr_db` over 0 to 40 dB above the noise floor. Triangles along the top edge mark the harmonic lines of the latest reports.
- **Cursor (acoustic).** Left and Right move it 5 Hz, with Shift 50 Hz, kept on the scale; it survives a tab switch. The readout gives the frequency, the nearest harmonic among the latest reports (order capped at the reported harmonic count, ties to the stronger report) with its offset, and the implied blade-pass rate (cursor divided by that order). A polite live region announces each move.

**Display decisions that are not measurements, stated in the legend.** The noise texture, the carrier slot inside a band window (chosen from the report's 45 degree bearing sector, only to keep two links in one band apart), the hop order and the line widths are drawn by the display. They are deterministic (an integer hash), so the same reports give the same picture.

**Honesty text, English and Hindi, always visible in the console footer.** "Synthesised from sensor reports · reference data" (or "... verified data" or "... reference and verified data", following the `data_status` of the sensors and reports the picture was built from). The RF console adds "RF is not occluded by terrain in this model. A link behind a ridge or building is still heard here." (Q-25, as in `SENSOR_MODELS.md`).

**Four states per console.**
- Populated: plot, status line, report table.
- Empty: a scenario without that sensor keeps the tab, marks it "unavailable" in the tab and explains in the panel. A sensor present with nothing heard shows the noise floor and "Listening: nothing heard yet".
- Loading: before the first frame, the app loading state.
- Error: a closed link before any frame uses the app error state (with Reload). After frames, a dropped link or no frame for 3 s while running freezes the display, draws a boxed "STALE" mark on the plot and shows the app warning alert with the scenario time of the last frame. A sensor in outage says so and draws only the floor.

**Not colour alone.** Every colour map has a numeric colour bar and range; a text table lists the latest reports (RF: band, level, link, bearing; acoustic: blade-pass, harmonics, tonal, SNR, bearing); the cursor is a dashed line with a flag at each end.

**Cost on the floor laptop.** 2D canvas only. A requestAnimationFrame loop runs only while the tab is showing and the document is visible, and draws only when the model, the cursor, the stale state or the size changed (about 4 times a second). Under `prefers-reduced-motion` the picture is redrawn at most once a second, except that a cursor key redraws at once. History lives in typed-array rings (`RowRing`, 120 rows), the bitmap is updated one row at a time, and nothing is allocated per frame in the draw path.

**Keys.** Added to the shortcuts dialog: Left, Right, Home, End on the tab list; Left, Right and Shift+Left, Right on the spectrogram.

**EO terrain notice (Q-26).** Under "Terrain: {name} · reference data" the EO view now says "Building heights are generic defaults where the source has no height." When the terrain manifest carries `buildings.height_source.default`, the line gives that count instead ("N building heights are generic defaults, because the source has no height for them.").

**Scripted session.** `live/mock.ts` gains `acoustic-1` (a perimeter microphone array north-east of the site, mock range 330 m) that hears the closing rotary contact in the second half of the run. Unit tests (`tests/live/consoles.test.ts`, `sensorConsoles.test.tsx`) cover the models and the states; `e2e/mock/consoles.spec.ts` covers the tabs, keyboard, honesty text, canvas ink, 1366 x 768 and axe in both languages and themes. `e2e/mock/fixtures.ts` gains `trackRows`, because the console report tables now precede the track table in the page.

## Target meshes (wave 8)

Source: `apps/web/src/live/views/eoMeshes.ts`, `eoHold.ts`, `eoScene.ts`. For the main session to fold into the build log, the engine notes and the traceability matrix.

### Classification vocabulary

The Classify step offers nine classes, in the order the welcome message sends them (`operator_classes`): rotary-small, fixed-wing-small, bird, unknown, fpv-small, fixed-wing-medium, fixed-wing-large, kite, balloon. Keys 1 to 9 pick them in that order; the first four keep their old keys. English and Hindi labels exist for all nine under `live.class.*`. The Hindi strings are an unreviewed draft (Q-15) and are in `docs/i18n/HI_REVIEW.md`. Truth class ids (autonomous-small, decoy-small, civil-drone and so on) are never sent to the browser and have no label or mesh.

### Shapes

The EO view draws one low-poly model per reported class. A report with no class, a coarse family or any other value is drawn as a generic point, as before. Models are unit-size and flat-shaded; the scene scales each to the angular size its pixel count implies.

| Shape | Silhouette | Triangles | Animation | Thermal look |
|---|---|---|---|---|
| rotary-small | body, crossed arms, four rotors | 68 | rotor blades spin | rotors hot, body warm, frame cooler |
| fpv-small | elongated body, battery slab, short thick arms, small props | 80 | rotor blades spin | as rotary-small |
| fixed-wing-small | fuselage, wing, tailplane, fin, nose propeller | 52 | propeller spins | fuselage (engine) hot, wing and tail cool |
| fixed-wing-medium | longer fuselage, larger span | 52 | propeller spins | as small |
| fixed-wing-large | central pod, widest wing, twin booms, tail bridge | 88 | propeller spins | pod hot, booms and tail cool |
| bird | body and two wings | 36 | wings flap | warm body, mid wings |
| kite | diamond of cloth, faint tether, no body | 8 | slight roll | cold: nearly invisible in white-hot |
| balloon | ellipsoid | 80 | slow vertical bob | cold: nearly invisible in white-hot |
| point | icosahedron fallback | 20 | none | hot |

Thermal is a rendering model, not radiometric: the vertex heat factor scales the same emissive value the scene already derived from the clock.

### Instancing

- One `THREE.InstancedMesh` per shape (nine), each with capacity 64 (`TARGET_CAPACITY`), created once when the scene is built. A shape's mesh is hidden while it has no contacts, so a frame costs one draw call per shape in use.
- Each model is one merged, non-indexed geometry. Per-vertex attributes carry what moves and how warm it is: `aPart` (hub position and motion kind) and `aHeat`. One per-instance attribute, `aAngle`, carries the animation angle. A small `onBeforeCompile` patch on the shared target material rotates animated vertices about their hub and scales emission by heat; it is the only shader change.
- A frame is `begin()`, `place()` per report, `end()`. `place()` writes the instance matrix and angle in place from a reused `Object3D`. No geometry, material or vector is created or disposed per report or per frame; contacts beyond 64 in one shape are not drawn. Teardown disposes every geometry once.
- `SceneStats` gains `targetsDrawn`, `targetTriangles` and `targetShapes` (the existing `triangles` and `drawCalls` still come from the renderer). The EO view mirrors the shapes on screen in a `data-shapes` attribute, written only when the set changes, for the mock e2e specs and support.

### Animation

All of it is a pure function of the report key and the clock, so it is deterministic and replays identically.

- Bird wings: 12 Hz real wing-beat drawn at a quarter of the rate (3 Hz) so a 60 Hz screen can show it; angle from -0.35 to +0.8 rad, phase offset from the key.
- Rotors and propellers: 2.5 revolutions per second as a visual cue (a real rotor is far above frame rate).
- Balloon: 0.06 model units of vertical bob, 7 s period.

### Cost

The largest model is 88 triangles, so 64 contacts of any one shape submit at most 5,632 triangles (the unit test asserts under 6,000). Typical frames are a handful of contacts. Memory is nine small geometries and 9 x 64 matrices; there is no per-frame allocation. Triangles per frame are visible in `SceneStats` for the bench. No benchmark was run for this change; it adds no performance claim.

### Mock session

`MOCK_WELCOME.operator_classes` is the nine ids and the mock now refuses a classify whose class is not in that list (as the server does). The dev-only `?mock=1&eoclass=<id>` variant reports every EO contact as that class so each model can be exercised end to end (`e2e/mock/classes.spec.ts`); it is stripped from production builds with the rest of the mock.
