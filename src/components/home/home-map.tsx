"use client";

/** Client island for the homepage: the world map (lazy, no SSR) + continent filters. */

import * as React from "react";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { WorldMapHandle } from "@/components/map/world-map";

const WorldMap = dynamic(() => import("@/components/map/world-map").then((m) => m.WorldMap), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full rounded-none" />,
});

const REGION_BOUNDS: Record<string, [[number, number], [number, number]]> = {
  Africa: [[-35, -20], [38, 52]],
  Americas: [[-56, -125], [62, -30]],
  Asia: [[-10, 25], [55, 145]],
  Europe: [[35, -12], [70, 45]],
  Oceania: [[-48, 110], [3, 180]],
};

const REGION_LABELS = ["Africa", "Americas", "Asia", "Europe", "Oceania"] as const;

export function HomeMap() {
  const mapRef = React.useRef<WorldMapHandle>(null);
  const [region, setRegion] = React.useState<string | null>(null);

  const pick = (r: string) => {
    const next = region === r ? null : r;
    setRegion(next);
    if (next) mapRef.current?.flyToRegion(REGION_BOUNDS[next]);
  };

  return (
    <div className="relative h-[calc(100dvh-3.5rem)] min-h-[420px] w-full overflow-hidden">
      <WorldMap ref={mapRef} highlightRegion={region} className="absolute inset-0" />

      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="pointer-events-none absolute left-4 top-4 z-[1000] max-w-sm">
        <div className="pointer-events-auto rounded-xl border bg-card/90 p-4 shadow-lg backdrop-blur">
          <h1 className="text-xl font-bold tracking-tight">Explore the World</h1>
          <p className="mt-1 text-sm text-muted-foreground">197 countries, every continent and ocean. Hover to preview, click any country to open its encyclopedia page.</p>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }} className="absolute bottom-6 left-1/2 z-[1000] -translate-x-1/2">
        <div className="flex flex-wrap justify-center gap-1.5 rounded-full border bg-card/90 p-1.5 shadow-lg backdrop-blur" role="group" aria-label="Filter map by continent">
          {REGION_LABELS.map((r) => (
            <button
              key={r}
              onClick={() => pick(r)}
              aria-pressed={region === r}
              className={cn("rounded-full px-3 py-1.5 text-xs font-medium transition-colors sm:px-4 sm:text-sm", region === r ? "bg-primary text-primary-foreground shadow" : "hover:bg-accent hover:text-accent-foreground")}
            >
              {r}
            </button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
