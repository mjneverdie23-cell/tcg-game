import { Suspense } from "react";
import type { Metadata } from "next";
import { CountryBrowser } from "@/components/browse/country-browser";
import { getAllSummaries } from "@/lib/countries";
import { Skeleton } from "@/components/ui/skeleton";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Browse all countries",
  description: "Browse every sovereign country in the World Atlas. Filter by continent, sort by name, population or area, and jump alphabetically.",
};

export default async function BrowsePage() {
  const countries = await getAllSummaries();
  return (
    <div className="container py-8">
      <h1 className="text-3xl font-bold tracking-tight">All countries</h1>
      <p className="mt-1 text-muted-foreground">Every sovereign state in the atlas — filter, sort and jump by letter.</p>
      <div className="mt-6">
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <CountryBrowser countries={countries} />
        </Suspense>
      </div>
    </div>
  );
}
