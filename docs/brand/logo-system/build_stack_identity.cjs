/** Build the selected three-case-and-disc responsive identity. */

const fs = require("node:fs/promises");
const path = require("node:path");
const sharp = require("sharp");

const ROOT = __dirname;
const OUTPUT = path.join(ROOT, "stack-family");
const CONCEPT_ROOT = path.join(ROOT, "concepts", "poster-stack-v2");

const GOLD = "#D4AF7F";
const CRIMSON = "#B8475E";
const DEEP_CRIMSON = "#520A1F";
const INK = "#0A0A0B";
const LIGHT = "#FAFAF9";
const OFF_WHITE = "#FAFAFA";

function documentSvg({ viewBox = "0 0 1024 1024", title, desc, content }) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}" role="img" aria-labelledby="title desc">
  <title id="title">${title}</title>
  <desc id="desc">${desc}</desc>
${content}
</svg>
`;
}

function recolour(pathMarkup, colour) {
  return pathMarkup.replace(/fill="#[A-Fa-f0-9]{6}"/, `fill="${colour}"`);
}

function pathsFrom(groupMarkup) {
  return [...groupMarkup.matchAll(/<path\b[^>]*\/>/g)].map((match) => match[0]);
}

function headline(paths, colour, apostrophe = GOLD) {
  return paths
    .map((pathMarkup, index) => recolour(pathMarkup, index === 4 ? apostrophe : colour))
    .join("\n    ");
}

function subtitle(paths, colour) {
  return paths.map((pathMarkup) => recolour(pathMarkup, colour)).join("\n    ");
}

// The rear cases are deliberately equal in visual width. The narrower centre
// case exposes more of both rear cases and sharpens the M-shaped top silhouette.
const LEFT_OUTER = "M116 266L432 326V748L116 696Z";
const LEFT_INNER = "M150 306L398 352V708L150 666Z";
const RIGHT_OUTER = "M592 326L908 266V696L592 748Z";
const RIGHT_INNER = "M626 352L874 306V666L626 708Z";
const CENTRE_OUTER = "M358 358L666 394V802L358 844Z";
const CENTRE_INNER = "M392 396L632 424V770L392 806Z";

function paletteFor(surface) {
  if (surface === "dark") {
    return { field: INK, outline: GOLD, centre: CRIMSON, spine: DEEP_CRIMSON, disc: GOLD };
  }
  return { field: LIGHT, outline: DEEP_CRIMSON, centre: CRIMSON, spine: GOLD, disc: GOLD };
}

function flatStackSymbol({ field, outline, centre, spine, disc }) {
  return `  <g stroke-linejoin="round">
    <circle cx="870" cy="520" r="180" fill="${disc}"/>
    <circle cx="870" cy="520" r="142" fill="${field}"/>
    <circle cx="870" cy="520" r="58" fill="${disc}"/>
    <circle cx="870" cy="520" r="26" fill="${field}"/>
    <path d="${LEFT_OUTER}" fill="${outline}"/>
    <path d="${LEFT_INNER}" fill="${field}"/>
    <path d="${RIGHT_OUTER}" fill="${outline}"/>
    <path d="${RIGHT_INNER}" fill="${field}"/>
    <path d="${CENTRE_OUTER}" fill="${outline}"/>
    <path d="${CENTRE_INNER}" fill="${centre}"/>
    <path d="M408 400L434 403V792L408 796Z" fill="${spine}"/>
  </g>`;
}

function compactStackSymbol({ field, outline, centre, spine, disc }) {
  return `  <g stroke-linejoin="round" stroke-linecap="square">
    <circle cx="870" cy="520" r="164" fill="${field}" stroke="${disc}" stroke-width="52"/>
    <circle cx="870" cy="520" r="46" fill="${field}" stroke="${disc}" stroke-width="38"/>
    <path d="${LEFT_OUTER}" fill="${field}" stroke="${outline}" stroke-width="48"/>
    <path d="${RIGHT_OUTER}" fill="${field}" stroke="${outline}" stroke-width="48"/>
    <path d="${CENTRE_OUTER}" fill="${centre}" stroke="${outline}" stroke-width="52"/>
    <path d="M410 405L438 408V790L410 794Z" fill="${spine}"/>
  </g>`;
}

function flatStackSvg({ surface = "dark", maskable = false }) {
  const palette = paletteFor(surface);
  const scale = maskable ? 0.72 : 0.88;
  const offset = (1024 - 1024 * scale) / 2;
  return documentSvg({
    title: "Mark's Cinematic Universe three-case mark",
    desc: "Three overlapping physical movie cases form an M silhouette with an optical disc behind them",
    content: `  <rect width="1024" height="1024"${maskable ? "" : ' rx="216"'} fill="${palette.field}"/>
  <g transform="translate(${offset} ${offset}) scale(${scale})">
