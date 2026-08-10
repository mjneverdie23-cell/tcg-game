import type { DinoClass, Rarity } from '../database/types';

/**
 * Card model — the contract between card generation, rendering, deck
 * building and the battle engine.
 *
 * Class match-up wheel (X beats Y ⇒ Y is weak to X, X resists Y):
 *   carnivore → herbivore → amphibian → pterosaur → carnivore
 */

/** One energy pip in an attack cost. `neutral` accepts any Instinct class. */
export type InstinctPip = DinoClass | 'neutral';

export interface Attack {
  name: string;
  cost: readonly InstinctPip[];
  damage: number;
}

interface CardBase {
  /** Unique across all cards, e.g. "dino:tyrannosaurus-rex", "field:dense-jungle". */
  id: string;
  name: string;
  rarity: Rarity;
}

export interface DinoCard extends CardBase {
  kind: 'dino';
  /** CreatureRecord id this card was generated from. */
  creatureId: string;
  class: DinoClass;
  hp: number;
  /** 1 = basic (playable from hand), 2+ = evolution stages. */
  stage: number;
  /** creatureId of the previous stage; only set when stage > 1. */
  evolvesFrom?: string;
  attacks: readonly Attack[];
  weakness: DinoClass;
  resistance: DinoClass;
  retreatCost: number;
  description: string;
  /** Art filename under src/assets/creatures/, '' if art is unavailable. */
  image: string;
}

/** Structured trainer effects — interpreted by the battle engine. */
export type TrainerEffect =
  | { type: 'heal'; amount: number } // heal your active dino
  | { type: 'heal-all'; amount: number } // heal all your dinos
  | { type: 'draw'; count: number }
  | { type: 'draw-to'; handSize: number } // draw until you hold N cards
  | { type: 'search-dino' } // take a random basic dino from your deck
  | { type: 'damage-boost'; amount: number } // your attacks this turn
  | { type: 'switch' } // swap active with a benched dino
  | { type: 'bonus-instinct' }; // may attach one extra Instinct this turn

export interface TrainerCard extends CardBase {
  kind: 'trainer';
  /** Items are unlimited per turn; only one support may be played per turn. */
  trainerKind: 'item' | 'support';
  text: string;
  effect: TrainerEffect;
}

/** Structured field effects — one field is active for both players at a time. */
export type FieldEffect =
  | { type: 'hp-bonus'; class: DinoClass; amount: number }
  | { type: 'damage-bonus'; class: DinoClass; amount: number }
  | { type: 'heal-per-turn'; class: DinoClass; amount: number }
  | { type: 'free-retreat'; class: DinoClass }
  | { type: 'retreat-penalty'; exemptClass: DinoClass; amount: number }
  | { type: 'retreat-discount'; amount: number }; // applies to every dino

export interface FieldCard extends CardBase {
  kind: 'field';
  text: string;
  effect: FieldEffect;
}

export interface InstinctCard extends CardBase {
  kind: 'instinct';
  class: DinoClass;
  text: string;
}

export type Card = DinoCard | TrainerCard | FieldCard | InstinctCard;

/** Full playable card pool: generated dinos + authored standard cards. */
export interface CardSet {
  dinos: readonly DinoCard[];
  trainers: readonly TrainerCard[];
  fields: readonly FieldCard[];
  instincts: readonly InstinctCard[];
}

/** X beats Y ⇒ WHEEL[X] = Y. */
export const CLASS_WHEEL: Record<DinoClass, DinoClass> = {
  carnivore: 'herbivore',
  herbivore: 'amphibian',
  amphibian: 'pterosaur',
  pterosaur: 'carnivore',
};

/** The class that beats `dinoClass` (its weakness). */
export function weaknessOf(dinoClass: DinoClass): DinoClass {
  const entry = (Object.entries(CLASS_WHEEL) as [DinoClass, DinoClass][]).find(
    ([, prey]) => prey === dinoClass,
  );
  // The wheel is a total cycle; every class has exactly one predator.
  return (entry as [DinoClass, DinoClass])[0];
}

/** The class `dinoClass` beats (its resistance). */
export function resistanceOf(dinoClass: DinoClass): DinoClass {
  return CLASS_WHEEL[dinoClass];
}
