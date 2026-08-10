import { generateDinoCards } from '../game/cardgen';
import { FIELD_CARDS, INSTINCT_CARDS, TRAINER_CARDS } from '../game/standardCards';
import type { Card, CardSet } from '../game/types';
import { STARTER_CREATURES } from './starterCreatures';
import type { CreatureDatabase, CreatureRecord } from './types';

/**
 * Card pool entry point. Uses the scraped creatures.json when it exists
 * (glob resolves at build time), otherwise the built-in starter roster —
 * either way the game works fully offline.
 */
const SCRAPED = import.meta.glob('./creatures.json', { eager: true, import: 'default' }) as Record<
  string,
  CreatureDatabase
>;

export function loadCreatures(): readonly CreatureRecord[] {
  return SCRAPED['./creatures.json']?.creatures ?? STARTER_CREATURES;
}

let cachedCardSet: CardSet | undefined;
let cachedById: Map<string, Card> | undefined;

/** The complete card pool (generated dinos + authored standard cards). */
export function getCardSet(): CardSet {
  cachedCardSet ??= {
    dinos: generateDinoCards(loadCreatures()),
    trainers: TRAINER_CARDS,
    fields: FIELD_CARDS,
    instincts: INSTINCT_CARDS,
  };
  return cachedCardSet;
}

/** Every card in the pool as a flat list. */
export function getAllCards(): readonly Card[] {
  const set = getCardSet();
  return [...set.dinos, ...set.trainers, ...set.fields, ...set.instincts];
}

/** Lookup by card id; throws on unknown ids (save data must stay consistent). */
export function getCardById(id: string): Card {
  cachedById ??= new Map(getAllCards().map((card) => [card.id, card]));
  const card = cachedById.get(id);
  if (card === undefined) throw new Error(`Unknown card id: ${id}`);
  return card;
}
