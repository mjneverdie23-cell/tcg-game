/**
 * Ambient animated backdrop rendered behind every screen: a deep night
 * gradient with softly drifting color blobs. Pure CSS animation (transform
 * only) so it stays cheap; disabled by the reduced-motion CSS guards
 * (system preference or the in-game setting via data-reduced-motion).
 */
export function AnimatedBackground() {
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden bg-night-950">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--color-night-800),_var(--color-night-950)_70%)]" />
      <div className="bg-blob bg-blob-a absolute -top-1/4 -left-1/4 h-[70vmax] w-[70vmax] rounded-full bg-pterosaur/10 blur-3xl" />
      <div className="bg-blob bg-blob-b absolute -right-1/4 -bottom-1/4 h-[60vmax] w-[60vmax] rounded-full bg-amphibian/10 blur-3xl" />
    </div>
  );
}
