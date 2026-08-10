import type { FieldCard } from '../../game/types';
import { RarityGems } from './RarityGems';

/**
 * Painted-gradient scene per field. Keyed by card id so new fields fail
 * loudly in tests rather than silently rendering an empty scene.
 */
const FIELD_SCENES: Record<string, string> = {
  'field:dense-jungle':
    'bg-[radial-gradient(circle_at_20%_20%,#2f6b2f_0%,transparent_55%),radial-gradient(circle_at_80%_60%,#123c1e_0%,transparent_60%)] bg-[#0a2411]',
  'field:volcanic-plains':
    'bg-[radial-gradient(circle_at_75%_25%,#ff8a3d_0%,transparent_45%),radial-gradient(circle_at_30%_75%,#7a1d12_0%,transparent_60%)] bg-[#230a08]',
  'field:river-delta':
    'bg-[radial-gradient(circle_at_30%_30%,#38a8ff_0%,transparent_50%),radial-gradient(circle_at_75%_70%,#0c4a6e_0%,transparent_60%)] bg-[#06202f]',
  'field:mountain-cliffs':
    'bg-[radial-gradient(circle_at_50%_15%,#94a3b8_0%,transparent_40%),radial-gradient(circle_at_25%_75%,#334155_0%,transparent_60%)] bg-[#111a2b]',
  'field:ancient-swamp':
    'bg-[radial-gradient(circle_at_70%_30%,#4d7c0f_0%,transparent_50%),radial-gradient(circle_at_25%_70%,#3b0764_0%,transparent_65%)] bg-[#141607]',
  'field:ice-valley':
    'bg-[radial-gradient(circle_at_35%_25%,#a5f3fc_0%,transparent_40%),radial-gradient(circle_at_70%_70%,#155e75_0%,transparent_60%)] bg-[#082030]',
};

export function fieldSceneClass(cardId: string): string {
  return FIELD_SCENES[cardId] ?? 'bg-night-800';
}

/** Inner layout of a field card: full-bleed scene with a caption plate. */
export function FieldCardView({ card }: { card: FieldCard }) {
  return (
    <div className={`relative flex h-full flex-col justify-end ${fieldSceneClass(card.id)}`}>
      <span className="absolute top-[3cqw] left-[3cqw] rounded-full bg-night-950/60 px-[2.5cqw] py-[0.8cqw] text-[3.2cqw] font-black tracking-wider text-herbivore uppercase backdrop-blur-sm">
        Field
      </span>
      <div className="space-y-[1.5cqw] bg-gradient-to-t from-night-950/95 via-night-950/70 to-transparent p-[4cqw] pt-[10cqw]">
        <h3 className="font-display text-[7cqw] leading-tight font-bold text-white">{card.name}</h3>
        <p className="text-[4.2cqw] leading-snug text-slate-300">{card.text}</p>
        <div className="flex justify-end">
          <RarityGems rarity={card.rarity} />
        </div>
      </div>
    </div>
  );
}
