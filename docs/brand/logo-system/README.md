# Mark's Cinematic Universe — logo system

## Assets

| Asset | Use | Minimum recommended size |
|---|---|---:|
| `hero-photo-five-v3.png` | Spacious primary hero for splash screens and presentation artwork | 600 px wide |
| `hero-photo-five-v3-web.png` | Web-optimised spacious hero | 360 px wide |
| `hero-photo-five-v3-compact.png` | Compact primary hero for in-app surfaces | 600 px wide |
| `hero-photo-five-v3-compact-web.png` | Web-optimised compact hero | 360 px wide |
| `hero-photo-v3.png` | Thirteen-image collector's edition for gifts and large presentation surfaces | 900 px wide |
| `hero-photo-v3-web.png` | Web-optimised collector's-edition export | 600 px wide |
| `stack-family/app-icon-concept-art-{192,512,1024}.png` | Selected app and home-screen icon | Native export |
| `stack-family/personalised-poster-icon-{128,192,512,1024}.png` | Private poster-art edition | 192 px square |
| `stack-family/stack-mark.svg` / `stack-mark-light.svg` | Selected display three-case-and-disc mark | 128 px square |
| `stack-family/stack-mark-compact.svg` / `stack-mark-compact-light.svg` | Optically strengthened compact mark | 32 px square |
| `stack-family/micro-mark-16.svg` / `favicon.ico` | Browser tab and very small UI | 16 px square |
| `stack-family/horizontal-lockup-{dark,light}.svg` | Navigation, footer and compact brand lockup | 280 px wide |
| `stack-family/stacked-lockup-{dark,light}.svg` | Square login and profile lockup | 320 px square |
| `stack-family/stack-mark-mono-{black,white}.svg` | One-colour print, engraving and watermark | Application-dependent |
| `responsive/wordmark-primary-{dark,light}.svg` | Full desktop navigation wordmark | 240 px wide |
| `responsive/wordmark-compact-{dark,light}.svg` | `MARK'S` mobile-navigation wordmark | 120 px wide |
| `responsive/social-card-1200x630.png` | Link-preview and sharing artwork | Native size |

The photographic heroes are intentionally tribute artwork as well as brand marks. Do not
use them as favicons or squeeze them into the sidebar: below their recommended sizes, the
photographs become texture rather than identifiable references. The path-based wordmarks
contain no live text or font dependency and have genuine transparent backgrounds.
The selected compact system, platform exports and detailed usage matrix are documented in
[`stack-family/README.md`](stack-family/README.md). The path-based wordmarks remain active.
The earlier abstract monogram and root-level marks are retained as superseded design history.

## Primary hero image map

- **M:** *Jaws*
- **A:** Humphrey Bogart
- **R:** *Double Indemnity* — Fred MacMurray and Barbara Stanwyck together
- **K:** Alfred Hitchcock
- **S:** *An American Werewolf in London*

The five-image edition is the default because each letter has one clear idea and remains
legible at smaller hero sizes. Cyan on the M and moonlit indigo on the S bookend the
monochrome centre. A single frame, no underline, compact possessive mark and controlled
subtitle tracking keep the composition cinematic without unnecessary ornament. The v3 A
uses a restrained triangular counter with the same burgundy, black and gold construction
as the R counter. Its central photographs share one warm noir grade; Hitchcock's midtones
are lifted for recognition, while the werewolf's colour and highlights are restrained.
The apostrophe is smaller, solid gold and optically closer to the S. Earlier five-image
passes remain available as superseded design history.

Use the spacious version where a ceremonial, poster-like presentation is appropriate.
Use the compact version in the app when vertical space is limited; its border and subtitle
have been rebalanced rather than mechanically cropped.

## Collector's-edition image map

- **M:** *Jaws*; *An American Werewolf in London*; *Double Indemnity*
- **A:** Humphrey Bogart; James Stewart
- **R:** Edward G. Robinson; Barbara Stanwyck; Cary Grant
- **K:** Alfred Hitchcock; *The 39 Steps* (Madeleine Carroll above, Robert Donat below)
- **S:** Bette Davis; Alastair Sim; Clint Eastwood

The thirteen-image v3 refinement uses a single frame, no subtitle underline, tighter
subtitle tracking, a smaller possessive mark placed closer to the S, a quieter shared
colour grade, and crop boundaries that avoid the centres of faces wherever the letter
geometry permits.

## Colour

| Token | Value | Use |
|---|---|---|
| Near black | `#0A0A0B` | Dark surfaces and icon field |
| Crimson | `#B8475E` | Hero field and restrained accent |
| Champagne gold | `#D4AF7F` | Primary brand mark and keylines |
| Off-white | `#FAFAFA` | Supporting type on dark surfaces |
| Light background | `#FAFAF9` | Light-mode surfaces |
| Light-mode ink | `#18181B` | Supporting type on light surfaces |

## Clear space

- Hero: preserve at least the distance between the outer frame and the M on every side.
- Wordmark: preserve clear space equal to the height of the apostrophe.
- Monogram: do not place any element inside the icon's existing gold inset keyline.

## Restrictions

- Do not recolour individual photographic slices independently.
- Do not add additional frames, shadows, bevels or glow.
- Do not place the dark-surface wordmark on a light background, or vice versa.
- Do not use the photographic hero where the monogram or compact wordmark is specified.
- Do not remove the TMDB attribution or treat the source manifest as rights clearance.

Source-image provenance and attribution are recorded in
[`../photo-logo-five-sources-v1.md`](../photo-logo-five-sources-v1.md) for the primary
hero and [`../photo-logo-sources-v2.md`](../photo-logo-sources-v2.md) for the
collector's edition.
