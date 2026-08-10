import { useState } from 'react';
import { useSettingsStore, type SettingsValues } from '../../stores/settings';
import { wipeAllData } from '../../utils/storage';
import { ScreenHeader } from '../ui/ScreenHeader';
import { ScreenShell } from '../ui/ScreenShell';
import { Toggle } from '../ui/Toggle';

interface SettingRow {
  key: keyof SettingsValues;
  label: string;
  description: string;
}

const SETTING_ROWS: readonly SettingRow[] = [
  { key: 'musicEnabled', label: 'Music', description: 'Background music during menus and battles' },
  { key: 'sfxEnabled', label: 'Sound effects', description: 'Card plays, attacks and pack opening' },
  {
    key: 'reducedMotion',
    label: 'Reduced motion',
    description: 'Minimize ambient and decorative animations',
  },
];

export function SettingsScreen() {
  const settings = useSettingsStore();
  const [confirmingReset, setConfirmingReset] = useState(false);

  const resetSave = async () => {
    if (!confirmingReset) {
      setConfirmingReset(true);
      return;
    }
    await wipeAllData();
    window.location.reload();
  };

  return (
    <ScreenShell>
      <ScreenHeader title="Settings" />
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <section className="glass rounded-3xl p-2">
          {SETTING_ROWS.map((row) => (
            <div key={row.key} className="flex items-center justify-between gap-4 p-4">
              <div>
                <p className="font-display font-semibold">{row.label}</p>
                <p className="text-sm text-slate-400">{row.description}</p>
              </div>
              <Toggle
                checked={settings[row.key]}
                onChange={(value) => settings.setSetting(row.key, value)}
                label={row.label}
              />
            </div>
          ))}
        </section>

        <section className="glass rounded-3xl p-4">
          <p className="font-display font-semibold">Reset save data</p>
          <p className="mb-3 text-sm text-slate-400">
            Permanently deletes your collection, decks, coins and settings on this device.
          </p>
          <button
            type="button"
            onClick={() => void resetSave()}
            className={`cursor-pointer rounded-2xl px-4 py-2.5 text-sm font-bold transition active:scale-95 ${
              confirmingReset
                ? 'bg-carnivore text-white'
                : 'bg-white/10 text-carnivore hover:bg-white/15'
            }`}
          >
            {confirmingReset ? 'Tap again to confirm' : 'Reset everything'}
          </button>
        </section>
      </div>
    </ScreenShell>
  );
}
