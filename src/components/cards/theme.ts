import type { DinoClass, Rarity } from '../../database/types';

/**
 * Visual theming for classes and rarities, shared by every card-rendering
 * component (and later by battle/collection UI).
 */

export interface ClassTheme {
  /** Display name, capitalized. */
  label: string;
  /** Tailwind text color for icons/labels. */
  text: string;
  /** Solid chip/pip background. */
  bg: string;
  /** Art-area backdrop gradient (also the art fallback). */
  artGradient: string;
}

export const CLASS_THEME: Record<DinoClass, ClassTheme> = {
  carnivore: {
    label: 'Carnivore',
    text: 'text-carnivore',
    bg: 'bg-carnivore',
    artGradient: 'bg-gradient-to-br from-[#4a1210] via-[#2d0b0e] to-night-950',
  },
  herbivore: {
    label: 'Herbivore',
    text: 'text-herbivore',
    bg: 'bg-herbivore',
    artGradient: 'bg-gradient-to-br from-[#123c1e] via-[#0c2615] to-night-950',
  },
  pterosaur: {
    label: 'Pterosaur',
    text: 'text-pterosaur',
    bg: 'bg-pterosaur',
    artGradient: 'bg-gradient-to-br from-[#2c2158] via-[#1b1438] to-night-950',
  },
  amphibian: {
    label: 'Amphibian',
    text: 'text-amphibian',
    bg: 'bg-amphibian',
    artGradient: 'bg-gradient-to-br from-[#0c2f4a] via-[#081d30] to-night-950',
  },
};

export interface RarityTheme {
  label: string;
  /** Gradient used on the card's outer border ring. */
  ring: string;
  /** Extra glow/shadow around the card. */
  glow: string;
  /** Color of the rarity gems under the footer. */
  gem: string;
  /** Number of gem shapes to render (legendary/mythic use special shapes). */
  gems: number;
}

export const RARITY_THEME: Record<Rarity, RarityTheme> = {
  common: {
    label: 'Common',
    ring: 'bg-white/20',
    glow: '',
    gem: 'text-rarity-common',
    gems: 1,
  },
  rare: {
    label: 'Rare',
    ring: 'bg-gradient-to-br from-rarity-rare/80 to-rarity-rare/30',
    glow: 'shadow-[0_0_18px_-4px_var(--color-rarity-rare)]',
    gem: 'text-rarity-rare',
    gems: 2,
  },
  epic: {
    label: 'Epic',
    ring: 'bg-gradient-to-br from-rarity-epic/80 to-rarity-epic/30',
    glow: 'shadow-[0_0_22px_-4px_var(--color-rarity-epic)]',
    gem: 'text-rarity-epic',
    gems: 3,
  },
  legendary: {
    label: 'Legendary',
    ring: 'bg-gradient-to-br from-gold-300 via-gold-500 to-[#8a5a00]',
    glow: 'shadow-[0_0_26px_-4px_var(--color-rarity-legendary)]',
    gem: 'text-rarity-legendary',
    gems: 1,
  },
  mythic: {
    label: 'Mythic',
    ring: 'animate-holo bg-[linear-gradient(120deg,#ff4fa0,#ffb938,#43d96b,#38a8ff,#b18aff,#ff4fa0)] bg-[length:300%_300%]',
    glow: 'shadow-[0_0_30px_-4px_var(--color-rarity-mythic)]',
    gem: 'text-rarity-mythic',
    gems: 1,
  },
};
