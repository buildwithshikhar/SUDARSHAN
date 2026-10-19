## RF and acoustic consoles (wave 8, Q-23)

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
