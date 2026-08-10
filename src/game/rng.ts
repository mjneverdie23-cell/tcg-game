/**
 * Deterministic pseudo-random number generation.
 *
 * Card generation must be reproducible: the same creature database always
 * yields exactly the same cards on every device (collections reference card
 * ids). Battle shuffling reuses the same primitives with per-match seeds.
 */

/** FNV-1a 32-bit string hash — stable, fast, good enough for seeding. */
export function hashString(input: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/** Mulberry32 PRNG — returns floats in [0, 1). */
export function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface Rng {
  /** Float in [0, 1). */
  next: () => number;
  /** Integer in [min, max] (inclusive). */
  int: (min: number, max: number) => number;
  /** Uniformly picked element. Throws on empty input. */
  pick: <T>(items: readonly T[]) => T;
  /** In-place Fisher–Yates shuffle; returns the same array. */
  shuffle: <T>(items: T[]) => T[];
}

export function createRng(seed: string | number): Rng {
  const next = mulberry32(typeof seed === 'number' ? seed : hashString(seed));
  const int = (min: number, max: number) => min + Math.floor(next() * (max - min + 1));
  return {
    next,
    int,
    pick: (items) => {
      if (items.length === 0) throw new Error('pick() on empty array');
      return items[int(0, items.length - 1)] as (typeof items)[number];
    },
    shuffle: (items) => {
      for (let i = items.length - 1; i > 0; i--) {
        const j = int(0, i);
        const tmp = items[i] as (typeof items)[number];
        items[i] = items[j] as (typeof items)[number];
        items[j] = tmp;
      }
      return items;
    },
  };
}
