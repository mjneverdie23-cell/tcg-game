import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { DINO_CLASSES, RARITIES, type CreatureDatabase } from './types';

/**
 * Integrity checks for the scraped database. Skipped until
 * `npm run scrape` has produced creatures.json (needs network access to the
 * fandom wiki); from then on they guard every future scrape.
 */
// Vitest runs with cwd at the project root; import.meta.url is not a file
// URL under the jsdom environment, so resolve from cwd instead.
const DB_PATH = path.resolve('src/database/creatures.json');
const ART_DIR = path.resolve('src/assets/creatures');

// Read lazily: a skipped describe body still runs at collection time.
const loadDatabase = (): CreatureDatabase =>
  JSON.parse(readFileSync(DB_PATH, 'utf8')) as CreatureDatabase;

describe.skipIf(!existsSync(DB_PATH))('creatures.json integrity', () => {
  it('has a meaningful roster size', () => {
    expect(loadDatabase().creatures.length).toBeGreaterThanOrEqual(50);
  });

  it('has unique, well-formed ids', () => {
    const ids = loadDatabase().creatures.map((creature) => creature.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/);
  });

  it('only uses the four classes and five rarities', () => {
    for (const creature of loadDatabase().creatures) {
      expect(DINO_CLASSES).toContain(creature.class);
      expect(RARITIES).toContain(creature.rarity);
    }
  });

  it('covers every class', () => {
    const present = new Set(loadDatabase().creatures.map((creature) => creature.class));
    for (const dinoClass of DINO_CLASSES) expect(present).toContain(dinoClass);
  });

  it('has sane generations and evolution tiers', () => {
    for (const creature of loadDatabase().creatures) {
      expect(creature.generation).toBeGreaterThanOrEqual(1);
      expect(creature.evolutionTier).toBeGreaterThanOrEqual(1);
    }
  });

  it('references downloaded art for every creature', () => {
    for (const creature of loadDatabase().creatures) {
      expect(creature.image).toBe(`${creature.id}.webp`);
      expect(existsSync(path.join(ART_DIR, creature.image))).toBe(true);
    }
  });
});
