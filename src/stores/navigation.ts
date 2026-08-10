import { create } from 'zustand';

/** Every screen the game will have. Screens unlock as milestones land. */
export type ScreenId =
  | 'menu'
  | 'collection'
  | 'deckbuilder'
  | 'packs'
  | 'shop'
  | 'battle'
  | 'settings';

interface NavigationState {
  screen: ScreenId;
  /** Screens we came through, so `back()` retraces the user's path. */
  stack: readonly ScreenId[];
  navigate: (to: ScreenId) => void;
  back: () => void;
}

export const useNavigationStore = create<NavigationState>()((set) => ({
  screen: 'menu',
  stack: [],
  navigate: (to) =>
    set((state) =>
      to === state.screen ? state : { screen: to, stack: [...state.stack, state.screen] },
    ),
  back: () =>
    set((state) => {
      const previous = state.stack.at(-1);
      return previous === undefined
        ? { screen: 'menu', stack: [] }
        : { screen: previous, stack: state.stack.slice(0, -1) };
    }),
}));
