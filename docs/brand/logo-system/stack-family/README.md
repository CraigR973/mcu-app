# Selected three-case + disc identity

This is the production compact-logo family for Mark's Cinematic Universe. It develops the selected three-overlapping-case concept into a responsive system: rich artwork at display size, simplified vector geometry in compact UI, and pixel-hinted geometry at favicon size.

The wide photographic `MARK'S CINEMATIC UNIVERSE` hero remains the ceremonial primary logo. This family handles square, compact and platform-icon contexts.

## Usage hierarchy

| Context | Preferred asset | Minimum size |
| --- | --- | ---: |
| Large square brand presentation | `app-icon-concept-art-1024.png` | 192 px |
| Private personalised presentation | `personalised-poster-icon-1024.png` | 192 px |
| Standard app/home-screen icon | `app-icon-concept-art-{192,384,512,1024}.png` | Native export |
| Maskable PWA icon | `app-icon-concept-art-maskable-{192,512}.png` | Native export |
| Apple touch icon | `apple-touch-icon.png` | 180 px |
| Notification badge and one-colour mask | `notification-badge-{72,96}.png` | Native export |
| Link preview and sharing | `social-card-1200x630.png` | Native export |
| Medium UI mark | `stack-mark.svg` or `stack-mark-light.svg` | 128 px |
| Compact UI mark | `stack-mark-compact.svg` or `stack-mark-compact-light.svg` | 32 px |
| Browser favicon | `favicon.ico` | 16 px |
| Horizontal navigation or footer | `horizontal-lockup-{dark,light}.svg` | 280 px wide |
| Square login/profile lockup | `stacked-lockup-{dark,light}.svg` | 320 px square |
| One-colour print, engraving or watermark | `stack-mark-mono-{black,white}.svg` | Application-dependent |

## Core assets

### Concept-art master

`app-icon-concept-art-*` is the default rich emblem. Its three text-free illustrations share one mid-century screen-print language: ocean suspense, classic noir and moonlit London horror. It is more cohesive and ownable than the poster edition while retaining the personality of Mark's favourites. `app-icon-concept-art-clean-master.png` is the edge-cleaned archival raster from which the fixed-size exports are derived.

### Personalised poster edition

`personalised-poster-icon-*` uses authentic crops from *Jaws*, *Double Indemnity* and *An American Werewolf in London*. It is reserved for private, internal and commemorative surfaces. It is not the rights-independent public identity. `personalised-poster-clean-master.png` is its cleaned archival raster.

### Simplified vector

`stack-mark.svg` removes all cover imagery while preserving the three cases, M-like top silhouette, central burgundy case and exposed optical-disc hub. Its centre case is deliberately narrower than the first prototype, revealing more of two optically equal rear cases and giving the M silhouette a clearer central notch.

- `stack-mark-light.svg` is optically recoloured for light surfaces.
- `stack-mark-compact.svg` and `stack-mark-compact-light.svg` use heavier, separately drawn geometry for 32–96 px rather than mechanically reducing the display master.
- `stack-mark-maskable.svg` protects the geometry inside a platform-safe area.
- `stack-mark-mono-black.svg` and `stack-mark-mono-white.svg` are genuine one-colour outline masters.
- `stack-mark-mono-{black,white}-512.png` are transparent raster companions.
- `stack-mark-{32,48,64,96,128,192,512,1024}.png` are fixed-size exports.

### Micro mark

`micro-mark-16.svg` is separately drawn on a 16×16 grid. It prioritises the M silhouette and central burgundy case, deliberately omitting the disc where its hub cannot survive. It is not a mechanical reduction of the display artwork. The 32, 48 and 64 px micro exports use the compact optical master; together they form `micro-mark-{16,32,48,64}.png` and the multi-image `favicon.ico` browser/UI set.

`micro-mark-mono-white.svg` and `micro-mark-mono-black.svg` are the micro mark in one colour: the same 16-grid geometry with the centre case knocked out rather than filled, because a one-colour rendering has no colour to separate the case from the M. `notification-badge-{72,96}.png` are its transparent raster exports, padded to 86% so a platform mask cannot clip the outer walls.

The display-size `stack-mark-mono-*` outline masters are **not** the right badge: at 24 dp their 32-unit strokes land under a pixel and the mark resolves to a grey smudge. Use them for print, engraving and watermarks, where they are drawn large.

### Sharing artwork

`social-card-1200x630.png` is the horizontal lockup optically centred on the ink field. It deliberately does not use the photographic hero or the personalised poster edition: a link-preview image is a redistribution surface, and both of those are built from third-party film stills.

### Proofs

`micro-mark-pixel-proof.png` enlarges the exact 16, 32, 48 and 64 px exports without smoothing. `monochrome-proof.png` verifies the one-colour masters on light and dark surfaces. `identity-overview.png` summarises the complete responsive hierarchy.

## Visual rules

- Preserve the order and overlap: left rear case, dominant centre case, right rear case, disc behind the right case.
- Keep the central case burgundy in both dark and light modes. Champagne gold is structural on dark surfaces and an accent on light surfaces.
- Do not put detailed imagery into the mark below 192 px.
- Do not remove the disc above 16 px: it distinguishes a physical collection from posters, books or a generic gallery.
- Do not add titles or credit text inside the small mark.
- Do not round bitmap app icons manually; operating systems apply their own masks.
- Preserve clear space equal to at least half the visible disc radius.

## Rebuilding

`../build_stack_identity.cjs` generates the vector masters, fixed-size exports, favicon, lockups, notification badge, social card and `identity-overview.png`. `../../../../scripts/brand-sync.mjs` then installs the subset the web app ships into `apps/web/public/brand/`; `--check` reports drift between the two. It uses `sharp`; in Codex, load the bundled workspace dependencies and expose their Node module directory when running the builder.

The builder consumes the approved concept and personalised masters from `../concepts/poster-stack-v2/` and the existing path-based wordmark. It does not modify application code or install runtime dependencies.
