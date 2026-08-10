import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useMemo, useState } from 'react';
import { getCardSet } from '../../database';
import type { Rarity } from '../../database/types';
import { dailyPackReadyAt, getPack, openPack, PACKS, type PackDefinition } from '../../game/packs';
import type { Card } from '../../game/types';
import { ownedIdSet, useCollectionStore } from '../../stores/collection';
import { CardView } from '../cards/CardView';
import { CardViewer } from '../cards/CardViewer';
import { ScreenHeader } from '../ui/ScreenHeader';
import { ScreenShell } from '../ui/ScreenShell';

/** Rarities that get a glow burst when revealed. */
const GLOW_COLOR: Partial<Record<Rarity, string>> = {
  epic: 'var(--color-rarity-epic)',
  legendary: 'var(--color-rarity-legendary)',
  mythic: 'var(--color-rarity-mythic)',
};

interface Opening {
  pack: PackDefinition;
  cards: Card[];
  /** Ids that were NOT owned before this pack (drive the NEW badge). */
  newIds: ReadonlySet<string>;
}

type Phase =
  | { name: 'select' }
  | { name: 'reveal'; opening: Opening; index: number; flipped: boolean }
  | { name: 'summary'; opening: Opening };

/**
 * Claim/pay for and open a pack, updating the collection. Returns null when
 * the pack isn't available (on cooldown, or not enough coins).
 */
function performOpening(
  packId: string,
  dailyReady: boolean,
  collection: ReturnType<typeof useCollectionStore.getState>,
  cardSet: ReturnType<typeof getCardSet>,
): Opening | null {
  const pack = getPack(packId);
  if (pack.price === 0) {
    if (!dailyReady) return null;
    collection.markDailyClaimed(Date.now());
  } else if (!collection.spendCoins(pack.price)) {
    return null;
  }
  const owned = ownedIdSet(collection.ownedCounts);
  const cards = openPack(pack, cardSet, owned, `${pack.id}:${Date.now()}`);
  collection.addCards(cards);
  const newIds = new Set(cards.map((card) => card.id).filter((id) => !owned.has(id)));
  return { pack, cards, newIds };
}

function formatCountdown(ms: number): string {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
}

/** Ticks once per second while mounted; drives the daily-pack countdown. */
function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

