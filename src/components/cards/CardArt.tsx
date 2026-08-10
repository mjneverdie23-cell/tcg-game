import type { DinoClass } from '../../database/types';
import { CLASS_THEME } from './theme';
import { ClassIcon } from './ClassIcon';

/**
 * Creature art, bundled at build time. The scraper drops WebP files into
 * src/assets/creatures/; this glob resolves them to hashed URLs so the PWA
 * precaches everything and nothing is ever hotlinked.
 */
const ART_URLS = import.meta.glob('../../assets/creatures/*.webp', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>;

export function creatureArtUrl(image: string): string | undefined {
  return ART_URLS[`../../assets/creatures/${image}`];
}

interface CardArtProps {
  image: string;
  name: string;
  dinoClass: DinoClass;
}

/**
 * Art area of a dino card. Falls back to a large class emblem on the class
 * gradient when art is missing (database not scraped yet, or a bad file).
 */
export function CardArt({ image, name, dinoClass }: CardArtProps) {
  const url = image === '' ? undefined : creatureArtUrl(image);
  const theme = CLASS_THEME[dinoClass];
  return (
    <div className={`relative h-full w-full overflow-hidden ${theme.artGradient}`}>
      {url !== undefined ? (
        <img
          src={url}
          alt={name}
          loading="lazy"
          draggable={false}
          className="h-full w-full object-cover object-center"
        />
      ) : (
        <div className={`flex h-full w-full items-center justify-center ${theme.text} opacity-40`}>
          <ClassIcon dinoClass={dinoClass} className="h-[55%] w-[55%]" />
        </div>
      )}
    </div>
  );
}
