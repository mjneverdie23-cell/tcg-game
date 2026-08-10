import type { CreatureRecord, DinoClass, Rarity } from '../database/types';
import { createRng } from './rng';
import { resistanceOf, weaknessOf, type Attack, type DinoCard, type InstinctPip } from './types';

/**
 * Deterministic dino card generation.
 *
 * The wiki provides identity (name, class, rarity, art, lore); gameplay
 * stats are derived here, seeded by the creature id, so the same database
 * always produces byte-identical cards on every device.
 */

const HP_RANGE: Record<Rarity, readonly [number, number]> = {
  common: [60, 80],
  rare: [80, 110],
  epic: [110, 140],
  legendary: [140, 170],
  mythic: [170, 200],
};

/** Damage scales off HP so rarity lifts both survivability and threat. */
const DAMAGE_FACTOR = 0.45;

const ATTACK_NAMES: Record<DinoClass, readonly string[]> = {
  carnivore: ['Savage Bite', 'Rending Claws', 'Apex Strike', 'Bone Crusher', 'Blood Frenzy', 'Ambush'],
  herbivore: ['Tail Slam', 'Stampede', 'Horn Charge', 'Thorned Hide', 'Ground Shaker', 'Canopy Crush'],
  pterosaur: ['Dive Bomb', 'Wing Slash', 'Sky Screech', 'Talon Snatch', 'Gale Force', 'Updraft'],
  amphibian: ['Tidal Snap', 'Swamp Ambush', 'Drowning Grip', 'Mud Spray', 'River Rush', 'Deep Lurk'],
};

function roundTo10(value: number): number {
  return Math.round(value / 10) * 10;
}

/**
 * Map evolution stage relationships across the whole roster: every stage-N
 * creature (N > 1) evolves from a deterministic stage-(N-1) creature of the
 * same class. Multiple evolutions may share a pre-stage (like real TCGs).
 */
export function buildEvolutionChains(creatures: readonly CreatureRecord[]): Map<string, string> {
  const evolvesFrom = new Map<string, string>();
  const byClassAndTier = new Map<string, CreatureRecord[]>();
  for (const creature of creatures) {
    const key = `${creature.class}:${creature.evolutionTier}`;
    const bucket = byClassAndTier.get(key) ?? [];
    bucket.push(creature);
    byClassAndTier.set(key, bucket);
  }
  for (const bucket of byClassAndTier.values()) {
    bucket.sort((a, b) => a.id.localeCompare(b.id));
  }

  for (const creature of creatures) {
    if (creature.evolutionTier <= 1) continue;
    const candidates = byClassAndTier.get(`${creature.class}:${creature.evolutionTier - 1}`);
    if (candidates === undefined || candidates.length === 0) continue; // stays basic
    const rng = createRng(`evo:${creature.id}`);
    evolvesFrom.set(creature.id, rng.pick(candidates).id);
  }
  return evolvesFrom;
}

function buildAttack(
  creature: CreatureRecord,
  hp: number,
  slot: number,
  usedNames: Set<string>,
): Attack {
  const rng = createRng(`attack:${creature.id}:${slot}`);
  const names = ATTACK_NAMES[creature.class].filter((name) => !usedNames.has(name));
  const name = rng.pick(names);
  usedNames.add(name);

  // Slot 0 is a cheap opener; slot 1 the heavy hitter.
  const pipCount = slot === 0 ? rng.int(1, 2) : rng.int(2, 3);
  const cost: InstinctPip[] = [creature.class];
  for (let i = 1; i < pipCount; i++) {
    cost.push(rng.next() < 0.5 ? creature.class : 'neutral');
  }
  const base = hp * DAMAGE_FACTOR * (slot === 0 ? 0.6 : 1);
  // ±10 jitter keeps same-rarity cards from all having identical numbers.
  const damage = Math.max(10, roundTo10(base + (rng.int(0, 2) - 1) * 10));
  return { name, cost, damage };
}

export function generateDinoCard(
  creature: CreatureRecord,
  evolvesFrom?: string | undefined,
): DinoCard {
  const rng = createRng(`dino:${creature.id}`);
  const [minHp, maxHp] = HP_RANGE[creature.rarity];
  const stageBonus = (Math.min(creature.evolutionTier, 3) - 1) * 20;
  const hp = roundTo10(rng.int(minHp, maxHp)) + stageBonus;

  const usedNames = new Set<string>();
  const attackCount = creature.rarity === 'common' ? rng.int(1, 2) : 2;
  const attacks = Array.from({ length: attackCount }, (_, slot) =>
    buildAttack(creature, hp, slot, usedNames),
  );

  return {
    id: `dino:${creature.id}`,
    kind: 'dino',
    creatureId: creature.id,
    name: creature.name,
    class: creature.class,
    rarity: creature.rarity,
    hp,
    stage: creature.evolutionTier,
    ...(evolvesFrom !== undefined && { evolvesFrom }),
    attacks,
    weakness: weaknessOf(creature.class),
    resistance: resistanceOf(creature.class),
    retreatCost: hp >= 150 ? 3 : hp >= 100 ? 2 : 1,
    description: creature.description,
    image: creature.image,
  };
}

/** Generate every dino card from the scraped roster, evolution links included. */
export function generateDinoCards(creatures: readonly CreatureRecord[]): DinoCard[] {
  const chains = buildEvolutionChains(creatures);
  return creatures.map((creature) => generateDinoCard(creature, chains.get(creature.id)));
}
