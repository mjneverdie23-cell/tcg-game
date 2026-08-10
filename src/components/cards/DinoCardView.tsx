import type { DinoCard } from '../../game/types';
import { CardArt } from './CardArt';
import { ClassIcon } from './ClassIcon';
import { InstinctPips } from './InstinctPips';
import { RarityGems } from './RarityGems';
import { CLASS_THEME } from './theme';

/** Inner layout of a dinosaur card (frame/ring supplied by CardView). */
export function DinoCardView({ card }: { card: DinoCard }) {
  const theme = CLASS_THEME[card.class];
  return (
    <div className="flex h-full flex-col bg-night-900 text-slate-100">
      <header className="flex items-baseline gap-[2cqw] px-[4cqw] pt-[2.5cqw]">
        {card.stage > 1 && (
          <span className="shrink-0 rounded-full bg-white/10 px-[2cqw] py-[0.5cqw] text-[3cqw] font-bold tracking-wider text-slate-300 uppercase">
            Stage {card.stage}
          </span>
        )}
        <h3 className="min-w-0 flex-1 truncate font-display text-[6.5cqw] leading-tight font-bold">
          {card.name}
        </h3>
        <span className="shrink-0 font-display text-[8.5cqw] leading-none font-extrabold">
          {card.hp}
          <span className="ml-[0.5cqw] text-[3.5cqw] font-bold text-slate-400">HP</span>
        </span>
      </header>

      <div className="relative mx-[3cqw] mt-[2cqw] aspect-[4/3] overflow-hidden rounded-[3cqw]">
        <CardArt image={card.image} name={card.name} dinoClass={card.class} />
        {card.rarity === 'mythic' && (
          <div
            aria-hidden="true"
            className="animate-holo pointer-events-none absolute inset-0 bg-[linear-gradient(105deg,transparent_40%,rgba(255,255,255,0.22)_50%,transparent_60%)] bg-[length:250%_100%] mix-blend-screen"
          />
        )}
        <span
          className={`absolute top-[2cqw] left-[2cqw] flex items-center gap-[1.5cqw] rounded-full bg-night-950/70 py-[1cqw] pr-[2.5cqw] pl-[1.5cqw] backdrop-blur-sm ${theme.text}`}
        >
          <ClassIcon dinoClass={card.class} className="h-[4.5cqw] w-[4.5cqw]" />
          <span className="text-[3.2cqw] font-bold tracking-wider uppercase">{theme.label}</span>
        </span>
      </div>

      <ul className="flex flex-1 flex-col justify-center gap-[1.5cqw] px-[4cqw]">
        {card.attacks.map((attack) => (
          <li key={attack.name} className="flex items-center gap-[2.5cqw]">
            <InstinctPips cost={attack.cost} />
            <span className="min-w-0 flex-1 truncate text-[5cqw] font-semibold">{attack.name}</span>
            <span className="font-display text-[6.5cqw] font-bold">{attack.damage}</span>
          </li>
        ))}
      </ul>

      <footer className="flex items-center justify-between border-t border-white/10 px-[4cqw] py-[2cqw] text-[3.4cqw] text-slate-400">
        <span className="flex items-center gap-[1cqw]" title={`Weak to ${card.weakness}`}>
          <span className="uppercase">Weak</span>
          <span className={CLASS_THEME[card.weakness].text}>
            <ClassIcon dinoClass={card.weakness} className="h-[4cqw] w-[4cqw]" />
          </span>
        </span>
        <span className="flex items-center gap-[1cqw]" title={`Resists ${card.resistance}`}>
          <span className="uppercase">Res</span>
          <span className={CLASS_THEME[card.resistance].text}>
            <ClassIcon dinoClass={card.resistance} className="h-[4cqw] w-[4cqw]" />
          </span>
        </span>
        <span className="flex items-center gap-[1cqw]" title={`Retreat cost ${card.retreatCost}`}>
          <span className="uppercase">Retreat</span>
          <span className="flex gap-[0.8cqw]">
            {Array.from({ length: card.retreatCost }, (_, i) => (
              <span key={i} className="h-[2.8cqw] w-[2.8cqw] rounded-full bg-slate-500" />
            ))}
          </span>
        </span>
        <RarityGems rarity={card.rarity} />
      </footer>
    </div>
  );
}
