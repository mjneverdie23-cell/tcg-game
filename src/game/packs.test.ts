import { describe, expect, it } from 'vitest';
import { getCardSet } from '../database';
import { DAILY_PACK_COOLDOWN_MS, dailyPackReadyAt, getPack, openPack, PACKS, packPool } from './packs';

const cardSet = getCardSet();

describe('pack definitions', () => {
  it('ships a free daily pack and a premium pack of 5 cards each', () => {
    expect(PACKS.some((pack) => pack.price === 0)).toBe(true);
    expect(PACKS.some((pack) => pack.price > 0)).toBe(true);
    for (const pack of PACKS) expect(pack.slots).toHaveLength(5);
  });

  it('getPack throws on unknown ids', () => {
    expect(() => getPack('nope')).toThrow();
  });
});

describe('openPack', () => {
  const dawn = getPack('dawn');
  const primal = getPack('primal');

  it('is deterministic for a given seed and collection', () => {
    const a = openPack(dawn, cardSet, new Set(), 'seed-1').map((card) => card.id);
    const b = openPack(dawn, cardSet, new Set(), 'seed-1').map((card) => card.id);
    expect(a).toEqual(b);
  });

  it('never repeats a card within one pack', () => {
    for (let i = 0; i < 200; i++) {
      const ids = openPack(primal, cardSet, new Set(), `dup-${i}`).map((card) => card.id);
      expect(new Set(ids).size).toBe(ids.length);
    }
  });

  it('strongly prefers unowned cards (duplicate protection)', () => {
    // Own everything except one specific common card…
    const pool = packPool(cardSet);
    const target = pool.find((card) => card.rarity === 'common');
    const owned = new Set(pool.map((card) => card.id));
    owned.delete((target as { id: string }).id);
    // …then the missing card should show up far more often than raw odds.
    let hits = 0;
    for (let i = 0; i < 100; i++) {
      const cards = openPack(dawn, cardSet, owned, `pity-${i}`);
      if (cards.some((card) => card.id === (target as { id: string }).id)) hits++;
    }
    expect(hits).toBeGreaterThan(50);
  });

  it('respects slot rarity floors: primal chase slot is epic or better', () => {
    for (let i = 0; i < 100; i++) {
      const chase = openPack(primal, cardSet, new Set(), `chase-${i}`)[4];
      expect(['epic', 'legendary', 'mythic']).toContain(chase?.rarity);
    }
  });
});

describe('daily pack timer', () => {
  it('is immediately ready for new players', () => {
    expect(dailyPackReadyAt(null)).toBe(0);
  });

  it('unlocks 24h after the last claim', () => {
    expect(dailyPackReadyAt(1_000)).toBe(1_000 + DAILY_PACK_COOLDOWN_MS);
  });
});
