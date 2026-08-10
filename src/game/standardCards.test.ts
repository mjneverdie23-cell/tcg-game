import { describe, expect, it } from 'vitest';
import { DINO_CLASSES } from '../database/types';
import { FIELD_CARDS, INSTINCT_CARDS, TRAINER_CARDS } from './standardCards';

describe('standard cards', () => {
  it('all ids are unique and namespaced by kind', () => {
    const all = [...TRAINER_CARDS, ...FIELD_CARDS, ...INSTINCT_CARDS];
    expect(new Set(all.map((card) => card.id)).size).toBe(all.length);
    for (const card of TRAINER_CARDS) expect(card.id).toMatch(/^trainer:/);
    for (const card of FIELD_CARDS) expect(card.id).toMatch(/^field:/);
    for (const card of INSTINCT_CARDS) expect(card.id).toMatch(/^instinct:/);
  });

  it('ships the six fields from the design spec', () => {
    expect(FIELD_CARDS.map((card) => card.name).sort()).toEqual([
      'Ancient Swamp',
      'Dense Jungle',
      'Ice Valley',
      'Mountain Cliffs',
      'River Delta',
      'Volcanic Plains',
    ]);
  });

  it('provides exactly one Instinct card per class', () => {
    expect(INSTINCT_CARDS.map((card) => card.class).sort()).toEqual([...DINO_CLASSES].sort());
  });

  it('includes both items and supports', () => {
    const kinds = new Set(TRAINER_CARDS.map((card) => card.trainerKind));
    expect(kinds).toEqual(new Set(['item', 'support']));
  });

  it('every card has display text', () => {
    for (const card of [...TRAINER_CARDS, ...FIELD_CARDS, ...INSTINCT_CARDS]) {
      expect(card.text.length).toBeGreaterThan(10);
    }
  });
});
