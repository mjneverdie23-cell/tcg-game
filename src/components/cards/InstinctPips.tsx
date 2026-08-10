import type { InstinctPip } from '../../game/types';
import { CLASS_THEME } from './theme';
import { ClassIcon } from './ClassIcon';

interface InstinctPipsProps {
  cost: readonly InstinctPip[];
  /** Pip diameter, sized in container-query units by the card layout. */
  pipClass?: string;
}

/** Row of energy pips: class-colored with the class glyph, gray for neutral. */
export function InstinctPips({ cost, pipClass = 'h-[7cqw] w-[7cqw]' }: InstinctPipsProps) {
  return (
    <span className="flex items-center gap-[1cqw]" aria-label={`cost: ${cost.join(', ')}`}>
      {cost.map((pip, index) => (
        <span
          key={index}
          className={`flex items-center justify-center rounded-full text-night-950 ${pipClass} ${
            pip === 'neutral' ? 'bg-slate-400' : CLASS_THEME[pip].bg
          }`}
        >
          {pip === 'neutral' ? (
            <span className="text-[4cqw] leading-none font-black">★</span>
          ) : (
            <ClassIcon dinoClass={pip} className="h-[70%] w-[70%]" />
          )}
        </span>
      ))}
    </span>
  );
}
