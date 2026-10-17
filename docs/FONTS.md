# Fonts and icons

All typefaces and icons are bundled with the application by the build. Nothing is loaded from a font or icon CDN, so the interface renders identically offline.

| Asset | Used for | Source | Version | Licence | Licence text |
|---|---|---|---|---|---|
| IBM Plex Sans (Latin, 400 / 500 / 600) | interface text | npm `@fontsource/ibm-plex-sans` | 5.3.0 | SIL Open Font License 1.1 | [IBM-Plex-Sans-OFL-1.1.txt](../apps/web/public/licenses/IBM-Plex-Sans-OFL-1.1.txt) |
| IBM Plex Mono (Latin, 400 / 500) | numbers, clocks, coordinates, logs | npm `@fontsource/ibm-plex-mono` | 5.3.0 | SIL Open Font License 1.1 | [IBM-Plex-Mono-OFL-1.1.txt](../apps/web/public/licenses/IBM-Plex-Mono-OFL-1.1.txt) |
| Noto Sans Devanagari (400 / 600) | Hindi text | npm `@fontsource/noto-sans-devanagari` | 5.3.0 | SIL Open Font License 1.1 | [Noto-Sans-Devanagari-OFL-1.1.txt](../apps/web/public/licenses/Noto-Sans-Devanagari-OFL-1.1.txt) |
| IBM Carbon icons (`@carbon/icons-react`) | the few icons in the interface | npm | see `apps/web/package.json` | Apache License 2.0 | [Carbon-icons-Apache-2.0.txt](../apps/web/public/licenses/Carbon-icons-Apache-2.0.txt) |

The font files come from the Fontsource packages, which repackage the upstream fonts under their original licence; the licence texts above are copied from those packages and are served with the application at `/licenses/`.

## Notes

- Only the subsets in use are bundled: Latin for Plex, Devanagari for Noto. Other scripts fall back to system fonts.
- Numerals are tabular everywhere (`font-variant-numeric: tabular-nums`), and values are set in Plex Mono.
- The OFL permits bundling and redistribution with software. It does not allow selling the fonts on their own, and a modified font may not use the reserved font name; we do not modify the fonts.
- Re-check the licences when the packages are upgraded (see [RELEASE.md](RELEASE.md)).
