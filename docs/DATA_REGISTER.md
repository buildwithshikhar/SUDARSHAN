# Data register

Working register for the build. The full research notes, sizes and source URLs are in [03-data-register.md](03-data-register.md); this file is the operational view: what we may ship, what is calibration-only, and what is still unconfirmed. Researched 2026-10-17 from official pages; nothing has been downloaded.

## Policy

1. **Calibrated from, never trained on.** We derive numeric parameters (RCS ranges, band plans, blade-pass harmonics, apparent-size curves) and cite them. Pitch wording: "parameters calibrated from published open research datasets".
2. **Raw samples ship only under a confirmed open licence** (CC0, CC BY, ODbL with attribution and share-alike, or equivalent), confirmed on the source page.
3. **NC, R and "licence not stated" sources are calibration-only.** They are never redistributed and never shown as clips in the app or the deck. A repo code licence (MIT, Apache) does not cover the data.
4. **Every parameter cites a register ID** in its sensor profile or threat file; the loader rejects parameters without one.
5. **Licence status is re-checked before each release.** Raw downloads live in `data/raw/`, which git ignores.
6. **Shipping terrain packs** (G01, G02) require the attribution files described in wave 7.

NC = non-commercial. R = research or academic use only. "Needs verification" lists what is unconfirmed; items are tracked in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## Register

| ID | Dataset | Modality | Licence as found | May ship? | Calibration only? | Needs verification |
|---|---|---|---|---|---|---|
| D01 | Anti-UAV (v1 / 300) | RGB + thermal video | Data licence not stated; "academic research" release; repo MIT (code only) | No | Yes: apparent size and contrast vs range | Data licence; frame count |
| D02 | Anti-UAV410 | Thermal IR video | Not stated (academic release) | No | Yes | Data licence |
| D03 | Anti-UAV600 / workshop tracks | Thermal IR video | Not stated | No | Yes: multi-target scenes | Data licence; sizes in frames and version |
| D04 | DUT Anti-UAV | RGB images and video | Data not stated; repo Apache-2.0 (code only) | No | Yes: daylight EO appearance | Data licence |
| D05 | MAV-VID | RGB video | Not stated | No | Yes | Licence (Kaggle page did not load) |
| D06 | Drone-vs-Bird (WOSDETC) | RGB video | Data usage agreement, research and non-commercial only (NC/R) | No | Yes, under the agreement | Current dataset size; exact agreement text; whether signing is needed for parameter extraction |
| D07 | Det-Fly | RGB images, air to air | Data not stated; repo MIT (code only); citation requested | No | Yes | Data licence |
| D08 | DroneRF | Raw RF, 2.4 GHz | Article CC BY; Mendeley data licence field blank | No (until confirmed) | Yes: RF detector parameters | Data licence on Mendeley |
| D09 | CardRF | RF (.mat) | Not stated; mixed access | No | Yes: Wi-Fi and Bluetooth confusers | Licence; true sampling rate |
| D10 | DroneAudioDataset | Audio | Not stated; contains third-party ESC-50 and Speech Commands clips | No | Yes: rotor acoustic signature | Licence; third-party clip terms |
| D11 | DREGON | Mic array on quadrotor | Free for academic and educational purpose (R) | No | Yes | Size, duration, sample rate, download terms |
| D12 | Svanström multi-sensor set | IR, visible, audio | Zenodo "Other (Open)"; article CC BY | Only after exact wording is confirmed | Yes: best confuser set | Exact Zenodo licence wording |
| D13 | DIAT-µSAT | X-band micro-Doppler images | No licence named; academic research only (R) | No | Yes: Indian micro-Doppler reference | Licence terms; access route (DataPort subscription) |
| D14 | KTH/SAAB 77 GHz radar | FMCW radar (.mat) | CC BY 4.0 | Yes, with attribution (derived extracts) | Yes: drone vs bird returns, RCS reference | None (confirmed on source page 2026-10-17) |
| D15 | NYU 60 GHz radar | FMCW radar | Not stated; "Open Access" with login | No | Yes | Licence |
| D16 | MAFAT Radar Challenge | Doppler I/Q, humans vs animals | Not stated | No | Yes: ground-clutter realism only | Terms (CodaLab T&C unreadable) |
| D17 | "Real Doppler RAD-DAR" | Radar | Dataset not found | No | No | Does it exist? Drop unless the user supplies a link |
| D18 | FBD-SV-2024 | RGB video, flying birds | Figshare: learning and research only (NC/R) | No | Yes: bird clutter | None beyond NC/R restriction |
| G01 | NASA SRTM GL1 v003 | DEM 30 m | Shared without restriction (EOSDIS guidance) | Yes, with citation | Yes | None |
| G02 | OpenStreetMap | Vector map data | ODbL (attribution and share-alike) | Yes, derived terrain packs under ODbL with "© OpenStreetMap contributors" | Yes | How share-alike applies to a bundled pack (confirm before release) |
| G03 | ISRO Bhuvan / NRSC | EO imagery, layers, DEM | Non-commercial, attribution "Source: NRSC, ISRO/DOS" (NC) | No | Yes, non-commercial demo only | Bhuvan-specific terms page not read |
| W01 | ERA5 (Copernicus C3S) | Reanalysis weather | CC-BY | Yes, with attribution | Yes | None |
| W02 | NOAA GFS (NODD) | NWP forecast | Open; attribution requested; no implied endorsement | Yes, with attribution | Yes | None (use noaa-gfs-bdp-pds bucket) |
| W03 | NOAA ISD | Station observations | Same NODD terms as W02 | Yes, with attribution | Yes | None |
| W04 | IMD gridded data | Rainfall, temperature | IMD site: not stated; data.gov.in copies under GODL-India | Not until confirmed | Yes | IMD site licence; full GODL-India text |
| X01 | UAV Database (NTNU) | Specification table, 93 UAVs | CC0 1.0 | Yes | Yes: threat envelopes | Type skew toward fixed-wing and research UAVs |

## Summary

- **May ship (with attribution):** D14, G01, G02, W01, W02, W03, X01. D12 only after the exact licence wording is confirmed.
- **Calibration-only:** D01–D11, D13, D15, D16, D18, G03. D08, D12 and W04 may move to "may ship" once their licences are confirmed.
- **Not found:** D17.
