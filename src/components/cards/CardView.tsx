import type { Card } from '../../game/types';
import { DinoCardView } from './DinoCardView';
import { FieldCardView } from './FieldCardView';
import { InstinctCardView } from './InstinctCardView';
import { TrainerCardView } from './TrainerCardView';
import { RARITY_THEME } from './theme';

interface CardViewProps {
  card: Card;
  onClick?: (() => void) | undefined;
  /** Width is controlled by the parent (e.g. `w-40`); the card scales itself. */
  className?: string;
}

/**
 * The card rendering engine's entry point: rarity ring + glow around the
 * kind-specific layout. All inner sizing uses container-query units, so a
 * card looks identical at any width — grid thumbnail to full-screen viewer.
 */
export function CardView({ card, onClick, className = '' }: CardViewProps) {
  const rarity = RARITY_THEME[card.rarity];
  const frame = (
    <div
      style={{ containerType: 'inline-size' }}
      className={`relative aspect-[5/7] w-full overflow-hidden rounded-[4.5%] p-[1.6%] select-none ${rarity.ring} ${rarity.glow}`}
    >
      <div className="h-full w-full overflow-hidden rounded-[3.5%] bg-night-900">
        {card.kind === 'dino' && <DinoCardView card={card} />}
        {card.kind === 'trainer' && <TrainerCardView card={card} />}
        {card.kind === 'field' && <FieldCardView card={card} />}
        {card.kind === 'instinct' && <InstinctCardView card={card} />}
      </div>
    </div>
  );

  if (onClick === undefined) {
    return <div className={className}>{frame}</div>;
  }
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`View ${card.name}`}
      className={`block w-full cursor-pointer transition-transform duration-150 hover:scale-[1.03] active:scale-[0.98] ${className}`}
    >
      {frame}
    </button>
  );
}
