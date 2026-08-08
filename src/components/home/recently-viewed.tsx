"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Clock } from "lucide-react";
import { useAtlasStore } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";

/** Horizontal strip of the user's recently opened countries (localStorage). */
export function RecentlyViewed() {
  const recent = useAtlasStore((s) => s.recent);
  if (recent.length === 0) return null;

  return (
    <section className="container py-8" aria-labelledby="recent-heading">
      <h2 id="recent-heading" className="mb-4 flex items-center gap-2 text-lg font-semibold">
        <Clock className="h-5 w-5 text-muted-foreground" /> Recently viewed
      </h2>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
        {recent.map((r, i) => (
          <motion.div key={r.slug} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
            <Link href={`/country/${r.slug}`} className="block">
              <Card className="w-40 shrink-0 transition-all hover:shadow-md hover:-translate-y-0.5">
                <CardContent className="flex items-center gap-2 p-3">
                  <span className="text-2xl">{r.flagEmoji}</span>
                  <span className="truncate text-sm font-medium">{r.name}</span>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
