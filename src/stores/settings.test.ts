import { describe, expect, it, vi } from 'vitest';
import { getValue } from '../utils/storage';
import { useSettingsStore } from './settings';

describe('settings store', () => {
  it('has sensible defaults', () => {
    const state = useSettingsStore.getState();
    expect(state.musicEnabled).toBe(true);
    expect(state.sfxEnabled).toBe(true);
    expect(state.reducedMotion).toBe(false);
  });

  it('updates a single setting', () => {
    useSettingsStore.getState().setSetting('musicEnabled', false);
    expect(useSettingsStore.getState().musicEnabled).toBe(false);
    expect(useSettingsStore.getState().sfxEnabled).toBe(true);
  });

  it('persists changes to IndexedDB', async () => {
    useSettingsStore.getState().setSetting('reducedMotion', true);
    await vi.waitFor(async () => {
      const raw = await getValue<string>('settings');
      expect(raw).toBeDefined();
      const parsed = JSON.parse(raw as string) as { state: { reducedMotion: boolean } };
      expect(parsed.state.reducedMotion).toBe(true);
    });
  });
});
