/**
 * Renders the PWA icon set from the master SVG (public/favicon.svg).
 * Run with: npm run icons
 */
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';

const PUBLIC_DIR = new URL('../public/', import.meta.url).pathname;
const svg = await readFile(path.join(PUBLIC_DIR, 'favicon.svg'));

const BACKGROUND = '#0d1226'; // matches the icon's gradient midpoint

async function renderPlain(size, filename) {
  await sharp(svg, { density: 300 })
    .resize(size, size)
    .png()
    .toFile(path.join(PUBLIC_DIR, filename));
  console.log(`✓ ${filename}`);
}

/**
 * Maskable icons get cropped to arbitrary shapes by the OS, so the artwork
 * must sit inside the central 80% "safe zone" on a full-bleed background.
 */
async function renderMaskable(size, filename) {
  const inner = Math.round(size * 0.8);
  const icon = await sharp(svg, { density: 300 }).resize(inner, inner).png().toBuffer();
  await sharp({
    create: { width: size, height: size, channels: 4, background: BACKGROUND },
  })
    .composite([{ input: icon, gravity: 'center' }])
    .png()
    .toFile(path.join(PUBLIC_DIR, filename));
  console.log(`✓ ${filename}`);
}

await renderPlain(192, 'pwa-192x192.png');
await renderPlain(512, 'pwa-512x512.png');
await renderPlain(180, 'apple-touch-icon.png');
await renderMaskable(512, 'maskable-icon-512x512.png');
