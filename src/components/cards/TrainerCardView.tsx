import type { ReactNode } from 'react';
import type { TrainerCard, TrainerEffect } from '../../game/types';
import { RarityGems } from './RarityGems';

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const;

/** Glyph per effect type, shown large in the card's icon well. */
const EFFECT_GLYPHS: Record<TrainerEffect['type'], ReactNode> = {
  heal: <path d="M12 4v16M4 12h16" {...stroke} strokeWidth="2.6" />,
  'heal-all': (
    <>
      <path d="M8 5v10M3 10h10" {...stroke} strokeWidth="2.2" />
      <path d="M16 11v8M12 15h8" {...stroke} strokeWidth="2.2" />
    </>
  ),
  draw: (
    <>
      <rect x="4" y="5" width="10" height="14" rx="1.5" {...stroke} />
      <path d="M14 8h4a1.5 1.5 0 0 1 1.5 1.5V19a1.5 1.5 0 0 1-1.5 1.5h-7" {...stroke} />
    </>
  ),
  'draw-to': (
    <>
      <rect x="4" y="4" width="11" height="15" rx="1.5" {...stroke} />
      <path d="M9.5 8v7M6 11.5h7" {...stroke} />
      <path d="M15 9h3.5a1.5 1.5 0 0 1 1.5 1.5V19a1.5 1.5 0 0 1-1.5 1.5H10" {...stroke} />
    </>
  ),
  'search-dino': (
    <>
      <circle cx="10.5" cy="10.5" r="6" {...stroke} />
      <path d="m15 15 5.5 5.5" {...stroke} strokeWidth="2.4" />
    </>
  ),
  'damage-boost': (
    <>
      <path d="M12 20V6M6 12l6-6 6 6" {...stroke} strokeWidth="2.4" />
      <path d="M6 20h12" {...stroke} />
    </>
  ),
  switch: (
    <>
      <path d="M4 8h13l-3.5-3.5M20 16H7l3.5 3.5" {...stroke} strokeWidth="2.2" />
    </>
  ),
  'bonus-instinct': (
    <>
      <path d="M13 2 5 13h6l-1 9 8-11h-6l1-9Z" {...stroke} />
    </>
  ),
};

/** Inner layout of a trainer (item/support) card. */
export function TrainerCardView({ card }: { card: TrainerCard }) {
  const isItem = card.trainerKind === 'item';
  return (
    <div className="flex h-full flex-col bg-night-900 text-slate-100">
      <header className="flex items-center gap-[2cqw] px-[4cqw] pt-[3cqw]">
        <span
          className={`shrink-0 rounded-full px-[2.5cqw] py-[0.8cqw] text-[3.2cqw] font-black tracking-wider uppercase ${
            isItem ? 'bg-amphibian/20 text-amphibian' : 'bg-gold-400/20 text-gold-300'
          }`}
        >
          {isItem ? 'Item' : 'Support'}
        </span>
        <h3 className="min-w-0 flex-1 truncate font-display text-[6cqw] leading-tight font-bold">
          {card.name}
        </h3>
      </header>

      <div className="mx-[3cqw] mt-[3cqw] flex aspect-[4/3] items-center justify-center rounded-[3cqw] bg-gradient-to-br from-night-700 to-night-950">
        <span className={isItem ? 'text-amphibian' : 'text-gold-300'}>
          <svg viewBox="0 0 24 24" className="h-[26cqw] w-[26cqw]" aria-hidden="true">
            {EFFECT_GLYPHS[card.effect.type]}
          </svg>
        </span>
      </div>

      <p className="flex-1 px-[5cqw] pt-[3.5cqw] text-[4.4cqw] leading-snug text-slate-300">
        {card.text}
      </p>

      <footer className="flex items-center justify-between border-t border-white/10 px-[4cqw] py-[2cqw]">
        <span className="text-[3.4cqw] text-slate-500 uppercase">
          {isItem ? 'Play any number per turn' : 'One per turn'}
        </span>
        <RarityGems rarity={card.rarity} />
      </footer>
    </div>
  );
}
