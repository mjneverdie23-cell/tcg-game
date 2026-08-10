/**
 * Exports the web app's card pool to the Godot project's JSON database
 * (godot/database/cards.json), preserving the original game's data and the
 * deterministic dino stats during the Godot migration.
 *
 * Run with: npm run export:godot
 *
 * Once the Python scraper (tools/jurassic_scraper.py, Milestone 2) owns
 * creature data, it regenerates the same file; this exporter remains the
 * source for the hand-authored trainer/field/instinct cards.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { generateDinoCards } from '../src/game/cardgen';
import { FIELD_CARDS, INSTINCT_CARDS, TRAINER_CARDS } from '../src/game/standardCards';
import { STARTER_CREATURES } from '../src/database/starterCreatures';

const OUT_FILE = path.resolve(__dirname, '../godot/database/cards.json');

/** camelCase → snake_case for effect payload keys (GDScript convention). */
function snakeCaseKeys(effect: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(effect).map(([key, value]) => [
      key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`),
      value,
    ]),
  );
}

const dinos = generateDinoCards(STARTER_CREATURES).map((card) => ({
  id: card.id,
  name: card.name,
  type: card.class,
  rarity: card.rarity,
  hp: card.hp,
  stage: card.stage,
  evolves_from: card.evolvesFrom === undefined ? '' : `dino:${card.evolvesFrom}`,
  attacks: card.attacks.map((attack) => ({
    name: attack.name,
    cost: attack.cost,
    damage: attack.damage,
  })),
  retreat_cost: card.retreatCost,
  description: card.description,
  image: card.image === '' ? '' : `assets/textures/cards/${card.image}`,
}));

const trainers = TRAINER_CARDS.map((card) => ({
  id: card.id,
  name: card.name,
  rarity: card.rarity,
  trainer_kind: card.trainerKind,
  text: card.text,
  effect: snakeCaseKeys(card.effect),
}));

const fields = FIELD_CARDS.map((card) => ({
  id: card.id,
  name: card.name,
  rarity: card.rarity,
  text: card.text,
  effect: snakeCaseKeys(card.effect),
}));

const instincts = INSTINCT_CARDS.map((card) => ({
  id: card.id,
  name: card.name,
  rarity: card.rarity,
  type: card.class,
  text: card.text,
}));

const database = { version: 1, dinos, trainers, fields, instincts };
mkdirSync(path.dirname(OUT_FILE), { recursive: true });
writeFileSync(OUT_FILE, `${JSON.stringify(database, null, 2)}\n`);
console.log(
  `Wrote ${dinos.length} dinos, ${trainers.length} trainers, ${fields.length} fields, ${instincts.length} instincts → ${path.relative(process.cwd(), OUT_FILE)}`,
);
