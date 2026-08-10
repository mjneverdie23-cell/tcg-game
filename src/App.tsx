import { AnimatePresence, MotionConfig } from 'framer-motion';
import { useEffect, type ComponentType } from 'react';
import { AnimatedBackground } from './components/game/AnimatedBackground';
import { MainMenu } from './components/game/MainMenu';
import { SettingsScreen } from './components/game/SettingsScreen';
import { PackOpeningScreen } from './components/packopening/PackOpeningScreen';
import { useNavigationStore, type ScreenId } from './stores/navigation';
import { useSettingsStore } from './stores/settings';

/**
 * Registry of implemented screens. As milestones land, new screens are added
 * here and the corresponding main-menu entry unlocks automatically.
 */
export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  menu: MainMenu,
  packs: PackOpeningScreen,
  settings: SettingsScreen,
};

export default function App() {
  const screen = useNavigationStore((state) => state.screen);
  const reducedMotion = useSettingsStore((state) => state.reducedMotion);
  const Screen = SCREENS[screen] ?? MainMenu;

  // Decorative CSS animations (bg blobs, holo cards) key off this attribute.
  useEffect(() => {
    document.documentElement.dataset.reducedMotion = String(reducedMotion);
  }, [reducedMotion]);

  return (
    <MotionConfig reducedMotion={reducedMotion ? 'always' : 'user'}>
      <div className="relative h-dvh w-full overflow-hidden">
        <AnimatedBackground />
        <AnimatePresence mode="wait">
          <Screen key={screen} />
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
