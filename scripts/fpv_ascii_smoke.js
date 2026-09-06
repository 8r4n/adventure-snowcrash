#!/usr/bin/env node
/**
 * #95 smoke: VideoAscii luminance→glyph diversity for FPV scene colors.
 * Mirrors snowcrash/static/ascii-video.js _paintGlyphs + post-#95 wallColor scales.
 * Exit 0 if representative surfaces map to several distinct glyphs (not one wall of `a`).
 */
"use strict";

const CHARSET =
  " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";

const BRIGHTNESS = 1.34;
const CONTRAST = 1.4;
const GAMMA = 0.86;
const SATURATE = 1.48;

const TEAL = [148, 226, 213];
const YELLOW = [249, 226, 175];
const SAPPHIRE = [116, 199, 236];
const GREEN = [166, 227, 161];
const MAUVE = [203, 166, 247];

function glyphFor(r0, g0, b0) {
  let r = Math.min(255, Math.max(0, ((r0 - 128) * CONTRAST + 128) * BRIGHTNESS));
  let g = Math.min(255, Math.max(0, ((g0 - 128) * CONTRAST + 128) * BRIGHTNESS));
  let b = Math.min(255, Math.max(0, ((b0 - 128) * CONTRAST + 128) * BRIGHTNESS));
  if (SATURATE !== 1) {
    const gray = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    r = Math.min(255, Math.max(0, gray + (r - gray) * SATURATE));
    g = Math.min(255, Math.max(0, gray + (g - gray) * SATURATE));
    b = Math.min(255, Math.max(0, gray + (b - gray) * SATURATE));
  }
  let lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  if (GAMMA !== 1) lum = Math.pow(Math.max(0, Math.min(1, lum)), GAMMA);
  const idx = Math.min(
    CHARSET.length - 1,
    Math.max(lum > 0.02 ? 1 : 0, Math.floor(lum * CHARSET.length))
  );
  return CHARSET[idx];
}

function wallColor(base, side, dist, scale) {
  const near = Math.max(0.22, Math.min(1, 1.7 / Math.max(0.25, dist)));
  let r = base[0] * scale;
  let g = base[1] * scale;
  let b = base[2] * scale;
  if (side) {
    r *= 0.78;
    g *= 0.78;
    b *= 0.85;
  }
  r = Math.min(255, r * near * 1.15);
  g = Math.min(255, g * near * 1.15);
  b = Math.min(255, b * near * 1.2);
  return [r | 0, g | 0, b | 0];
}

function mixRgb(a, b, t) {
  return [
    (a[0] + (b[0] - a[0]) * t) | 0,
    (a[1] + (b[1] - a[1]) * t) | 0,
    (a[2] + (b[2] - a[2]) * t) | 0,
  ];
}

const CRUST = [17, 17, 27];
const MANTLE = [24, 24, 37];
const BASE = [30, 30, 46];
const SKY = [137, 220, 235];

const samples = {
  ceil: mixRgb(CRUST, SKY, 0.08),
  ceilHorizon: mixRgb(MANTLE, SAPPHIRE, 0.22),
  floorNear: mixRgb(BASE, TEAL, 0.16),
  floorFar: mixRgb(MANTLE, TEAL, 0.1),
  wallNear: wallColor(TEAL, 0, 0.6, 0.58),
  wallMid: wallColor(TEAL, 0, 1.8, 0.58),
  wallFar: wallColor(TEAL, 0, 4, 0.58),
  wallSide: wallColor(TEAL, 1, 1.8, 0.58),
  door: wallColor(YELLOW, 0, 1.5, 0.72),
  ice: wallColor(SAPPHIRE, 0, 1.5, 0.68),
  entity: [Math.min(255, (GREEN[0] * 1.18) | 0), Math.min(255, (GREEN[1] * 1.18) | 0), Math.min(255, (GREEN[2] * 1.18) | 0)],
  entityMauve: [Math.min(255, (MAUVE[0] * 1.18) | 0), Math.min(255, (MAUVE[1] * 1.18) | 0), Math.min(255, (MAUVE[2] * 1.18) | 0)],
};

const mapped = {};
const glyphs = new Set();
for (const [name, rgb] of Object.entries(samples)) {
  const g = glyphFor(rgb[0], rgb[1], rgb[2]);
  mapped[name] = { rgb, glyph: g };
  if (g !== " ") glyphs.add(g);
}

const unique = glyphs.size;
const vals = Object.values(mapped).map((m) => m.glyph);
const allSame = vals.every((g) => g === vals[0]);
const wallGlyphs = new Set(
  ["wallNear", "wallMid", "wallFar", "wallSide", "ceil", "floorNear"].map(
    (k) => mapped[k].glyph
  )
);

console.log(JSON.stringify({ mapped, uniqueNonSpace: unique, wallBandGlyphs: [...wallGlyphs] }, null, 2));

if (allSame) {
  console.error("FAIL: all sample surfaces map to the same glyph (" + vals[0] + ")");
  process.exit(1);
}
if (unique < 5) {
  console.error("FAIL: expected >=5 distinct non-space glyphs, got " + unique);
  process.exit(1);
}
if (wallBandGlyphsUniqueTooLow()) {
  console.error("FAIL: ceiling/floor/walls not distinguishable enough");
  process.exit(1);
}
// Guard the original bug: must not be a solid field of `a`
const aCount = vals.filter((g) => g === "a").length;
if (aCount >= vals.length - 1) {
  console.error("FAIL: nearly all samples are glyph 'a' (bug #95 regression)");
  process.exit(1);
}

console.log("OK: FPV ascii luminance diversity smoke passed (" + unique + " glyphs)");
process.exit(0);

function wallBandGlyphsUniqueTooLow() {
  return wallGlyphs.size < 3;
}
