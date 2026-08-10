import { motion } from 'framer-motion';

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}

/** Accessible switch styled for the dark glass UI. */
export function Toggle({ checked, onChange, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-8 w-14 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ${
        checked ? 'bg-gold-400' : 'bg-white/15'
      }`}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 500, damping: 32 }}
        className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow-md ${
          checked ? 'left-7' : 'left-1'
        }`}
      />
    </button>
  );
}
