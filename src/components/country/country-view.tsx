"use client";

/** Two-pane country view: detailed map (left) + tabbed encyclopedia (right). */

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";
import { CountryHeader } from "./country-header";
import { CountryTabs } from "./country-tabs";
import type { CountryDetail } from "@/lib/types";

const CountryMap = dynamic(() => import("@/components/map/country-map").then((m) => m.CountryMap), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full rounded-none" />,
});

export function CountryView({ country }: { country: CountryDetail }) {
  return (
    <div className="flex flex-col">
      <CountryHeader country={country} sectionCount={country.sections.length} />
      <div className="grid flex-1 lg:grid-cols-2">
        {/* Left: interactive detailed map */}
        <div className="relative h-[45vh] border-b lg:h-[calc(100dvh-3.5rem-5.5rem)] lg:border-b-0 lg:border-r lg:sticky lg:top-[3.5rem]">
          <CountryMap
            slug={country.slug}
            name={country.name}
            bbox={country.bbox}
            latitude={country.latitude}
            longitude={country.longitude}
            cities={country.cities}
            neighbors={country.neighbors}
            className="absolute inset-0"
          />
        </div>
        {/* Right: tabbed encyclopedia */}
        <div className="min-h-[60vh] lg:h-[calc(100dvh-3.5rem-5.5rem)]">
          <CountryTabs slug={country.slug} countryName={country.name} sections={country.sections} />
        </div>
      </div>
    </div>
  );
}
