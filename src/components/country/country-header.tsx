"use client";

import * as React from "react";
import Link from "next/link";
import { Heart } from "lucide-react";
import { useAtlasStore } from "@/lib/store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatArea, formatCompact } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CountryDetail } from "@/lib/types";

/** Sticky country header: flag, names, key facts, favorite toggle, learning progress. */
export function CountryHeader({ country, sectionCount }: { country: CountryDetail; sectionCount: number }) {
  const { slug, name, cca2 } = country;
  const isFavorite = useAtlasStore((s) => s.favorites.includes(slug));
  const toggleFavorite = useAtlasStore((s) => s.toggleFavorite);
  const addRecent = useAtlasStore((s) => s.addRecent);
  const progress = useAtlasStore((s) => s.progressFor(slug, sectionCount));

  React.useEffect(() => {
    addRecent({ slug, name, flagEmoji: country.flagEmoji });
  }, [slug, name, country.flagEmoji, addRecent]);

  return (
    <div className="border-b bg-card/60">
      <div className="flex items-center gap-4 px-4 py-3 sm:px-6">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`/flags/${cca2.toLowerCase()}.svg`} alt={`Flag of ${name}`} className="h-11 w-16 shrink-0 rounded border object-cover shadow-sm" width={64} height={44} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate text-2xl font-bold tracking-tight">{name}</h1>
            <Badge variant="secondary">{country.subregion ?? country.region}</Badge>
            {country.unMember && <Badge variant="outline">UN member</Badge>}
          </div>
          <p className="truncate text-sm text-muted-foreground">
            {country.officialName} · {country.capital[0] ?? "—"} · {formatCompact(country.population)} people · {formatArea(country.area)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex flex-col items-end">
            <span className="text-xs text-muted-foreground">Learning progress</span>
            <div className="mt-1 h-1.5 w-28 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>
          <Button variant={isFavorite ? "default" : "outline"} size="sm" onClick={() => toggleFavorite(slug)} aria-pressed={isFavorite}>
            <Heart className={cn("h-4 w-4", isFavorite && "fill-current")} />
            <span className="hidden sm:inline">{isFavorite ? "Favorited" : "Favorite"}</span>
          </Button>
        </div>
      </div>
      {country.neighbors.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto scrollbar-thin px-4 pb-2 sm:px-6">
          <span className="shrink-0 text-xs text-muted-foreground">Borders:</span>
          {country.neighbors.map((n) => (
            <Link key={n.slug} href={`/country/${n.slug}`} className="shrink-0 rounded-full border bg-background px-2.5 py-1 text-xs transition-colors hover:bg-accent">
              {n.flagEmoji} {n.name}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
