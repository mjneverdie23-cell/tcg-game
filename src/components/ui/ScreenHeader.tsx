import { useNavigationStore } from '../../stores/navigation';

/** Title bar with a back button, used by every screen except the main menu. */
export function ScreenHeader({ title }: { title: string }) {
  const back = useNavigationStore((state) => state.back);
  return (
    <header className="mx-auto mb-6 flex w-full max-w-3xl items-center gap-3">
      <button
        type="button"
        onClick={back}
        aria-label="Back"
        className="glass flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-2xl text-slate-200 transition hover:bg-white/10 active:scale-95"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
          <path
            d="M14.5 5.5 8 12l6.5 6.5"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <h1 className="font-display text-2xl font-bold tracking-wide">{title}</h1>
    </header>
  );
}
