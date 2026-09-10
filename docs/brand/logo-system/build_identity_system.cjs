/** Build the responsive, source-controlled Mark's Cinematic Universe identity. */

const fs = require("node:fs/promises");
const path = require("node:path");
const sharp = require("sharp");

const ROOT = __dirname;
const OUTPUT = path.join(ROOT, "responsive");

const GOLD = "#D4AF7F";
const CRIMSON = "#B8475E";
const DEEP_CRIMSON = "#520A1F";
const INK = "#0A0A0B";
const OFF_WHITE = "#FAFAFA";
const LIGHT = "#FAFAF9";

function documentSvg({ viewBox, title, desc, content }) {
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

function wordmarkSvg({ headlinePaths, subtitlePaths, surface, compact = false, mono }) {
  const mainColour = mono ?? (surface === "dark" ? GOLD : CRIMSON);
  const apostropheColour = mono ?? GOLD;
  const supportingColour = mono ?? (surface === "dark" ? OFF_WHITE : INK);
  const main = headline(headlinePaths, mainColour, apostropheColour);
  const support = compact ? "" : `\n  <g>\n    ${subtitle(subtitlePaths, supportingColour)}\n  </g>`;

  return documentSvg({
    viewBox: compact ? "0 0 1200 270" : "0 0 1200 360",
    title: compact ? "Mark's" : "Mark's Cinematic Universe",
    desc: compact
      ? `Compact one-line wordmark for ${surface} surfaces`
      : `Primary wordmark for ${surface} surfaces`,
    content: `  <g>\n    ${main}\n  </g>${support}`,
  });
}

function microSymbol(primary = GOLD, accent = CRIMSON, maskable = false) {
  if (maskable) {
    return `  <path d="M292 738V330L512 558 732 330V738" fill="none" stroke="${primary}" stroke-width="118" stroke-linejoin="miter" stroke-linecap="square"/>
  <path d="M742 282H819L807 398H730Z" fill="${accent}"/>`;
  }
  return `  <path d="M218 788V252L512 548 806 252V788" fill="none" stroke="${primary}" stroke-width="138" stroke-linejoin="miter" stroke-linecap="square"/>
  <path d="M806 194H894L881 326H793Z" fill="${accent}"/>`;
}

function microSvg({ surface = "dark", mono, maskable = false }) {
  const background = surface === "dark" ? INK : LIGHT;
  const primary = mono ?? (surface === "dark" ? GOLD : CRIMSON);
  const accent = mono ?? (surface === "dark" ? CRIMSON : GOLD);
  const field = mono
    ? ""
    : `  <rect width="1024" height="1024"${maskable ? "" : ' rx="220"'} fill="${background}"/>\n`;
  return documentSvg({
    viewBox: "0 0 1024 1024",
    title: "Mark's micro mark",
    desc: "Simplified M and possessive mark for very small sizes",
    content: `${field}${microSymbol(primary, accent, maskable)}`,
  });
}

function micro16Svg() {
  return documentSvg({
    viewBox: "0 0 16 16",
    title: "Mark's sixteen-pixel micro mark",
    desc: "Pixel-hinted M and possessive mark for browser tabs",
    content: `  <g shape-rendering="crispEdges">
    <rect width="16" height="16" fill="${INK}"/>
    <path d="M3 14V4H5L8 8L11 4H13V14H11V8L8 12L5 8V14Z" fill="${GOLD}"/>
    <rect x="13" y="2" width="2" height="3" fill="${CRIMSON}"/>
  </g>`,
  });
}

function monogramSymbol(primary = GOLD, accent = CRIMSON) {
  return `  <path d="M244 526V230L512 486 780 230V526" fill="none" stroke="${primary}" stroke-width="82" stroke-linejoin="miter" stroke-linecap="square"/>
  <path d="M274 580V714Q274 820 384 820H640Q750 820 750 714V580" fill="none" stroke="${primary}" stroke-width="78" stroke-linecap="square" stroke-linejoin="round"/>
  <path d="M630 538A130 130 0 1 0 630 682" fill="none" stroke="${primary}" stroke-width="60" stroke-linecap="square"/>
  <path d="M629 565L691 591 629 617Z" fill="${accent}"/>`;
}

function monogramSvg({ surface = "dark", mono }) {
  const background = surface === "dark" ? INK : LIGHT;
  const primary = mono ?? (surface === "dark" ? GOLD : CRIMSON);
  const accent = mono ?? (surface === "dark" ? CRIMSON : GOLD);
  const field = mono ? "" : `  <rect width="1024" height="1024" rx="216" fill="${background}"/>\n`;
  return documentSvg({
    viewBox: "0 0 1024 1024",
    title: "The Real MCU display monogram",
    desc: "Display-size monogram combining an M, C, U and triangular accent",
    content: `${field}  <rect x="42" y="42" width="940" height="940" rx="184" fill="none" stroke="${primary}" stroke-width="18"/>
${monogramSymbol(primary, accent)}`,
  });
}

function appIconSvg({ maskable = false }) {
  const scale = maskable ? 0.68 : 0.78;
  const offset = (1024 - 1024 * scale) / 2;
  return documentSvg({
    viewBox: "0 0 1024 1024",
    title: "Mark's Cinematic Universe app icon",
    desc: maskable
      ? "Full-bleed maskable app icon with protected monogram safe area"
      : "Full-bleed home-screen app icon",
    content: `  <rect width="1024" height="1024" fill="${INK}"/>
  <g transform="translate(${offset} ${offset}) scale(${scale})">
    <rect x="42" y="42" width="940" height="940" rx="184" fill="none" stroke="${GOLD}" stroke-width="18"/>
${monogramSymbol(GOLD, CRIMSON)}
  </g>`,
  });
}

function stackedSvg({ headlinePaths, subtitlePaths, surface }) {
  const background = surface === "dark" ? INK : LIGHT;
  const primary = surface === "dark" ? GOLD : CRIMSON;
  const supporting = surface === "dark" ? OFF_WHITE : INK;
  const main = headline(headlinePaths, primary, GOLD);
  const support = subtitle(subtitlePaths, supporting);

  return documentSvg({
    viewBox: "0 0 1080 1080",
    title: "Mark's Cinematic Universe stacked lockup",
    desc: `Square brand lockup for ${surface} presentation surfaces`,
    content: `  <rect width="1080" height="1080" fill="${background}"/>
  <g transform="translate(294 45) scale(0.48)">
    <rect x="42" y="42" width="940" height="940" rx="184" fill="none" stroke="${primary}" stroke-width="18"/>
${monogramSymbol(primary, surface === "dark" ? CRIMSON : GOLD)}
  </g>
  <g transform="translate(12 640) scale(0.88)">
    ${main}
  </g>
  <g transform="translate(12 640) scale(0.88)">
    ${support}
  </g>`,
  });
}

async function writeSvg(name, svg) {
  const destination = path.join(OUTPUT, name);
  await fs.writeFile(destination, svg, "utf8");
  return destination;
}

async function render(svgPath, outputName, width, height) {
  await sharp(svgPath, { density: 300 })
    .resize(width, height, { fit: "fill" })
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
    entry.writeUInt8(0, 2);
    entry.writeUInt8(0, 3);
    entry.writeUInt16LE(1, 4);
    entry.writeUInt16LE(32, 6);
    entry.writeUInt32LE(buffer.length, 8);
    entry.writeUInt32LE(offset, 12);
    offset += buffer.length;
    return entry;
  });
  return Buffer.concat([header, ...directory, ...entries.map(({ buffer }) => buffer)]);
}

