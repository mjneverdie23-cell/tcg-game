import { describe, expect, it } from 'vitest';
import type { CreatureRecord, Rarity } from '../database/types';
import { buildEvolutionChains, generateDinoCard, generateDinoCards } from './cardgen';
import { weaknessOf, resistanceOf, CLASS_WHEEL } from './types';

const creature = (overrides: Partial<CreatureRecord> = {}): CreatureRecord => ({
  id: 'tyrannosaurus-rex',
  name: 'Tyrannosaurus rex',
  class: 'carnivore',
  rarity: 'epic',
  generation: 1,
  evolutionTier: 1,
  description: 'The apex predator.',
  image: 'tyrannosaurus-rex.webp',
  ...overrides,
});

describe('class wheel', () => {
  it('forms a complete cycle covering all four classes', () => {
    const classes = Object.keys(CLASS_WHEEL);
    expect(new Set(Object.values(CLASS_WHEEL)).size).toBe(4);
    for (const dinoClass of classes) {
      expect(classes).toContain(CLASS_WHEEL[dinoClass as keyof typeof CLASS_WHEEL]);
    }
  });

  it('weakness and resistance are consistent with the wheel', () => {
    expect(weaknessOf('herbivore')).toBe('carnivore'); // carnivores hunt herbivores
    expect(resistanceOf('carnivore')).toBe('herbivore');
    expect(weaknessOf('carnivore')).toBe('pterosaur');
  });
});

describe('generateDinoCard', () => {
  it('is fully deterministic', () => {
    expect(generateDinoCard(creature())).toEqual(generateDinoCard(creature()));
  });

  it('keeps HP inside the rarity band (rounded to 10)', () => {
    const bands: Record<Rarity, [number, number]> = {
      common: [60, 80],
      rare: [80, 110],
      epic: [110, 140],
      legendary: [140, 170],
      mythic: [170, 200],
    };
    for (const [rarity, [min, max]] of Object.entries(bands) as [Rarity, [number, number]][]) {
      for (let i = 0; i < 25; i++) {
        const card = generateDinoCard(creature({ id: `dino-${rarity}-${i}`, rarity }));
        expect(card.hp).toBeGreaterThanOrEqual(min - 5); // rounding tolerance
        expect(card.hp).toBeLessThanOrEqual(max + 5);
        expect(card.hp % 10).toBe(0);
      }
    }
  });

  it('adds a stage bonus for evolved forms', () => {
    const basic = generateDinoCard(creature({ id: 'x', evolutionTier: 1 }));
    const evolved = generateDinoCard(creature({ id: 'x', evolutionTier: 2 }));
    expect(evolved.hp).toBe(basic.hp + 20);
    expect(evolved.stage).toBe(2);
  });

  it('generates 1–2 attacks with valid costs, unique names and 10-step damage', () => {
    for (let i = 0; i < 50; i++) {
      const card = generateDinoCard(creature({ id: `atk-${i}`, rarity: i % 2 ? 'common' : 'mythic' }));
      expect(card.attacks.length).toBeGreaterThanOrEqual(1);
      expect(card.attacks.length).toBeLessThanOrEqual(2);
      expect(new Set(card.attacks.map((a) => a.name)).size).toBe(card.attacks.length);
      for (const attack of card.attacks) {
        expect(attack.damage).toBeGreaterThanOrEqual(10);
        expect(attack.damage % 10).toBe(0);
        expect(attack.cost.length).toBeGreaterThanOrEqual(1);
        expect(attack.cost.length).toBeLessThanOrEqual(3);
        expect(attack.cost[0]).toBe(card.class); // first pip is always on-class
      }
    }
  });

  it('non-common cards always get two attacks', () => {
    for (let i = 0; i < 20; i++) {
      expect(generateDinoCard(creature({ id: `r-${i}`, rarity: 'rare' })).attacks).toHaveLength(2);
    }
  });

  it('derives retreat cost from bulk', () => {
    expect(generateDinoCard(creature({ id: 'small', rarity: 'common' })).retreatCost).toBe(1);
    expect(generateDinoCard(creature({ id: 'big', rarity: 'mythic' })).retreatCost).toBe(3);
  });
});

describe('buildEvolutionChains', () => {
  const roster: CreatureRecord[] = [
    creature({ id: 'raptor-a', evolutionTier: 1 }),
    creature({ id: 'raptor-b', evolutionTier: 1 }),
    creature({ id: 'hybrid-x', evolutionTier: 2 }),
    creature({ id: 'lonely-herb', class: 'herbivore', evolutionTier: 2 }),
  ];

  it('links evolutions to a same-class lower tier, deterministically', () => {
    const chains = buildEvolutionChains(roster);
    const from = chains.get('hybrid-x');
    expect(['raptor-a', 'raptor-b']).toContain(from);
    expect(buildEvolutionChains(roster).get('hybrid-x')).toBe(from);
  });

  it('leaves evolutions without a lower tier unlinked (they play as basic)', () => {
    expect(buildEvolutionChains(roster).get('lonely-herb')).toBeUndefined();
  });

  it('wires evolvesFrom into generated cards', () => {
    const cards = generateDinoCards(roster);
    const hybrid = cards.find((card) => card.creatureId === 'hybrid-x');
    expect(hybrid?.evolvesFrom).toBeDefined();
    const basic = cards.find((card) => card.creatureId === 'raptor-a');
    expect(basic?.evolvesFrom).toBeUndefined();
  });
});
