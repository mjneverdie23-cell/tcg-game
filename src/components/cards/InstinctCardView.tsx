import type { InstinctCard } from '../../game/types';
import { ClassIcon } from './ClassIcon';
import { CLASS_THEME } from './theme';

/** Inner layout of an Instinct (energy) card: a big class emblem burst. */
export function InstinctCardView({ card }: { card: InstinctCard }) {
  const theme = CLASS_THEME[card.class];
  return (
    <div className={`relative flex h-full flex-col ${theme.artGradient}`}>
      <div className="flex flex-1 items-center justify-center">
        <span
          className={`flex h-[42cqw] w-[42cqw] items-center justify-center rounded-full text-night-950 shadow-[0_0_35cqw_8cqw_rgba(255,255,255,0.12)] ${theme.bg}`}
        >
          <ClassIcon dinoClass={card.class} className="h-[60%] w-[60%]" />
        </span>
      </div>
      <div className="p-[4cqw] text-center">
        <h3 className={`font-display text-[6.5cqw] font-bold ${theme.text}`}>{card.name}</h3>
        <p className="mt-[1cqw] text-[3.8cqw] text-slate-400">{card.text}</p>
      </div>
    </div>
  );
}
