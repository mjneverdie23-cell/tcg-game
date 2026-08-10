import type { DinoClass } from '../../database/types';

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const;

/** Per-class glyphs, drawn to read clearly even at pip size. */
const ICON_PATHS: Record<DinoClass, React.ReactNode> = {
  // Fang / claw
  carnivore: (
    <path d="M6 4c1 5 2 9 6 16 4-7 5-11 6-16-2 2.5-4 3-6 3s-4-.5-6-3Z" {...stroke} />
  ),
  // Frond leaf
  herbivore: (
    <>
      <path d="M12 21C12 11 13 6 19 3c.5 6-1 12-7 18Z" {...stroke} />
      <path d="M12 21C12 13 10 8 5 5c-.5 5 1 10 7 16" {...stroke} />
    </>
  ),
  // Wing
  pterosaur: (
    <path d="M2 15c4-6 8-9 20-9-3 2-4 4-5 7-2-1-4-1-5 1-2-1-4 0-5 2-2-1-3-1-5-1Z" {...stroke} />
  ),
  // Wave
  amphibian: (
    <>
      <path d="M3 12c2-2 4-2 6 0s4 2 6 0 4-2 6 0" {...stroke} />
      <path d="M3 17c2-2 4-2 6 0s4 2 6 0 4-2 6 0" {...stroke} />
      <path d="M12 3c-2 2.5-3 4-3 5.5a3 3 0 0 0 6 0C15 7 14 5.5 12 3Z" {...stroke} />
    </>
  ),
};

interface ClassIconProps {
  dinoClass: DinoClass;
  className?: string;
}

export function ClassIcon({ dinoClass, className = 'h-5 w-5' }: ClassIconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} role="img" aria-label={dinoClass}>
      {ICON_PATHS[dinoClass]}
    </svg>
  );
}
