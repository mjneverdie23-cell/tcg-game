"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowDownAZ, Users, Ruler } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatArea, formatCompact } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CountrySummary } from "@/lib/types";

const REGIONS = ["All", "Africa", "Americas", "Asia", "Europe", "Oceania"] as const;
type Sort = "name" | "population" | "area";
const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

export function CountryBrowser({ countries }: { countries: CountrySummary[] }) {
  const params = useSearchParams();
  const initialRegion = params.get("region") ?? "All";
  const [region, setRegion] = React.useState<string>(REGIONS.includes(initialRegion as (typeof REGIONS)[number]) ? initialRegion : "All");
  const [query, setQuery] = React.useState("");
  const [sort, setSort] = React.useState<Sort>("name");

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = countries.filter((c) => {
      if (region !== "All" && c.region !== region) return false;
      if (!q) return true;
      return c.name.toLowerCase().includes(q) || (c.capital[0]?.toLowerCase().includes(q) ?? false);
    });
    list = list.slice().sort((a, b) => {
      if (sort === "population") return b.population - a.population;
      if (sort === "area") return b.area - a.area;
      return a.name.localeCompare(b.name);
    });
    return list;
  }, [countries, region, query, sort]);

  const grouped = React.useMemo(() => {
    if (sort !== "name") return null;
    const groups = new Map<string, CountrySummary[]>();
    for (const c of filtered) {
      const letter = c.name[0].toUpperCase();
      const key = /[A-Z]/.test(letter) ? letter : "#";
      (groups.get(key) ?? groups.set(key, []).get(key)!).push(c);
    }
    return groups;
  }, [filtered, sort]);

  const activeLetters = new Set(grouped ? [...grouped.keys()] : []);

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center">
        <Input placeholder="Filter by name or capital…" value={query} onChange={(e) => setQuery(e.target.value)} className="md:max-w-xs" aria-label="Filter countries" />
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by region">
          {REGIONS.map((r) => (
            <button key={r} onClick={() => setRegion(r)} aria-pressed={region === r} className={cn("rounded-full border px-3 py-1 text-sm transition-colors", region === r ? "bg-primary text-primary-foreground" : "hover:bg-accent")}>
              {r}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5 md:ml-auto" role="group" aria-label="Sort">
          {[
            { key: "name" as const, icon: ArrowDownAZ, label: "Name" },
            { key: "population" as const, icon: Users, label: "Population" },
            { key: "area" as const, icon: Ruler, label: "Area" },
          ].map((s) => (
            <button key={s.key} onClick={() => setSort(s.key)} aria-pressed={sort === s.key} className={cn("inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm transition-colors", sort === s.key ? "border-primary text-primary" : "hover:bg-accent")}>
              <s.icon className="h-3.5 w-3.5" />
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {sort === "name" && (
        <div className="mb-4 flex flex-wrap gap-1 border-y py-2 text-sm">
          {LETTERS.map((l) => (
            <a key={l} href={activeLetters.has(l) ? `#letter-${l}` : undefined} className={cn("w-6 text-center", activeLetters.has(l) ? "text-primary hover:underline" : "cursor-default text-muted-foreground/40")}>
              {l}
            </a>
          ))}
        </div>
      )}

      <p className="mb-4 text-sm text-muted-foreground">{filtered.length} countries</p>

      {grouped ? (
        [...grouped.entries()].map(([letter, list]) => (
          <section key={letter} id={`letter-${letter}`} className="mb-6 scroll-mt-20">
            <h2 className="mb-3 text-lg font-bold text-primary">{letter}</h2>
            <Grid list={list} />
          </section>
        ))
      ) : (
        <Grid list={filtered} />
      )}
    </div>
  );
}

function Grid({ list }: { list: CountrySummary[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {list.map((c, i) => (
        <motion.div key={c.slug} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.01, 0.2) }}>
          <Link href={`/country/${c.slug}`}>
            <Card className="h-full transition-all hover:shadow-md hover:-translate-y-0.5">
              <CardContent className="flex items-center gap-3 p-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/flags/${c.cca2.toLowerCase()}.svg`} alt="" className="h-8 w-12 shrink-0 rounded border object-cover" width={48} height={32} loading="lazy" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">{c.name}</span>
                    <Badge variant="outline" className="shrink-0 text-[10px]">{c.region}</Badge>
                  </div>
                  <div className="truncate text-xs text-muted-foreground">{c.capital[0] ?? "—"} · {formatCompact(c.population)} · {formatArea(c.area)}</div>
                </div>
              </CardContent>
            </Card>
          </Link>
        </motion.div>
      ))}
    </div>
  );
}
