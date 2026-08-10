import type { Rarity } from '../../database/types';
import { RARITY_THEME } from './theme';

/**
 * Rarity indicator in the card footer: 1–3 diamonds for common/rare/epic,
 * a star for legendary, a burst for mythic (TCG-Pocket style).
 */
export function RarityGems({ rarity }: { rarity: Rarity }) {
  const theme = RARITY_THEME[rarity];
  if (rarity === 'legendary') {
    return (
      <svg viewBox="0 0 24 24" className={`h-[4.5cqw] w-[4.5cqw] ${theme.gem}`} role="img" aria-label="legendary">
        <path
          d="m12 2 2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2l-6.1 3.4 1.4-6.8L2.2 9.1l6.9-.8L12 2Z"
          fill="currentColor"
        />
      </svg>
    );
  }
  if (rarity === 'mythic') {
    return (
      <svg viewBox="0 0 24 24" className={`h-[4.5cqw] w-[4.5cqw] ${theme.gem}`} role="img" aria-label="mythic">
        <path
          d="M12 1l2.2 6.2L20 5l-3.2 5.4L23 12l-6.2 1.6L20 19l-5.8-2.2L12 23l-2.2-6.2L4 19l3.2-5.4L1 12l6.2-1.6L4 5l5.8 2.2L12 1Z"
          fill="currentColor"
        />
      </svg>
    );
  }
  return (
    <span className={`flex gap-[1cqw] ${theme.gem}`} role="img" aria-label={rarity}>
      {Array.from({ length: theme.gems }, (_, i) => (
        <span key={i} className="h-[3cqw] w-[3cqw] rotate-45 bg-current" />
      ))}
    </span>
  );
}
