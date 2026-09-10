# Responsive identity assets

> Superseded: the abstract MCU monogram in this directory was exploratory. The selected compact identity is the three-case-and-disc system in [`../stack-family/README.md`](../stack-family/README.md). Retain these files as design history; do not use them for new implementation.

This directory contains the production logo family derived from the photographic
`MARK'S CINEMATIC UNIVERSE` hero. The system changes complexity deliberately as the
available space becomes smaller; no single mark is expected to cover every context.

## Usage hierarchy

| Context | Preferred asset | Minimum size |
|---|---|---:|
| Splash screen or presentation | `../hero-photo-five-v3.png` | 600 px wide |
| In-app photographic hero | `../hero-photo-five-v3-compact.png` | 600 px wide |
| Desktop header | `wordmark-primary-{dark,light}.svg` | 240 px wide |
| Mobile header | `wordmark-compact-{dark,light}.svg` | 120 px wide |
| Square login or profile surface | `stacked-lockup-{dark,light}.svg` | 320 px square |
| App and home-screen icon | `app-icon.svg` | 64 px square |
| Favicon or very small UI | `micro-mark.svg` | 16–48 px square |
| Print, embossing or watermark | matching `mono-black` or `mono-white` SVG | Application-dependent |
| Link preview | `social-card-1200x630.png` | Native size |

## Core masters

- `wordmark-primary-{dark,light}.svg`: full everyday wordmark with subtitle.
- `wordmark-compact-{dark,light}.svg`: `MARK'S` only for constrained navigation.
- `micro-mark.svg` / `micro-mark-light.svg`: simplified M and possessive accent.
- `display-monogram-v2.svg` / `display-monogram-v2-light.svg`: detailed MCU
  monogram for display sizes.
- `stacked-lockup-{dark,light}.svg`: square monogram-and-wordmark composition.

The primary, compact and stacked SVGs contain paths rather than live text. They do not
depend on local fonts. PNG companions are supplied for applications without SVG support.

## Platform exports

- `favicon.ico`: multi-image 16, 32 and 48 px favicon.
- `micro-mark-{16,32,48,64}.png`: exact-size UI exports. The 16 px version has
  separately drawn, pixel-hinted geometry rather than being a naive downscale.
- `apple-touch-icon.png`: opaque 180 px home-screen icon.
- `app-icon-{192,512,1024}.png`: full-bleed standard app icons.
- `app-icon-maskable-{192,512}.png`: protected safe-area exports for maskable PWA use.
- `app-icon.svg` / `app-icon-maskable.svg`: platform-icon vector masters.

The micro M is reserved for browser tabs and very small controls. App icons use the richer
display monogram because home-screen sizes can sustain its C/U construction.

## One-colour family

The `wordmark`, `wordmark-compact`, `micro-mark` and `display-monogram` families each
include `mono-black` and `mono-white` SVG masters. Use these where reproduction permits
only one ink, where photography is inappropriate, or where maximum contrast is required.

Do not approximate a one-colour mark by converting a coloured PNG to grayscale.

## Clear space and restrictions

- Preserve clear space around a wordmark equal to the apostrophe height.
- Do not add the subtitle back to the compact wordmark.
- Do not place the display monogram below 64 px or the photographic hero below 600 px.
- Do not add a frame to the micro mark; the simplified silhouette is intentional.
- Do not round the app-icon bitmap manually. The operating system supplies its own mask.
- Do not recolour the burgundy/gold marks outside the documented brand palette.
- Do not use the photographic hero as a favicon, navigation logo or app icon.

## Rebuilding

`../build_identity_system.cjs` generates this directory from the path-based wordmark and
the approved geometry. It requires Node.js and `sharp`. The generated files should be
visually checked at 16, 32, 64, 120 and 240 px whenever the masters change.
