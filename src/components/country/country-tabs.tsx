"use client";

import * as React from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { SectionRenderer } from "@/components/content/section-renderer";
import { Icon } from "@/components/content/icon";
import { sectionDef } from "@/lib/sections";
import { useAtlasStore } from "@/lib/store";
import type { SectionDto } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CountryTabs({ slug, countryName, sections }: { slug: string; countryName: string; sections: SectionDto[] }) {
  const [active, setActive] = React.useState(sections[0]?.key ?? "overview");
  const markSectionRead = useAtlasStore((s) => s.markSectionRead);
  const toggleBookmark = useAtlasStore((s) => s.toggleBookmark);
  const bookmarks = useAtlasStore((s) => s.bookmarks);

  React.useEffect(() => {
    if (active) markSectionRead(slug, active);
  }, [active, slug, markSectionRead]);

  return (
    <Tabs value={active} onValueChange={setActive} className="flex h-full flex-col">
      <div className="border-b bg-background/80 backdrop-blur">
        <ScrollArea className="w-full whitespace-nowrap">
          <TabsList className="inline-flex h-auto w-max gap-1 bg-transparent p-2">
            {sections.map((s) => {
              const def = sectionDef(s.key);
              return (
                <TabsTrigger key={s.key} value={s.key} className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                  <Icon name={def?.icon} className="h-3.5 w-3.5" />
                  {s.title}
                </TabsTrigger>
              );
            })}
          </TabsList>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {sections.map((s) => {
          const isBookmarked = bookmarks.some((b) => b.slug === slug && b.sectionKey === s.key);
          return (
            <TabsContent key={s.key} value={s.key} className="mt-0 p-4 sm:p-6 focus-visible:outline-none">
              <div className="mb-4 flex items-center justify-between gap-2">
                <h2 className="text-xl font-bold tracking-tight">{s.title}</h2>
                <button
                  onClick={() => toggleBookmark({ slug, sectionKey: s.key, countryName, sectionTitle: s.title })}
                  className={cn("inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-accent", isBookmarked && "border-primary text-primary")}
                  aria-pressed={isBookmarked}
                >
                  {isBookmarked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <Bookmark className="h-3.5 w-3.5" />}
                  {isBookmarked ? "Bookmarked" : "Bookmark"}
                </button>
              </div>
              <SectionRenderer blocks={s.blocks} />
            </TabsContent>
          );
        })}
      </div>
    </Tabs>
  );
}
