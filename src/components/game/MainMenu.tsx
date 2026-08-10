import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { SCREENS } from '../../App';
import { useNavigationStore, type ScreenId } from '../../stores/navigation';
import { ScreenShell } from '../ui/ScreenShell';

interface MenuEntry {
  screen: ScreenId;
  label: string;
  description: string;
  icon: ReactNode;
  /** Tailwind text color class for the icon accent. */
  accent: string;
}

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const;

const MENU_ENTRIES: readonly MenuEntry[] = [
  {
    screen: 'battle',
    label: 'Battle',
    description: 'Fight the AI',
    accent: 'text-carnivore',
    icon: (
      <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden="true">
        <path d="M4 20 18.5 5.5M4 20h4m-4 0v-4M20 4l-3 3M20 20 5.5 5.5M20 20h-4m4 0v-4M4 4l3 3" {...stroke} />
      </svg>
    ),
  },
  {
    screen: 'collection',
    label: 'Collection',
    description: 'Your dinosaurs',
    accent: 'text-herbivore',
    icon: (
      <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden="true">
        <rect x="7.5" y="4" width="12" height="16" rx="2" {...stroke} />
        <path d="M7.5 6.5 5.7 7a2 2 0 0 0-1.4 2.4L6.8 19" {...stroke} />
      </svg>
    ),
  },
  {
    screen: 'deckbuilder',
    label: 'Deck Builder',
    description: 'Craft your strategy',
    accent: 'text-amphibian',
    icon: (
      <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden="true">
        <path d="m12 3 9 5-9 5-9-5 9-5Z" {...stroke} />
        <path d="m3.5 12.5 8.5 4.7 8.5-4.7M3.5 16.5 12 21l8.5-4.5" {...stroke} />
      </svg>
    ),
  },
  {
    screen: 'packs',
    label: 'Open Packs',
    description: 'Daily free pack',
    accent: 'text-pterosaur',
    icon: (
      <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden="true">
        <path d="M4 8.5 12 4l8 4.5v7L12 20l-8-4.5v-7Z" {...stroke} />
        <path d="M4 8.5 12 13l8-4.5M12 13v7" {...stroke} />
      </svg>
    ),
  },
  {
    screen: 'shop',
    label: 'Shop',
    description: 'Spend your coins',
    accent: 'text-gold-400',
    icon: (
      <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden="true">
        <circle cx="12" cy="12" r="8.5" {...stroke} />
        <path d="M12 7.5v9M15 9.5c-.6-1.2-1.7-1.8-3-1.8-1.6 0-2.9.9-2.9 2.2 0 2.9 6 1.5 6 4.3 0 1.3-1.4 2.3-3.1 2.3-1.4 0-2.6-.7-3.2-1.9" {...stroke} />
      </svg>
    ),
  },
  {
    screen: 'settings',
    label: 'Settings',
    description: 'Audio & options',
    accent: 'text-slate-300',
    icon: (
      <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden="true">
        <circle cx="12" cy="12" r="3.2" {...stroke} />
        <path d="M12 3v2.5M12 18.5V21M21 12h-2.5M5.5 12H3m15.4-6.4-1.8 1.8M7.4 16.6l-1.8 1.8m12.8 0-1.8-1.8M7.4 7.4 5.6 5.6" {...stroke} />
      </svg>
    ),
  },
];

export function MainMenu() {
  const navigate = useNavigationStore((state) => state.navigate);

  return (
    <ScreenShell>
      <div className="mx-auto flex w-full max-w-3xl grow flex-col justify-center py-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="mb-10 text-center"
        >
          <h1 className="font-display bg-gradient-to-br from-gold-300 via-gold-400 to-carnivore bg-clip-text text-6xl font-extrabold tracking-tight text-transparent sm:text-7xl">
            PRIMORDIA
          </h1>
          <p className="mt-2 text-sm font-medium tracking-[0.3em] text-slate-400 uppercase">
            The Dinosaur Trading Card Game
          </p>
        </motion.div>

        <nav aria-label="Main menu" className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {MENU_ENTRIES.map((entry, index) => {
            const implemented = entry.screen in SCREENS;
            return (
              <motion.button
                key={entry.screen}
                type="button"
                disabled={!implemented}
                onClick={() => navigate(entry.screen)}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 * index, duration: 0.35, ease: 'easeOut' }}
                whileHover={implemented ? { scale: 1.03 } : undefined}
                whileTap={implemented ? { scale: 0.97 } : undefined}
                className={`glass relative flex flex-col items-start gap-2 rounded-3xl p-5 text-left ${
                  implemented ? 'cursor-pointer hover:bg-white/10' : 'opacity-50'
                }`}
              >
                <span className={entry.accent}>{entry.icon}</span>
                <span className="font-display text-lg font-bold">{entry.label}</span>
                <span className="text-xs text-slate-400">{entry.description}</span>
                {!implemented && (
                  <span className="absolute top-3 right-3 rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold tracking-wider text-slate-300 uppercase">
                    Soon
                  </span>
                )}
              </motion.button>
            );
          })}
        </nav>

        <p className="mt-10 text-center text-xs text-slate-500">
          v{__APP_VERSION__} · plays fully offline
        </p>
      </div>
    </ScreenShell>
  );
}
