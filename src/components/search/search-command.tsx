"use client";

/**
 * Global search: a ⌘K command palette with debounced autocomplete against
 * /api/search, plus recently-viewed and favorite countries when the query is
 * empty. Falls back to the static countries index when the API is offline.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { Clock, Heart, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { useAtlasStore } from "@/lib/store";
import { rankCountries } from "@/lib/search";
import type { SearchResult } from "@/lib/types";

type IndexEntry = {
  slug: string;
  name: string;
  officialName: string;
  cca2: string;
  cca3: string;
  flagEmoji: string;
  region: string;
  capital: string[];
  altSpellings: string[];
};

export function SearchCommand() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<SearchResult[]>([]);
  const [loading, setLoading] = React.useState(false);
  const indexRef = React.useRef<IndexEntry[] | null>(null);
  const recent = useAtlasStore((s) => s.recent);
  const favorites = useAtlasStore((s) => s.favorites);

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || e.key === "/") {
        const target = e.target as HTMLElement;
        if (e.key === "/" && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  React.useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=10`);
        if (!res.ok) throw new Error(`search failed: ${res.status}`);
        setResults((await res.json()) as SearchResult[]);
      } catch {
        try {
          if (!indexRef.current) {
            const res = await fetch("/data/countries-index.json");
            indexRef.current = (await res.json()) as IndexEntry[];
          }
          const ranked = rankCountries(query, indexRef.current, 10);
          setResults(ranked.map((r) => ({ slug: r.slug, name: r.name, flagEmoji: r.flagEmoji, region: r.region ?? "", capital: r.capital ?? [], score: r.score })));
        } catch {
          setResults([]);
        }
      } finally {
        setLoading(false);
      }
    }, 160);
    return () => clearTimeout(t);
  }, [query]);

  const go = React.useCallback(
    (slug: string) => {
      setOpen(false);
      setQuery("");
      router.push(`/country/${slug}`);
    },
    [router],
  );

  return (
    <>
      <Button variant="outline" className="relative h-9 w-9 p-0 sm:w-56 sm:justify-start sm:px-3 text-muted-foreground" onClick={() => setOpen(true)} aria-label="Search countries">
        <Search className="h-4 w-4 sm:mr-2" />
        <span className="hidden sm:inline-flex">Search countries…</span>
        <kbd className="pointer-events-none absolute right-2 hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium sm:flex">⌘K</kbd>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} title="Search countries">
        <CommandInput placeholder="Search countries, capitals, codes…" value={query} onValueChange={setQuery} />
        <CommandList>
          {query.trim() ? (
            <>
              {!loading && <CommandEmpty>No countries found for “{query}”.</CommandEmpty>}
              <CommandGroup heading="Countries">
                {results.map((r) => (
                  <CommandItem key={r.slug} value={r.slug} onSelect={() => go(r.slug)}>
                    <span className="text-lg leading-none">{r.flagEmoji}</span>
                    <span className="font-medium">{r.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">{r.capital[0] ?? r.region}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          ) : (
            <>
              {recent.length > 0 && (
                <CommandGroup heading="Recently viewed">
                  {recent.slice(0, 5).map((r) => (
                    <CommandItem key={r.slug} value={`recent-${r.slug}`} onSelect={() => go(r.slug)}>
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <span className="text-lg leading-none">{r.flagEmoji}</span>
                      {r.name}
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
              {favorites.length > 0 && (
                <CommandGroup heading="Favorites">
                  {favorites.slice(0, 5).map((slug) => (
                    <CommandItem key={slug} value={`fav-${slug}`} onSelect={() => go(slug)}>
                      <Heart className="h-4 w-4 text-muted-foreground" />
                      <span className="capitalize">{slug.replace(/-/g, " ")}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
              {recent.length === 0 && favorites.length === 0 && (
                <div className="py-6 text-center text-sm text-muted-foreground">Type to search 197 countries by name, capital or ISO code.</div>
              )}
            </>
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
}
