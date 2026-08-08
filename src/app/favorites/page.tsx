"use client";

import Link from "next/link";
import { Heart, Bookmark, Clock, Trash2 } from "lucide-react";
import { useAtlasStore } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function FavoritesPage() {
  const favorites = useAtlasStore((s) => s.favorites);
  const recent = useAtlasStore((s) => s.recent);
  const bookmarks = useAtlasStore((s) => s.bookmarks);
  const toggleFavorite = useAtlasStore((s) => s.toggleFavorite);
  const toggleBookmark = useAtlasStore((s) => s.toggleBookmark);

  const empty = favorites.length === 0 && recent.length === 0 && bookmarks.length === 0;

  return (
    <div className="container py-8">
      <h1 className="text-3xl font-bold tracking-tight">Your Atlas</h1>
      <p className="mt-1 text-muted-foreground">Favorites, bookmarks and recently viewed countries — saved privately on this device.</p>

      {empty && (
        <div className="mt-12 flex flex-col items-center gap-3 text-center text-muted-foreground">
          <Heart className="h-10 w-10" />
          <p>Nothing saved yet. Open a country and tap <strong>Favorite</strong> or bookmark a section.</p>
          <Button asChild className="mt-2"><Link href="/browse">Browse countries</Link></Button>
        </div>
      )}

      {favorites.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Heart className="h-5 w-5 text-primary" /> Favorites</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {favorites.map((slug) => (
              <Card key={slug}>
                <CardContent className="flex items-center gap-3 p-3">
                  <Link href={`/country/${slug}`} className="flex-1 font-medium capitalize hover:underline">{slug.replace(/-/g, " ")}</Link>
                  <Button variant="ghost" size="icon" onClick={() => toggleFavorite(slug)} aria-label="Remove favorite"><Trash2 className="h-4 w-4" /></Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {bookmarks.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Bookmark className="h-5 w-5 text-primary" /> Bookmarked sections</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {bookmarks.map((b) => (
              <Card key={`${b.slug}-${b.sectionKey}`}>
                <CardContent className="flex items-center gap-3 p-3">
                  <Link href={`/country/${b.slug}`} className="flex-1 hover:underline">
                    <span className="font-medium">{b.countryName}</span>
                    <span className="text-muted-foreground"> — {b.sectionTitle}</span>
                  </Link>
                  <Button variant="ghost" size="icon" onClick={() => toggleBookmark(b)} aria-label="Remove bookmark"><Trash2 className="h-4 w-4" /></Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {recent.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Clock className="h-5 w-5 text-primary" /> Recently viewed</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {recent.map((r) => (
              <Link key={r.slug} href={`/country/${r.slug}`}>
                <Card className="transition-all hover:shadow-md hover:-translate-y-0.5">
                  <CardContent className="flex items-center gap-2 p-3">
                    <span className="text-2xl">{r.flagEmoji}</span>
                    <span className="truncate text-sm font-medium">{r.name}</span>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
