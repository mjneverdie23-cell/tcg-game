import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import type { Card } from '../game/types';
import { idbStateStorage } from '../utils/storage';

/**
 * The player's profile: owned cards, coins and the daily-pack timer.
 * Persisted to IndexedDB. Cards are stored as id → copies owned.
 */
interface CollectionState {
  ownedCounts: Record<string, number>;
  coins: number;
  /** Epoch ms of the last daily-pack claim; null = never claimed. */
  lastDailyClaimAt: number | null;
  addCards: (cards: readonly Card[]) => void;
  /** Returns false (and changes nothing) if the player can't afford it. */
  spendCoins: (amount: number) => boolean;
  earnCoins: (amount: number) => void;
  markDailyClaimed: (at: number) => void;
}

/** Coins a brand-new player starts with (enough for one premium pack). */
const STARTING_COINS = 150;

export const useCollectionStore = create<CollectionState>()(
  persist(
    (set, get) => ({
      ownedCounts: {},
      coins: STARTING_COINS,
      lastDailyClaimAt: null,
      addCards: (cards) =>
        set((state) => {
          const ownedCounts = { ...state.ownedCounts };
          for (const card of cards) {
            ownedCounts[card.id] = (ownedCounts[card.id] ?? 0) + 1;
          }
          return { ownedCounts };
        }),
      spendCoins: (amount) => {
        if (get().coins < amount) return false;
        set((state) => ({ coins: state.coins - amount }));
        return true;
      },
      earnCoins: (amount) => set((state) => ({ coins: state.coins + amount })),
      markDailyClaimed: (at) => set({ lastDailyClaimAt: at }),
    }),
    {
      name: 'collection',
      storage: createJSONStorage(() => idbStateStorage),
      partialize: ({ ownedCounts, coins, lastDailyClaimAt }) => ({
        ownedCounts,
        coins,
        lastDailyClaimAt,
      }),
    },
  ),
);

/** Set of owned card ids — the shape pack duplicate-protection consumes. */
export function ownedIdSet(ownedCounts: Record<string, number>): ReadonlySet<string> {
  return new Set(Object.keys(ownedCounts));
}