async function build() {
  await fs.mkdir(OUTPUT, { recursive: true });

  const source = await fs.readFile(path.join(ROOT, "wordmark-dark.svg"), "utf8");
  const groups = [...source.matchAll(/<g>\s*([\s\S]*?)\s*<\/g>/g)].map((match) => match[1]);
  if (groups.length !== 2) throw new Error("Expected headline and subtitle groups");
  const headlinePaths = pathsFrom(groups[0]);
  const subtitlePaths = pathsFrom(groups[1]);
  if (headlinePaths.length !== 6 || subtitlePaths.length < 17) {
    throw new Error("Unexpected source wordmark path count");
  }

  const svgs = new Map([
    ["wordmark-primary-dark.svg", wordmarkSvg({ headlinePaths, subtitlePaths, surface: "dark" })],
    ["wordmark-primary-light.svg", wordmarkSvg({ headlinePaths, subtitlePaths, surface: "light" })],
    ["wordmark-compact-dark.svg", wordmarkSvg({ headlinePaths, subtitlePaths, surface: "dark", compact: true })],
    ["wordmark-compact-light.svg", wordmarkSvg({ headlinePaths, subtitlePaths, surface: "light", compact: true })],
    ["wordmark-mono-black.svg", wordmarkSvg({ headlinePaths, subtitlePaths, surface: "light", mono: "#000000" })],
    ["wordmark-mono-white.svg", wordmarkSvg({ headlinePaths, subtitlePaths, surface: "dark", mono: "#FFFFFF" })],
    ["wordmark-compact-mono-black.svg", wordmarkSvg({ headlinePaths, subtitlePaths, surface: "light", compact: true, mono: "#000000" })],
    ["wordmark-compact-mono-white.svg", wordmarkSvg({ headlinePaths, subtitlePaths, surface: "dark", compact: true, mono: "#FFFFFF" })],
    ["micro-mark.svg", microSvg({ surface: "dark" })],
    ["micro-mark-16.svg", micro16Svg()],
    ["micro-mark-light.svg", microSvg({ surface: "light" })],
    ["micro-mark-mono-black.svg", microSvg({ mono: "#000000" })],
    ["micro-mark-mono-white.svg", microSvg({ mono: "#FFFFFF" })],
    ["display-monogram-v2.svg", monogramSvg({ surface: "dark" })],
    ["display-monogram-v2-light.svg", monogramSvg({ surface: "light" })],
    ["display-monogram-mono-black.svg", monogramSvg({ mono: "#000000" })],
    ["display-monogram-mono-white.svg", monogramSvg({ mono: "#FFFFFF" })],
    ["app-icon.svg", appIconSvg({})],
    ["app-icon-maskable.svg", appIconSvg({ maskable: true })],
    ["stacked-lockup-dark.svg", stackedSvg({ headlinePaths, subtitlePaths, surface: "dark" })],
    ["stacked-lockup-light.svg", stackedSvg({ headlinePaths, subtitlePaths, surface: "light" })],
  ]);

  const svgPaths = new Map();
  for (const [name, svg] of svgs) svgPaths.set(name, await writeSvg(name, svg));

  const renders = [
    ["wordmark-primary-dark.svg", "wordmark-primary-dark.png", 1200, 360],
    ["wordmark-primary-light.svg", "wordmark-primary-light.png", 1200, 360],
    ["wordmark-compact-dark.svg", "wordmark-compact-dark.png", 1200, 270],
    ["wordmark-compact-light.svg", "wordmark-compact-light.png", 1200, 270],
    ["display-monogram-v2.svg", "display-monogram-v2-1024.png", 1024, 1024],
    ["display-monogram-v2.svg", "display-monogram-v2-512.png", 512, 512],
    ["display-monogram-v2.svg", "display-monogram-v2-192.png", 192, 192],
    ["display-monogram-v2.svg", "display-monogram-v2-64.png", 64, 64],
    ["stacked-lockup-dark.svg", "stacked-lockup-dark.png", 1080, 1080],
    ["stacked-lockup-light.svg", "stacked-lockup-light.png", 1080, 1080],
  ];
  for (const [svgName, pngName, width, height] of renders) {
    await render(svgPaths.get(svgName), pngName, width, height);
  }

  const microPath = svgPaths.get("micro-mark.svg");
  const faviconEntries = [];
  for (const size of [16, 32, 48, 64]) {
    const name = `micro-mark-${size}.png`;
    const sourcePath = size === 16 ? svgPaths.get("micro-mark-16.svg") : microPath;
    await render(sourcePath, name, size, size);
    if ([16, 32, 48].includes(size)) {
      faviconEntries.push({ size, buffer: await fs.readFile(path.join(OUTPUT, name)) });
    }
  }
  await fs.writeFile(path.join(OUTPUT, "favicon.ico"), icoFromPngBuffers(faviconEntries));
  await render(svgPaths.get("app-icon.svg"), "apple-touch-icon.png", 180, 180);
  await render(svgPaths.get("app-icon.svg"), "app-icon-192.png", 192, 192);
  await render(svgPaths.get("app-icon.svg"), "app-icon-512.png", 512, 512);
  await render(svgPaths.get("app-icon.svg"), "app-icon-1024.png", 1024, 1024);
  await render(svgPaths.get("app-icon-maskable.svg"), "app-icon-maskable-192.png", 192, 192);
  await render(svgPaths.get("app-icon-maskable.svg"), "app-icon-maskable-512.png", 512, 512);

  const hero = path.join(ROOT, "hero-photo-five-v3.png");
  const heroBuffer = await sharp(hero).resize(1200, 570, { fit: "fill" }).png().toBuffer();
  await sharp({
    create: { width: 1200, height: 630, channels: 3, background: DEEP_CRIMSON },
  })
    .composite([{ input: heroBuffer, left: 0, top: 30 }])
    .png()
    .toFile(path.join(OUTPUT, "social-card-1200x630.png"));
}

build().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
