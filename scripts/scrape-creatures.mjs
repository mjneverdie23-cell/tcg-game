/**
 * Creature database scraper.
 *
 * Builds the local card database from the Jurassic World: The Game fandom
 * wiki (https://jurassic-world-the-mobile-game.fandom.com):
 *
 *   1. Reads the roster from the "List of All Creatures" page (MediaWiki API).
 *   2. Fetches every creature page's infobox, intro text and main image.
 *   3. Downloads each image, resizes it and converts to WebP in
 *      src/assets/creatures/.
 *   4. Writes src/database/creatures.json (schema: src/database/types.ts).
 *
 * Images are never hotlinked at runtime — the game ships with the downloaded
 * art. Run with: npm run scrape   (add --force to re-download existing images)
 *
 * The script is idempotent and polite: batched API queries, limited download
 * concurrency, and it fails loudly with per-page reasons instead of writing a
 * partial database silently.
 */
import { mkdir, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
import {
  buildRoster,
  deriveEvolutionTier,
  deriveGeneration,
  extractSectionLinks,
  mapRarity,
  normalizeClass,
  parseInfobox,
  pickField,
  slugify,
  tidyDescription,
} from './scrape-lib.mjs';

const WIKI_ORIGIN = 'https://jurassic-world-the-mobile-game.fandom.com';
const API = `${WIKI_ORIGIN}/api.php`;
const LIST_PAGE = 'List_of_All_Creatures';
const USER_AGENT = 'PrimordiaScraper/1.0 (personal fan project; contact via repo)';

const ROOT = new URL('..', import.meta.url).pathname;
const ART_DIR = path.join(ROOT, 'src/assets/creatures');
const DB_FILE = path.join(ROOT, 'src/database/creatures.json');

const FORCE = process.argv.includes('--force');
const API_BATCH = 20; // exlimit caps extracts at 20 titles per query
const DOWNLOAD_CONCURRENCY = 4;
const IMAGE_MAX_SIZE = 640;
const MIN_EXPECTED_CREATURES = 50;

async function fetchWithRetry(url, init = {}, attempts = 4) {
  for (let attempt = 1; ; attempt++) {
    try {
      const response = await fetch(url, {
        ...init,
        headers: { 'user-agent': USER_AGENT, ...init.headers },
      });
      if (response.status === 403) {
        throw new Error(
          `403 Forbidden from ${new URL(url).host} — if you are running inside a ` +
            `restricted environment, allow this host in the network policy first.`,
        );
      }
      if (!response.ok && response.status >= 500 && attempt < attempts) {
        throw new Error(`retryable HTTP ${response.status}`);
      }
      if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
      return response;
    } catch (error) {
      if (attempt >= attempts || String(error).includes('403 Forbidden')) throw error;
      const delay = 500 * 2 ** attempt;
      console.warn(`  retry ${attempt}/${attempts - 1} in ${delay}ms: ${error.message}`);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}

async function apiQuery(params) {
  const url = new URL(API);
  for (const [key, value] of Object.entries({ format: 'json', ...params })) {
    url.searchParams.set(key, value);
  }
  const response = await fetchWithRetry(url);
  return response.json();
}

/** Roster of creature pages from the list page, grouped by class section. */
async function fetchRoster() {
  const data = await apiQuery({ action: 'parse', page: LIST_PAGE, prop: 'wikitext' });
  const wikitext = data.parse?.wikitext?.['*'];
  if (typeof wikitext !== 'string' || wikitext.length === 0) {
    throw new Error(`Could not read wikitext of ${LIST_PAGE} — response: ${JSON.stringify(data).slice(0, 400)}`);
  }
  const roster = buildRoster(extractSectionLinks(wikitext));
  if (roster.length === 0) throw new Error(`No creature links found on ${LIST_PAGE}`);
  return roster;
}

/** Infobox wikitext, intro extract and original image URL for up to 20 titles. */
async function fetchPageBatch(titles) {
  const data = await apiQuery({
    action: 'query',
    titles: titles.join('|'),
    redirects: '1',
    prop: 'revisions|extracts|pageimages',
    rvprop: 'content',
    rvslots: 'main',
    exintro: '1',
    explaintext: '1',
    exlimit: 'max',
    piprop: 'original',
  });
  const pages = Object.values(data.query?.pages ?? {});
  const redirects = new Map(
    (data.query?.redirects ?? []).map((r) => [r.to, r.from]),
  );
  return pages.map((page) => ({
    // Report under the roster's original title so lookups stay consistent.
    title: redirects.get(page.title) ?? page.title,
    missing: 'missing' in page,
    wikitext: page.revisions?.[0]?.slots?.main?.['*'] ?? '',
    extract: page.extract ?? '',
    imageUrl: page.original?.source ?? null,
  }));
}

/** Download `imageUrl`, fit inside 640×640, save as WebP. Returns the filename. */
async function downloadArt(imageUrl, slug) {
  const filename = `${slug}.webp`;
  const target = path.join(ART_DIR, filename);
  if (!FORCE && existsSync(target)) return filename;
  const response = await fetchWithRetry(imageUrl);
  const original = Buffer.from(await response.arrayBuffer());
  await sharp(original)
    .resize(IMAGE_MAX_SIZE, IMAGE_MAX_SIZE, { fit: 'inside', withoutEnlargement: true })
    .webp({ quality: 82 })
    .toFile(target);
  return filename;
}

async function main() {
  await mkdir(ART_DIR, { recursive: true });
  await mkdir(path.dirname(DB_FILE), { recursive: true });

  console.log(`Fetching roster from ${LIST_PAGE} …`);
  const roster = await fetchRoster();
  console.log(`  ${roster.length} linked pages found`);

  const bySection = new Map(roster.map((entry) => [entry.title, entry.sectionClass]));
  const creatures = [];
  const skipped = [];

  for (let i = 0; i < roster.length; i += API_BATCH) {
    const batch = roster.slice(i, i + API_BATCH).map((entry) => entry.title);
    console.log(`Pages ${i + 1}–${i + batch.length} of ${roster.length} …`);
    for (const page of await fetchPageBatch(batch)) {
      if (page.missing) {
        skipped.push({ title: page.title, reason: 'page missing' });
        continue;
      }
      const fields = parseInfobox(page.wikitext);
      const dinoClass =
        normalizeClass(pickField(fields, ['class', 'type', 'creature type']) ?? '') ??
        bySection.get(page.title) ??
        null;
      if (dinoClass === null) {
        skipped.push({ title: page.title, reason: 'no carnivore/herbivore/pterosaur/amphibian class' });
        continue;
      }
      if (page.imageUrl === null) {
        skipped.push({ title: page.title, reason: 'no main image' });
        continue;
      }
      const rawRarity = pickField(fields, ['rarity', 'rarity level']);
      const rarity = mapRarity(rawRarity ?? '') ?? 'common';
      if (rawRarity !== null && mapRarity(rawRarity) === null) {
        console.warn(`  unmapped rarity "${rawRarity}" on ${page.title} → common`);
      }
      creatures.push({
        id: slugify(page.title),
        name: page.title,
        class: dinoClass,
        rarity,
        generation: deriveGeneration(fields, page.title),
        evolutionTier: deriveEvolutionTier(fields),
        description: tidyDescription(page.extract),
        image: '', // filled in after download below
        imageUrl: page.imageUrl,
      });
    }
  }

  // Unique ids are a schema invariant — bail out before downloading anything.
  const ids = new Set();
  for (const creature of creatures) {
    if (ids.has(creature.id)) throw new Error(`Duplicate creature id: ${creature.id}`);
    ids.add(creature.id);
  }

  console.log(`Downloading art for ${creatures.length} creatures …`);
  const queue = [...creatures];
  const failures = [];
  await Promise.all(
    Array.from({ length: DOWNLOAD_CONCURRENCY }, async () => {
      for (let item = queue.shift(); item !== undefined; item = queue.shift()) {
        try {
          item.image = await downloadArt(item.imageUrl, item.id);
        } catch (error) {
          failures.push({ title: item.name, reason: String(error.message) });
        }
      }
    }),
  );
  if (failures.length > 0) {
    for (const failure of failures) console.error(`  art failed: ${failure.title} — ${failure.reason}`);
    throw new Error(`${failures.length} image downloads failed; database not written`);
  }

  creatures.sort((a, b) => a.class.localeCompare(b.class) || a.name.localeCompare(b.name));
  const database = {
    source: `${WIKI_ORIGIN}/wiki/${LIST_PAGE}`,
    scrapedAt: new Date().toISOString(),
    creatures: creatures.map(({ imageUrl: _drop, ...record }) => record),
  };
  await writeFile(DB_FILE, `${JSON.stringify(database, null, 2)}\n`);

  const counts = (key) =>
    [...creatures.reduce((m, c) => m.set(c[key], (m.get(c[key]) ?? 0) + 1), new Map())]
      .map(([k, n]) => `${k}: ${n}`)
      .join(', ');
  console.log(`\nWrote ${creatures.length} creatures to ${path.relative(ROOT, DB_FILE)}`);
  console.log(`  by class  — ${counts('class')}`);
  console.log(`  by rarity — ${counts('rarity')}`);
  if (skipped.length > 0) {
    console.log(`  skipped ${skipped.length}:`);
    for (const s of skipped) console.log(`    - ${s.title} (${s.reason})`);
  }
  if (creatures.length < MIN_EXPECTED_CREATURES) {
    throw new Error(
      `Only ${creatures.length} creatures scraped (expected ≥ ${MIN_EXPECTED_CREATURES}) — page layout may have changed`,
    );
  }
}

main().catch((error) => {
  console.error(`\nScrape failed: ${error.message}`);
  process.exitCode = 1;
});
