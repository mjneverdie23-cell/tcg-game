import type { Rarity } from '../database/types';
import { createRng, type Rng } from './rng';
import type { Card, CardSet } from './types';

/**
 * Pack opening: definitions, per-slot rarity odds and duplicate protection.
 * Opening is seeded, so a given seed + collection state always yields the
 * same cards (testable, and immune to reroll cheating via reload).
 */

export interface PackDefinition {
  id: string;
  name: string;
  description: string;
  /** Coin price; 0 = the daily free pack. */
  price: number;
  /** Rarity weights per card slot (weights need not sum to 100). */
  slots: readonly Readonly<Record<Rarity, number>>[];
}

const STANDARD_SLOT: Readonly<Record<Rarity, number>> = {
  common: 72,
  rare: 24,
  epic: 4,
  legendary: 0,
  mythic: 0,
};

const PREMIUM_SLOT: Readonly<Record<Rarity, number>> = {
  common: 0,
  rare: 58,
  epic: 30,
  legendary: 9,
  mythic: 3,
};

const CHASE_SLOT: Readonly<Record<Rarity, number>> = {
  common: 0,
  rare: 0,
  epic: 62,
  legendary: 28,
  mythic: 10,
};

export const PACKS: readonly PackDefinition[] = [
  {
    id: 'dawn',
    name: 'Dawn Pack',
    description: 'Your free pack — a new one hatches every 24 hours.',
    price: 0,
    slots: [STANDARD_SLOT, STANDARD_SLOT, STANDARD_SLOT, STANDARD_SLOT, PREMIUM_SLOT],
  },
  {
    id: 'primal',
    name: 'Primal Pack',
    description: 'Five cards with a guaranteed epic-or-better chase slot.',
    price: 100,
    slots: [STANDARD_SLOT, STANDARD_SLOT, STANDARD_SLOT, PREMIUM_SLOT, CHASE_SLOT],
  },
];

export function getPack(id: string): PackDefinition {
  const pack = PACKS.find((entry) => entry.id === id);
  if (pack === undefined) throw new Error(`Unknown pack: ${id}`);
  return pack;
}

/** Cards that can appear in packs (dinos, trainers and fields — not energy). */
export function packPool(cardSet: CardSet): readonly Card[] {
  return [...cardSet.dinos, ...cardSet.trainers, ...cardSet.fields];
}

function rollRarity(weights: Readonly<Record<Rarity, number>>, rng: Rng): Rarity {
  const entries = Object.entries(weights) as [Rarity, number][];
  const total = entries.reduce((sum, [, weight]) => sum + weight, 0);
  let roll = rng.next() * total;
  for (const [rarity, weight] of entries) {
    roll -= weight;
    if (roll < 0) return rarity;
  }
  return entries[entries.length - 1]?.[0] ?? 'common';
}

/**
 * Open a pack. Duplicate protection, in priority order:
 *  1. no card appears twice in the same pack,
 *  2. cards the player doesn't own yet are strongly preferred (up to 4
 *     rerolls per slot) within the rolled rarity,
 *  3. if the rolled rarity has no cards at all, fall back to the whole pool.
 */
export function openPack(
  pack: PackDefinition,
  cardSet: CardSet,
  ownedIds: ReadonlySet<string>,
  seed: string,
): Card[] {
  const rng = createRng(seed);
  const pool = packPool(cardSet);
  if (pool.length === 0) throw new Error('Card pool is empty');
  const drawn = new Set<string>();

  return pack.slots.map((weights) => {
    const rarity = rollRarity(weights, rng);
    const rarityPool = pool.filter((card) => card.rarity === rarity && !drawn.has(card.id));
    const candidates = rarityPool.length > 0 ? rarityPool : pool.filter((c) => !drawn.has(c.id));
    const fresh = candidates.filter((card) => !ownedIds.has(card.id));

    let card = rng.pick(candidates);
    for (let reroll = 0; reroll < 4 && ownedIds.has(card.id) && fresh.length > 0; reroll++) {
      card = rng.pick(fresh);
    }
    drawn.add(card.id);
    return card;
  });
}

/** Milliseconds in the daily-pack cooldown. */
export const DAILY_PACK_COOLDOWN_MS = 24 * 60 * 60 * 1000;

export function dailyPackReadyAt(lastClaimAt: number | null): number {
  return lastClaimAt === null ? 0 : lastClaimAt + DAILY_PACK_COOLDOWN_MS;
}
