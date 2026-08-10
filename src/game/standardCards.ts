import type { FieldCard, InstinctCard, TrainerCard } from './types';

/**
 * Hand-authored standard cards: trainers, fields and Instinct energy.
 * These ship with the game (unlike dino cards, which are generated from the
 * scraped creature database) and are referenced by id in decks.
 */

export const TRAINER_CARDS: readonly TrainerCard[] = [
  {
    id: 'trainer:dino-berry',
    kind: 'trainer',
    trainerKind: 'item',
    name: 'Dino Berry',
    rarity: 'common',
    text: 'Heal 30 damage from your active dinosaur.',
    effect: { type: 'heal', amount: 30 },
  },
  {
    id: 'trainer:amber-charm',
    kind: 'trainer',
    trainerKind: 'item',
    name: 'Amber Charm',
    rarity: 'common',
    text: 'Draw 2 cards.',
    effect: { type: 'draw', count: 2 },
  },
  {
    id: 'trainer:fossil-whistle',
    kind: 'trainer',
    trainerKind: 'item',
    name: 'Fossil Whistle',
    rarity: 'rare',
    text: 'Put a random basic dinosaur from your deck into your hand.',
    effect: { type: 'search-dino' },
  },
  {
    id: 'trainer:adrenaline-gland',
    kind: 'trainer',
    trainerKind: 'item',
    name: 'Adrenaline Gland',
    rarity: 'rare',
    text: 'Your attacks deal +20 damage this turn.',
    effect: { type: 'damage-boost', amount: 20 },
  },
  {
    id: 'trainer:park-ranger',
    kind: 'trainer',
    trainerKind: 'support',
    name: 'Park Ranger',
    rarity: 'rare',
    text: 'Heal 20 damage from each of your dinosaurs.',
    effect: { type: 'heal-all', amount: 20 },
  },
  {
    id: 'trainer:paleontologist',
    kind: 'trainer',
    trainerKind: 'support',
    name: 'Paleontologist',
    rarity: 'epic',
    text: 'Draw cards until you have 5 in hand.',
    effect: { type: 'draw-to', handSize: 5 },
  },
  {
    id: 'trainer:dino-handler',
    kind: 'trainer',
    trainerKind: 'support',
    name: 'Dino Handler',
    rarity: 'common',
    text: 'Switch your active dinosaur with one on your bench.',
    effect: { type: 'switch' },
  },
  {
    id: 'trainer:egg-incubator',
    kind: 'trainer',
    trainerKind: 'support',
    name: 'Egg Incubator',
    rarity: 'epic',
    text: 'You may attach one additional Instinct card this turn.',
    effect: { type: 'bonus-instinct' },
  },
];

export const FIELD_CARDS: readonly FieldCard[] = [
  {
    id: 'field:dense-jungle',
    kind: 'field',
    name: 'Dense Jungle',
    rarity: 'rare',
    text: 'Herbivores (both players) get +20 HP.',
    effect: { type: 'hp-bonus', class: 'herbivore', amount: 20 },
  },
  {
    id: 'field:volcanic-plains',
    kind: 'field',
    name: 'Volcanic Plains',
    rarity: 'rare',
    text: 'Carnivore attacks deal +10 damage.',
    effect: { type: 'damage-bonus', class: 'carnivore', amount: 10 },
  },
  {
    id: 'field:river-delta',
    kind: 'field',
    name: 'River Delta',
    rarity: 'rare',
    text: 'Amphibians heal 10 damage at the end of each turn.',
    effect: { type: 'heal-per-turn', class: 'amphibian', amount: 10 },
  },
  {
    id: 'field:mountain-cliffs',
    kind: 'field',
    name: 'Mountain Cliffs',
    rarity: 'rare',
    text: 'Pterosaurs retreat for free.',
    effect: { type: 'free-retreat', class: 'pterosaur' },
  },
  {
    id: 'field:ancient-swamp',
    kind: 'field',
    name: 'Ancient Swamp',
    rarity: 'epic',
    text: 'Retreating costs +1 Instinct, except for amphibians.',
    effect: { type: 'retreat-penalty', exemptClass: 'amphibian', amount: 1 },
  },
  {
    id: 'field:ice-valley',
    kind: 'field',
    name: 'Ice Valley',
    rarity: 'epic',
    text: 'All dinosaurs retreat for 1 less Instinct.',
    effect: { type: 'retreat-discount', amount: 1 },
  },
];

export const INSTINCT_CARDS: readonly InstinctCard[] = [
  {
    id: 'instinct:carnivore',
    kind: 'instinct',
    class: 'carnivore',
    name: 'Hunter Instinct',
    rarity: 'common',
    text: 'Provides 1 Carnivore Instinct.',
  },
  {
    id: 'instinct:herbivore',
    kind: 'instinct',
    class: 'herbivore',
    name: 'Grazer Instinct',
    rarity: 'common',
    text: 'Provides 1 Herbivore Instinct.',
  },
  {
    id: 'instinct:pterosaur',
    kind: 'instinct',
    class: 'pterosaur',
    name: 'Soarer Instinct',
    rarity: 'common',
    text: 'Provides 1 Pterosaur Instinct.',
  },
  {
    id: 'instinct:amphibian',
    kind: 'instinct',
    class: 'amphibian',
    name: 'Lurker Instinct',
    rarity: 'common',
    text: 'Provides 1 Amphibian Instinct.',
  },
];