${flatStackSymbol(palette)}
  </g>`,
  });
}

function compactStackSvg({ surface = "dark" }) {
  const palette = paletteFor(surface);
  return documentSvg({
    title: "Mark's Cinematic Universe compact three-case mark",
    desc: "Optically strengthened three-case and disc mark for compact interfaces",
    content: `  <rect width="1024" height="1024" rx="216" fill="${palette.field}"/>
  <g transform="translate(72 72) scale(0.86)">
${compactStackSymbol(palette)}
  </g>`,
  });
}

function monoStackSvg(colour) {
  return documentSvg({
    title: "Mark's Cinematic Universe monochrome three-case mark",
    desc: "One-colour outline of three movie cases and an optical disc",
    content: `  <defs>
    <mask id="disc-cut">
      <rect width="1024" height="1024" fill="white"/>
      <path d="${RIGHT_OUTER}" fill="black"/>
      <path d="${CENTRE_OUTER}" fill="black"/>
    </mask>
    <mask id="rear-cut">
      <rect width="1024" height="1024" fill="white"/>
      <path d="${CENTRE_OUTER}" fill="black"/>
    </mask>
  </defs>
  <g fill="none" stroke="${colour}" stroke-width="32" stroke-linejoin="round">
    <g mask="url(#disc-cut)">
      <circle cx="870" cy="520" r="164"/>
      <circle cx="870" cy="520" r="46"/>
    </g>
    <g mask="url(#rear-cut)">
      <path d="${LEFT_OUTER}"/>
      <path d="${RIGHT_OUTER}"/>
    </g>
    <path d="${CENTRE_OUTER}"/>
  </g>`,
  });
}

// Drawn on a 16x16 grid rather than reduced from the display master: the M silhouette
// and the centre case are the only two ideas that survive at this size.
const MICRO_M = "M1 3H4L8 6L12 3H15V13H12V7L9 9V14H7V9L4 7V13H1Z";
const MICRO_CASE = "M5 6L11 7V15L5 14Z";
const MICRO_CASE_INNER = "M6 7L10 8V13L6 13Z";

function micro16Svg() {
  return documentSvg({
    viewBox: "0 0 16 16",
    title: "Mark's sixteen-pixel movie-case mark",
    desc: "Pixel-hinted three-case-and-disc favicon",
    content: `  <g shape-rendering="crispEdges">
    <rect width="16" height="16" fill="${INK}"/>
    <path d="${MICRO_M}" fill="${GOLD}"/>
    <path d="${MICRO_CASE}" fill="${GOLD}"/>
    <path d="${MICRO_CASE_INNER}" fill="${CRIMSON}"/>
  </g>`,
  });
}

/**
 * The micro mark in one colour, for a platform that keeps only the alpha channel.
 *
 * The same geometry as `micro16Svg`, with the centre case knocked out instead of filled
 * crimson — colour is what separates the case from the M at this size, and a mask has no
 * colour to separate them with. The display-size monochrome outline master was tried
 * first and does not survive: its 32-unit strokes land under a pixel at 24 dp and the
 * mark resolves to a grey smudge.
 */
function microMarkMonoSvg(colour) {
  return documentSvg({
    viewBox: "0 0 16 16",
    title: "Mark's Cinematic Universe one-colour micro mark",
    desc: "Single-colour M silhouette with the centre case knocked out, for notification badges and masks",
    content: `  <defs>
    <mask id="centre-case">
      <rect width="16" height="16" fill="white"/>
      <path d="${MICRO_CASE_INNER}" fill="black"/>
    </mask>
  </defs>
  <g fill="${colour}" mask="url(#centre-case)">
    <path d="${MICRO_M}"/>
    <path d="${MICRO_CASE}"/>
  </g>`,
  });
}

function horizontalLockupSvg({ headlinePaths, subtitlePaths, surface }) {
  const palette = paletteFor(surface);
  const primary = surface === "dark" ? GOLD : DEEP_CRIMSON;
  const supporting = surface === "dark" ? OFF_WHITE : INK;
  return documentSvg({
    viewBox: "0 0 1600 420",
    title: "Mark's Cinematic Universe horizontal logo",
    desc: `Three-case collection mark and wordmark for ${surface} surfaces`,
    content: `  <g transform="translate(-10 0) scale(0.41)">
