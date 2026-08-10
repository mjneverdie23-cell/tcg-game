/**
 * Creature database schema — the contract between the scraper
 * (scripts/scrape-creatures.mjs, which writes creatures.json) and the game.
 */

/** The four elemental classes. Every dinosaur belongs to exactly one. */
export type DinoClass = 'carnivore' | 'herbivore' | 'pterosaur' | 'amphibian';

export type Rarity = 'common' | 'rare' | 'epic' | 'legendary' | 'mythic';

export const DINO_CLASSES: readonly DinoClass[] = [
  'carnivore',
  'herbivore',
  'pterosaur',
  'amphibian',
];

export const RARITIES: readonly Rarity[] = ['common', 'rare', 'epic', 'legendary', 'mythic'];

export interface CreatureRecord {
  /** Stable slug id, e.g. "tyrannosaurus-rex". Unique across the database. */
  id: string;
  name: string;
  class: DinoClass;
  rarity: Rarity;
  /** Source-game generation (1 unless the wiki says otherwise). */
  generation: number;
  /** 1 = base creature, 2+ = hybrid/evolved forms in the source game. */
  evolutionTier: number;
  description: string;
  /** Art filename under src/assets/creatures/ (downloaded by the scraper). */
  image: string;
}

export interface CreatureDatabase {
  /** Where the data was scraped from. */
  source: string;
  /** ISO timestamp of the scrape. */
  scrapedAt: string;
  creatures: CreatureRecord[];
}
