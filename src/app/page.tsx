import Link from "next/link";
import { Compass, Globe2, Landmark, UtensilsCrossed } from "lucide-react";
import { HomeMap } from "@/components/home/home-map";
import { RecentlyViewed } from "@/components/home/recently-viewed";
import { getAllSummaries } from "@/lib/countries";
import { formatCompact } from "@/lib/format";
import { REGION_EMOJI } from "@/lib/continents";
import { Card, CardContent } from "@/components/ui/card";

export const revalidate = 3600;

export default async function HomePage() {
  const countries = await getAllSummaries();
  const totalPop = countries.reduce((sum, c) => sum + c.population, 0);
  const byRegion = new Map<string, number>();
  for (const c of countries) byRegion.set(c.region, (byRegion.get(c.region) ?? 0) + 1);

  return (
    <div className="flex flex-col">
      <HomeMap />

      {/* Stats band */}
      <section className="border-b bg-card/40">
        <div className="container grid grid-cols-2 gap-4 py-8 sm:grid-cols-4">
          {[
            { icon: Globe2, label: "Countries", value: String(countries.length) },
            { icon: Compass, label: "Continents", value: "6" },
            { icon: Landmark, label: "People", value: formatCompact(totalPop) },
            { icon: UtensilsCrossed, label: "Encyclopedia sections", value: "29 each" },
          ].map((s) => (
            <div key={s.label} className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-lg bg-primary/10 text-primary">
                <s.icon className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xl font-bold leading-none">{s.value}</div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <RecentlyViewed />

      {/* Browse by continent */}
      <section className="container py-8">
        <h2 className="mb-4 text-lg font-semibold">Browse by continent</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {[...byRegion.entries()].sort((a, b) => b[1] - a[1]).map(([region, count]) => (
            <Link key={region} href={`/browse?region=${encodeURIComponent(region)}`}>
              <Card className="transition-all hover:shadow-md hover:-translate-y-0.5">
                <CardContent className="flex flex-col items-center gap-1 p-4 text-center">
                  <span className="text-3xl">{REGION_EMOJI[region] ?? "🌍"}</span>
                  <span className="font-medium">{region}</span>
                  <span className="text-xs text-muted-foreground">{count} countries</span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