${flatStackSymbol(palette)}
  </g>
  <g transform="translate(345 30)">
    ${headline(headlinePaths, primary, GOLD)}
    ${subtitle(subtitlePaths, supporting)}
  </g>`,
  });
}

function stackedLockupSvg({ headlinePaths, subtitlePaths, surface }) {
  const palette = paletteFor(surface);
  const primary = surface === "dark" ? GOLD : DEEP_CRIMSON;
  const supporting = surface === "dark" ? OFF_WHITE : INK;
  return documentSvg({
    viewBox: "0 0 1080 1080",
    title: "Mark's Cinematic Universe stacked logo",
    desc: `Square three-case collection mark and wordmark for ${surface} surfaces`,
    content: `  <rect width="1080" height="1080" fill="${palette.field}"/>
  <g transform="translate(207 -2) scale(0.65)">
${flatStackSymbol(palette)}
  </g>
  <g transform="translate(38 620) scale(0.84)">
    ${headline(headlinePaths, primary, GOLD)}
    ${subtitle(subtitlePaths, supporting)}
  </g>`,
  });
}

async function writeSvg(name, svg) {
  const destination = path.join(OUTPUT, name);
  await fs.writeFile(destination, svg, "utf8");
  return destination;
}

async function renderSvg(svgPath, outputName, width, height) {
  await sharp(svgPath, { density: 300 })
    .resize(width, height, { fit: "fill" })
    .png()
    .toFile(path.join(OUTPUT, outputName));
}

async function renderImage(source, outputName, size) {
  await sharp(source)
    .resize(size, size, { fit: "fill" })
    .png()
    .toFile(path.join(OUTPUT, outputName));
}

async function cleanArtworkBackground(source) {
  const { data, info } = await sharp(source).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const pixelCount = info.width * info.height;
  const visited = new Uint8Array(pixelCount);
  const queue = new Int32Array(pixelCount);
  let head = 0;
  let tail = 0;

  const isBackground = (pixelIndex) => {
    const offset = pixelIndex * 4;
    return Math.max(data[offset], data[offset + 1], data[offset + 2]) <= 48;
  };
  const enqueue = (pixelIndex) => {
    if (visited[pixelIndex] || !isBackground(pixelIndex)) return;
    visited[pixelIndex] = 1;
    queue[tail] = pixelIndex;
    tail += 1;
  };

  for (let x = 0; x < info.width; x += 1) {
    enqueue(x);
    enqueue((info.height - 1) * info.width + x);
  }
  for (let y = 1; y < info.height - 1; y += 1) {
    enqueue(y * info.width);
    enqueue(y * info.width + info.width - 1);
  }

  while (head < tail) {
    const pixelIndex = queue[head];
    head += 1;
    const x = pixelIndex % info.width;
    const y = Math.floor(pixelIndex / info.width);
    if (x > 0) enqueue(pixelIndex - 1);
    if (x + 1 < info.width) enqueue(pixelIndex + 1);
    if (y > 0) enqueue(pixelIndex - info.width);
    if (y + 1 < info.height) enqueue(pixelIndex + info.width);
  }

  for (let pixelIndex = 0; pixelIndex < pixelCount; pixelIndex += 1) {
    if (!visited[pixelIndex]) continue;
    const offset = pixelIndex * 4;
    data[offset] = 10;
    data[offset + 1] = 10;
    data[offset + 2] = 11;
    data[offset + 3] = 255;
  }

  return sharp(data, { raw: info }).png().toBuffer();
}

async function renderMaskable(source, outputName, size) {
  const innerSize = Math.round(size * 0.72);
  const inset = Math.floor((size - innerSize) / 2);
  const image = await sharp(source).resize(innerSize, innerSize, { fit: "fill" }).png().toBuffer();
  await sharp({ create: { width: size, height: size, channels: 3, background: INK } })
    .composite([{ input: image, left: inset, top: inset }])
    .flatten({ background: INK })
    .removeAlpha()
    .png()
    .toFile(path.join(OUTPUT, outputName));
}

function icoFromPngBuffers(entries) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(entries.length, 4);
  let offset = 6 + 16 * entries.length;
  const directory = entries.map(({ size, buffer }) => {
    const entry = Buffer.alloc(16);
    entry.writeUInt8(size === 256 ? 0 : size, 0);
    entry.writeUInt8(size === 256 ? 0 : size, 1);
    entry.writeUInt16LE(1, 4);
    entry.writeUInt16LE(32, 6);
    entry.writeUInt32LE(buffer.length, 8);
    entry.writeUInt32LE(offset, 12);
    offset += buffer.length;
    return entry;
  });
  return Buffer.concat([header, ...directory, ...entries.map(({ buffer }) => buffer)]);
}

/**
 * Notification badge — a platform mask, not a picture.
 *
 * Android draws `badge` at 24 dp and keeps only the alpha channel, recolouring it with the
 * system accent. The badge is therefore the one-colour micro mark, padded into a
 * transparent canvas rather than run to the edges: the platform crops, and an asset that
 * already touches its own frame loses its outer walls when it does.
 */
async function renderNotificationBadge(svgPath, outputName, size) {
  const innerSize = Math.round(size * 0.86);
  const inset = Math.floor((size - innerSize) / 2);
  const mark = await sharp(svgPath, { density: 1200 })
    .resize(innerSize, innerSize, { fit: "fill" })
    .png()
    .toBuffer();
  await sharp({
    create: { width: size, height: size, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } },
  })
    .composite([{ input: mark, left: inset, top: inset }])
    .png()
    .toFile(path.join(OUTPUT, outputName));
}

/**
 * Link-preview artwork.
 *
 * The horizontal lockup on the ink field and nothing else: the lockup already carries the
 * mark, so adding the icon beside it would show the same stack twice. The photographic
 * hero is deliberately not used here — a share card is a redistribution surface, and that
 * edition is built from third-party film stills.
 */
async function buildSocialCard() {
  const width = 1200;
  const height = 630;
  const lockupWidth = 880;
  const lockupHeight = Math.round((lockupWidth * 420) / 1600);
  const lockup = await sharp(path.join(OUTPUT, "horizontal-lockup-dark.svg"), { density: 600 })
    .resize(lockupWidth, lockupHeight, { fit: "fill" })
    .png()
    .toBuffer();
  // The lockup's viewBox carries clear space, and not symmetrically — its ink ends about
  // 60 units short of the right edge. Centring the *box* would leave the logo visibly left
  // of centre on the card, so centre the drawn artwork instead.
  const bounds = await inkBounds(lockup);
  await sharp({ create: { width, height, channels: 3, background: INK } })
    .composite([
      {
        input: lockup,
        left: Math.round((width - bounds.width) / 2) - bounds.left,
        top: Math.round((height - bounds.height) / 2) - bounds.top,
      },
    ])
    .png()
    .toFile(path.join(OUTPUT, "social-card-1200x630.png"));
}

/** The bounding box of everything actually drawn in a transparent PNG buffer. */
async function inkBounds(buffer) {
  const { data, info } = await sharp(buffer).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  let left = info.width;
  let top = info.height;
  let right = -1;
  let bottom = -1;
  for (let y = 0; y < info.height; y += 1) {
    for (let x = 0; x < info.width; x += 1) {
      if (data[(y * info.width + x) * 4 + 3] <= 8) continue;
      if (x < left) left = x;
      if (x > right) right = x;
      if (y < top) top = y;
      if (y > bottom) bottom = y;
    }
  }
  return { left, top, width: right - left + 1, height: bottom - top + 1 };
}

async function buildPreview() {
  const width = 1800;
  const height = 1120;
  const concept = await sharp(path.join(OUTPUT, "app-icon-concept-art-512.png")).resize(420, 420).toBuffer();
  const poster = await sharp(path.join(OUTPUT, "personalised-poster-icon-512.png")).resize(420, 420).toBuffer();
  const flat = await sharp(path.join(OUTPUT, "stack-mark-512.png")).resize(420, 420).toBuffer();
  const micro = await sharp(path.join(OUTPUT, "micro-mark-64.png")).resize(256, 256, { kernel: "nearest" }).toBuffer();
  const label = Buffer.from(`<svg width="1800" height="1120" xmlns="http://www.w3.org/2000/svg">
    <style>.h{font:700 38px Arial,sans-serif;fill:${OFF_WHITE}}.s{font:400 22px Arial,sans-serif;fill:${GOLD}}.l{font:700 22px Arial,sans-serif;fill:${OFF_WHITE}}.n{font:400 18px Arial,sans-serif;fill:#B8AFB2}</style>
    <text x="42" y="58" class="h">THREE-CASE + DISC — RESPONSIVE IDENTITY</text>
    <text x="42" y="94" class="s">Rich at display size. Optically strengthened below 128 px.</text>
    <rect x="42" y="130" width="536" height="520" rx="22" fill="${INK}" stroke="#40383B" stroke-width="2"/>
    <rect x="632" y="130" width="536" height="520" rx="22" fill="${INK}" stroke="#40383B" stroke-width="2"/>
    <rect x="1222" y="130" width="536" height="520" rx="22" fill="${INK}" stroke="#40383B" stroke-width="2"/>
    <text x="64" y="620" class="l">CONCEPT-ART MASTER</text>
    <text x="654" y="620" class="l">PERSONALISED EDITION</text>
    <text x="1244" y="620" class="l">SIMPLIFIED VECTOR</text>
    <rect x="42" y="700" width="1716" height="370" rx="22" fill="${INK}" stroke="#40383B" stroke-width="2"/>
    <text x="64" y="744" class="l">MICRO MARK</text>
    <text x="64" y="1052" class="n">Shown enlarged from the exact 64 px export</text>
    <text x="430" y="806" class="l">Usage threshold</text>
    <text x="430" y="832" class="s">192 px and above</text><text x="690" y="832" class="n">Concept-art or personalised edition</text>
    <text x="430" y="878" class="s">128 px</text><text x="690" y="878" class="n">Display vector stack</text>
    <text x="430" y="924" class="s">32–96 px</text><text x="690" y="924" class="n">Optically strengthened compact stack</text>
    <text x="430" y="970" class="s">16 px</text><text x="690" y="970" class="n">Pixel-hinted M favicon</text>
  </svg>`);
  await sharp({ create: { width, height, channels: 3, background: "#141316" } })
    .composite([
      { input: label, left: 0, top: 0 },
      { input: concept, left: 100, top: 170 },
      { input: poster, left: 690, top: 170 },
      { input: flat, left: 1280, top: 170 },
      { input: micro, left: 100, top: 770 },
    ])
    .png()
    .toFile(path.join(OUTPUT, "identity-overview.png"));
}

async function buildProofs() {
  const sizes = [16, 32, 48, 64];
  const composites = [];
  for (let index = 0; index < sizes.length; index += 1) {
    const size = sizes[index];
    const source = path.join(OUTPUT, `micro-mark-${size}.png`);
    const enlarged = await sharp(source).resize(220, 220, { kernel: "nearest" }).png().toBuffer();
    composites.push({ input: enlarged, left: 42 + index * 280, top: 94 });
  }
  const labels = Buffer.from(`<svg width="1200" height="410" xmlns="http://www.w3.org/2000/svg">
    <style>.h{font:700 30px Arial,sans-serif;fill:${OFF_WHITE}}.l{font:700 20px Arial,sans-serif;fill:${GOLD}}.n{font:400 16px Arial,sans-serif;fill:#B8AFB2}</style>
    <text x="42" y="52" class="h">MICRO-MARK PIXEL PROOF</text>
    <text x="42" y="78" class="n">Each exact export enlarged with nearest-neighbour scaling.</text>
    <text x="126" y="350" class="l">16 px</text>
    <text x="406" y="350" class="l">32 px</text>
    <text x="686" y="350" class="l">48 px</text>
    <text x="966" y="350" class="l">64 px</text>
  </svg>`);
  await sharp({ create: { width: 1200, height: 410, channels: 3, background: "#141316" } })
    .composite([{ input: labels, left: 0, top: 0 }, ...composites])
    .png()
    .toFile(path.join(OUTPUT, "micro-mark-pixel-proof.png"));

  const black = await sharp(path.join(OUTPUT, "stack-mark-mono-black-512.png")).resize(360, 360).toBuffer();
  const white = await sharp(path.join(OUTPUT, "stack-mark-mono-white-512.png")).resize(360, 360).toBuffer();
  const monoLabels = Buffer.from(`<svg width="1000" height="560" xmlns="http://www.w3.org/2000/svg">
    <style>.h{font:700 30px Arial,sans-serif;fill:${OFF_WHITE}}.d{font:700 20px Arial,sans-serif;fill:${INK}}.l{font:700 20px Arial,sans-serif;fill:${OFF_WHITE}}</style>
    <text x="36" y="48" class="h">ONE-COLOUR PROOF</text>
    <rect x="36" y="78" width="440" height="440" rx="18" fill="${LIGHT}"/>
    <rect x="524" y="78" width="440" height="440" rx="18" fill="${INK}" stroke="#40383B" stroke-width="2"/>
    <text x="60" y="494" class="d">BLACK</text>
    <text x="548" y="494" class="l">WHITE</text>
  </svg>`);
  await sharp({ create: { width: 1000, height: 560, channels: 3, background: "#141316" } })
    .composite([
      { input: monoLabels, left: 0, top: 0 },
      { input: black, left: 76, top: 112 },
      { input: white, left: 564, top: 112 },
    ])
    .png()
    .toFile(path.join(OUTPUT, "monochrome-proof.png"));
}

async function build() {
  await fs.mkdir(OUTPUT, { recursive: true });
  const source = await fs.readFile(path.join(ROOT, "wordmark-dark.svg"), "utf8");
  const groups = [...source.matchAll(/<g>\s*([\s\S]*?)\s*<\/g>/g)].map((match) => match[1]);
  if (groups.length !== 2) throw new Error("Expected headline and subtitle groups");
  const headlinePaths = pathsFrom(groups[0]);
  const subtitlePaths = pathsFrom(groups[1]);

  const svgs = new Map([
    ["stack-mark.svg", flatStackSvg({ surface: "dark" })],
    ["stack-mark-light.svg", flatStackSvg({ surface: "light" })],
    ["stack-mark-compact.svg", compactStackSvg({ surface: "dark" })],
    ["stack-mark-compact-light.svg", compactStackSvg({ surface: "light" })],
    ["stack-mark-maskable.svg", flatStackSvg({ surface: "dark", maskable: true })],
    ["stack-mark-mono-black.svg", monoStackSvg("#000000")],
    ["stack-mark-mono-white.svg", monoStackSvg("#FFFFFF")],
    ["micro-mark-16.svg", micro16Svg()],
    ["micro-mark-mono-white.svg", microMarkMonoSvg("#FFFFFF")],
    ["micro-mark-mono-black.svg", microMarkMonoSvg("#000000")],
    ["horizontal-lockup-dark.svg", horizontalLockupSvg({ headlinePaths, subtitlePaths, surface: "dark" })],
    ["horizontal-lockup-light.svg", horizontalLockupSvg({ headlinePaths, subtitlePaths, surface: "light" })],
    ["stacked-lockup-dark.svg", stackedLockupSvg({ headlinePaths, subtitlePaths, surface: "dark" })],
    ["stacked-lockup-light.svg", stackedLockupSvg({ headlinePaths, subtitlePaths, surface: "light" })],
  ]);

  const svgPaths = new Map();
  for (const [name, svg] of svgs) svgPaths.set(name, await writeSvg(name, svg));

  for (const size of [1024, 512, 192, 128]) {
    await renderSvg(svgPaths.get("stack-mark.svg"), `stack-mark-${size}.png`, size, size);
  }
  for (const size of [96, 64, 48, 32]) {
    await renderSvg(svgPaths.get("stack-mark-compact.svg"), `stack-mark-${size}.png`, size, size);
  }

  const faviconEntries = [];
  for (const size of [16, 32, 48, 64]) {
    const name = `micro-mark-${size}.png`;
    const sourcePath = size === 16 ? svgPaths.get("micro-mark-16.svg") : svgPaths.get("stack-mark-compact.svg");
    await renderSvg(sourcePath, name, size, size);
    if ([16, 32, 48].includes(size)) {
      faviconEntries.push({ size, buffer: await fs.readFile(path.join(OUTPUT, name)) });
    }
  }
  await fs.writeFile(path.join(OUTPUT, "favicon.ico"), icoFromPngBuffers(faviconEntries));

  for (const [svgName, pngName, width, height] of [
    ["horizontal-lockup-dark.svg", "horizontal-lockup-dark.png", 1600, 420],
    ["horizontal-lockup-light.svg", "horizontal-lockup-light.png", 1600, 420],
    ["stacked-lockup-dark.svg", "stacked-lockup-dark.png", 1080, 1080],
    ["stacked-lockup-light.svg", "stacked-lockup-light.png", 1080, 1080],
    ["stack-mark-mono-black.svg", "stack-mark-mono-black-512.png", 512, 512],
    ["stack-mark-mono-white.svg", "stack-mark-mono-white-512.png", 512, 512],
  ]) {
    await renderSvg(svgPaths.get(svgName), pngName, width, height);
  }

  const conceptSource = path.join(CONCEPT_ROOT, "poster-stack-concept-art-v1.png");
  const posterSource = path.join(CONCEPT_ROOT, "poster-stack-actual-posters-v1.png");
  const cleanConceptSource = await cleanArtworkBackground(conceptSource);
  const cleanPosterSource = await cleanArtworkBackground(posterSource);
  await fs.writeFile(path.join(OUTPUT, "app-icon-concept-art-clean-master.png"), cleanConceptSource);
  await fs.writeFile(path.join(OUTPUT, "personalised-poster-clean-master.png"), cleanPosterSource);
  // 384 is in the list because the web app manifest declares that size; 180 is the
  // Apple touch icon.
  for (const size of [1024, 512, 384, 192, 180, 128]) {
    await renderImage(cleanConceptSource, `app-icon-concept-art-${size}.png`, size);
  }
  for (const size of [1024, 512, 192, 128]) {
    await renderImage(cleanPosterSource, `personalised-poster-icon-${size}.png`, size);
  }
  await fs.copyFile(path.join(OUTPUT, "app-icon-concept-art-180.png"), path.join(OUTPUT, "apple-touch-icon.png"));
  await renderMaskable(cleanConceptSource, "app-icon-concept-art-maskable-512.png", 512);
  await renderMaskable(cleanConceptSource, "app-icon-concept-art-maskable-192.png", 192);
  await renderSvg(svgPaths.get("stack-mark-maskable.svg"), "stack-mark-maskable-512.png", 512, 512);
  await renderSvg(svgPaths.get("stack-mark-maskable.svg"), "stack-mark-maskable-192.png", 192, 192);

  for (const size of [96, 72]) {
    await renderNotificationBadge(
      svgPaths.get("micro-mark-mono-white.svg"),
      `notification-badge-${size}.png`,
      size,
    );
  }

  await buildSocialCard();
  await buildPreview();
  await buildProofs();
}

build().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
