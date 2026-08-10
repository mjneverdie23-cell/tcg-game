import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

/**
 * Wrapper every screen renders inside. Provides the shared enter/exit
 * transition (driven by AnimatePresence in App) and mobile safe-area padding.
 */
export function ScreenShell({ children }: { children: ReactNode }) {
  return (
    <motion.main
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -24 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="absolute inset-0 flex flex-col overflow-y-auto px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))]"
    >
      {children}
    </motion.main>
  );
}