export function PackOpeningScreen() {
  const [phase, setPhase] = useState<Phase>({ name: 'select' });
  const [inspecting, setInspecting] = useState<Card | null>(null);
  const collection = useCollectionStore();
  const now = useNow();
  const cardSet = useMemo(() => getCardSet(), []);

  const dailyReadyAt = dailyPackReadyAt(collection.lastDailyClaimAt);
  const dailyReady = now >= dailyReadyAt;

  const handleOpenPack = (packId: string) => {
    const opening = performOpening(packId, dailyReady, useCollectionStore.getState(), cardSet);
    if (opening !== null) {
      setPhase({ name: 'reveal', opening, index: 0, flipped: false });
    }
  };

  const advance = () => {
    if (phase.name !== 'reveal') return;
    if (!phase.flipped) {
      setPhase({ ...phase, flipped: true });
    } else if (phase.index + 1 < phase.opening.cards.length) {
      setPhase({ ...phase, index: phase.index + 1, flipped: false });
    } else {
      setPhase({ name: 'summary', opening: phase.opening });
    }
  };

  return (
    <ScreenShell>
      <ScreenHeader title="Open Packs" />
      <div className="mx-auto flex w-full max-w-3xl grow flex-col">
        <AnimatePresence mode="wait">
          {phase.name === 'select' && (
            <motion.div
              key="select"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              className="flex grow flex-col gap-6"
            >
              <div className="glass flex items-center justify-between rounded-2xl px-4 py-3">
                <span className="text-sm text-slate-400">Your coins</span>
                <span className="font-display text-lg font-bold text-gold-300">
                  {collection.coins.toLocaleString()} 🪙
                </span>
              </div>

              <div className="grid grow content-center gap-5 sm:grid-cols-2">
                {PACKS.map((pack) => {
                  const isDaily = pack.price === 0;
                  const locked = isDaily ? !dailyReady : collection.coins < pack.price;
                  return (
                    <motion.button
                      key={pack.id}
                      type="button"
                      disabled={locked}
                      onClick={() => handleOpenPack(pack.id)}
                      whileHover={locked ? undefined : { scale: 1.02 }}
                      whileTap={locked ? undefined : { scale: 0.97 }}
                      className={`glass flex flex-col items-center gap-4 rounded-3xl p-6 text-center ${
                        locked ? 'opacity-60' : 'cursor-pointer hover:bg-white/10'
                      }`}
                    >
                      <PackArt packId={pack.id} dimmed={locked} />
                      <div>
                        <h2 className="font-display text-xl font-bold">{pack.name}</h2>
                        <p className="mt-1 text-xs text-slate-400">{pack.description}</p>
                      </div>
                      <span className="rounded-full bg-white/10 px-4 py-1.5 text-sm font-bold">
                        {isDaily
                          ? dailyReady
                            ? 'Open free pack'
                            : `Next in ${formatCountdown(dailyReadyAt - now)}`
                          : `${pack.price} 🪙`}
                      </span>
                    </motion.button>
                  );
                })}
              </div>
            </motion.div>
          )}

          {phase.name === 'reveal' && (
            <motion.div
              key={`reveal-${phase.index}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex grow flex-col items-center justify-center gap-6"
              onClick={advance}
            >
              <RevealCard
                card={phase.opening.cards[phase.index] as Card}
                flipped={phase.flipped}
                isNew={phase.flipped && phase.opening.newIds.has((phase.opening.cards[phase.index] as Card).id)}
              />
              <div className="flex gap-2" aria-label={`Card ${phase.index + 1} of ${phase.opening.cards.length}`}>
                {phase.opening.cards.map((_, i) => (
                  <span
                    key={i}
                    className={`h-2 w-2 rounded-full ${i <= phase.index ? 'bg-gold-400' : 'bg-white/20'}`}
                  />
                ))}
              </div>
              <p className="text-sm text-slate-400">
                {phase.flipped ? 'Tap to continue' : 'Tap to reveal'}
              </p>
            </motion.div>
          )}

          {phase.name === 'summary' && (
            <motion.div
              key="summary"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex grow flex-col items-center justify-center gap-6"
            >
              <h2 className="font-display text-2xl font-bold">
                {phase.opening.pack.name} opened!
              </h2>
              <div className="grid w-full grid-cols-3 gap-3 sm:grid-cols-5">
                {phase.opening.cards.map((card, index) => (
                  <motion.div
                    key={`${card.id}-${index}`}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.08 }}
                    className="relative"
                  >
                    <CardView card={card} onClick={() => setInspecting(card)} />
                    {phase.opening.newIds.has(card.id) && <NewBadge />}
                  </motion.div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setPhase({ name: 'select' })}
                className="cursor-pointer rounded-2xl bg-gold-400 px-6 py-3 font-display font-bold text-night-950 transition hover:bg-gold-300 active:scale-95"
              >
                Done
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <CardViewer card={inspecting} onClose={() => setInspecting(null)} />
    </ScreenShell>
  );
}

/** Stylized pack visual — pure CSS, no image assets. */
function PackArt({ packId, dimmed }: { packId: string; dimmed: boolean }) {
  const premium = packId === 'primal';
  return (
    <div
      className={`relative flex h-44 w-32 items-center justify-center overflow-hidden rounded-2xl border shadow-xl ${
        premium
          ? 'border-gold-400/40 bg-gradient-to-b from-[#3a2404] via-night-800 to-night-950'
          : 'border-white/15 bg-gradient-to-b from-night-700 via-night-800 to-night-950'
      } ${dimmed ? 'saturate-50' : ''}`}
    >
      <div className="absolute inset-x-0 top-0 h-10 bg-gradient-to-b from-white/10 to-transparent" />
      <svg viewBox="0 0 512 512" className={`h-16 w-16 ${premium ? 'text-gold-400' : 'text-slate-300'}`} aria-hidden="true">
        <g fill="currentColor">
          <path d="M118 122 C 176 208, 208 310, 214 418 C 152 328, 108 216, 94 140 Q 104 124 118 122 Z" />
          <path d="M236 88 C 292 190, 320 306, 324 428 C 264 330, 226 200, 210 108 Q 222 88 236 88 Z" />
          <path d="M356 122 C 402 210, 422 308, 420 406 C 368 322, 336 220, 330 142 Q 342 124 356 122 Z" />
        </g>
      </svg>
      <span className="absolute bottom-2 font-display text-[10px] font-bold tracking-[0.25em] text-slate-400 uppercase">
        Primordia
      </span>
    </div>
  );
}

/** Face-down card that flips over on tap, with a rarity glow burst. */
function RevealCard({ card, flipped, isNew }: { card: Card; flipped: boolean; isNew: boolean }) {
  const glow = GLOW_COLOR[card.rarity];
  return (
    <div className="relative w-56 sm:w-64" style={{ perspective: 1000 }}>
      {glow !== undefined && (
        <motion.div
          aria-hidden="true"
          initial={false}
          animate={flipped ? { opacity: 0.55, scale: 1.5 } : { opacity: 0, scale: 0.8 }}
          transition={{ duration: 0.6 }}
          className="absolute inset-0 rounded-full blur-3xl"
          style={{ backgroundColor: glow }}
        />
      )}
      <motion.div
        initial={false}
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={{ type: 'spring', stiffness: 200, damping: 22 }}
        className="relative aspect-[5/7] w-full [transform-style:preserve-3d]"
      >
        <div className="absolute inset-0 [backface-visibility:hidden]">
          <CardBack />
        </div>
        <div className="absolute inset-0 [backface-visibility:hidden]" style={{ transform: 'rotateY(180deg)' }}>
          <CardView card={card} />
          {isNew && <NewBadge />}
        </div>
      </motion.div>
    </div>
  );
}

/** Shared card-back design (also used face-down in battles later). */
export function CardBack() {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-3 rounded-[4.5%] border border-white/10 bg-gradient-to-br from-night-700 via-night-900 to-night-950 shadow-xl">
      <svg viewBox="0 0 512 512" className="h-1/3 w-1/3 text-gold-400/80" aria-hidden="true">
        <g fill="currentColor">
          <path d="M118 122 C 176 208, 208 310, 214 418 C 152 328, 108 216, 94 140 Q 104 124 118 122 Z" />
          <path d="M236 88 C 292 190, 320 306, 324 428 C 264 330, 226 200, 210 108 Q 222 88 236 88 Z" />
          <path d="M356 122 C 402 210, 422 308, 420 406 C 368 322, 336 220, 330 142 Q 342 124 356 122 Z" />
        </g>
      </svg>
      <span className="font-display text-xs font-bold tracking-[0.3em] text-slate-500 uppercase">
        Primordia
      </span>
    </div>
  );
}

function NewBadge() {
  return (
    <span className="absolute -top-2 -right-2 z-10 rounded-full bg-gold-400 px-2 py-0.5 text-[10px] font-black tracking-wider text-night-950 uppercase shadow-lg">
      New
    </span>
  );
}
