import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import type { PointerEvent } from 'react';
import type { Card } from '../../game/types';
import { CardView } from './CardView';
import { RARITY_THEME } from './theme';

interface CardViewerProps {
  /** Card to show; null hides the viewer. */
  card: Card | null;
  onClose: () => void;
}

/**
 * Full-screen card inspector: dimmed backdrop, large card that tilts toward
 * the pointer (Pocket-style), rarity label and flavor text underneath.
 */
export function CardViewer({ card, onClose }: CardViewerProps) {
  const pointerX = useMotionValue(0.5);
  const pointerY = useMotionValue(0.5);
  const rotateY = useSpring(useTransform(pointerX, [0, 1], [-10, 10]), {
    stiffness: 250,
    damping: 25,
  });
  const rotateX = useSpring(useTransform(pointerY, [0, 1], [8, -8]), {
    stiffness: 250,
    damping: 25,
  });

  const handlePointer = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    pointerX.set((event.clientX - rect.left) / rect.width);
    pointerY.set((event.clientY - rect.top) / rect.height);
  };

  const resetPointer = () => {
    pointerX.set(0.5);
    pointerY.set(0.5);
  };

  return (
    <AnimatePresence>
      {card !== null && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-night-950/80 p-6 backdrop-blur-md"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label={card.name}
        >
          <motion.div
            initial={{ scale: 0.7, y: 40 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.8, y: 40 }}
            transition={{ type: 'spring', stiffness: 260, damping: 24 }}
            style={{ rotateX, rotateY, transformPerspective: 900 }}
            className="w-full max-w-xs sm:max-w-sm"
            onClick={(event) => event.stopPropagation()}
            onPointerMove={handlePointer}
            onPointerLeave={resetPointer}
          >
            <CardView card={card} />
          </motion.div>

          <div className="mt-5 max-w-sm text-center" onClick={(event) => event.stopPropagation()}>
            <p className={`text-sm font-bold tracking-widest uppercase ${RARITY_THEME[card.rarity].gem}`}>
              {RARITY_THEME[card.rarity].label}
            </p>
            {card.kind === 'dino' && card.description !== '' && (
              <p className="mt-2 text-sm leading-relaxed text-slate-300">{card.description}</p>
            )}
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="glass absolute top-[max(1rem,env(safe-area-inset-top))] right-4 flex h-11 w-11 cursor-pointer items-center justify-center rounded-2xl text-slate-200 transition hover:bg-white/10 active:scale-95"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
              <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
            </svg>
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
