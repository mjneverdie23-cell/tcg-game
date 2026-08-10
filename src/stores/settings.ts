import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { idbStateStorage } from '../utils/storage';

export interface SettingsValues {
  musicEnabled: boolean;
  sfxEnabled: boolean;
  /** Disables ambient/decorative animation for accessibility and battery. */
  reducedMotion: boolean;
}

interface SettingsState extends SettingsValues {
  setSetting: <K extends keyof SettingsValues>(key: K, value: SettingsValues[K]) => void;
}

const DEFAULTS: SettingsValues = {
  musicEnabled: true,
  sfxEnabled: true,
  reducedMotion: false,
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      setSetting: (key, value) => set({ [key]: value }),
    }),
    {
      name: 'settings',
      storage: createJSONStorage(() => idbStateStorage),
      partialize: ({ musicEnabled, sfxEnabled, reducedMotion }) => ({
        musicEnabled,
        sfxEnabled,
        reducedMotion,
      }),
    },
  ),
);
