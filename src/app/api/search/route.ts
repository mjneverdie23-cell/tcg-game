import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { rankCountries } from "@/lib/search";
import type { SearchResult } from "@/lib/types";

export const revalidate = 3600;

/** GET /api/search?q=fra&limit=10 — ranked autocomplete results. */
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim() ?? "";
  const limit = Math.min(25, Math.max(1, Number(req.nextUrl.searchParams.get("limit")) || 10));
  if (q.length < 1) return NextResponse.json([]);

  try {
    const normalized = q.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const candidates = await prisma.country.findMany({ where: { searchText: { contains: normalized } }, take: 80 });
    const ranked = rankCountries(
      q,
      candidates.map((c) => ({
        slug: c.slug,
        name: c.name,
        officialName: c.officialName,
        altSpellings: JSON.parse(c.altSpellings || "[]") as string[],
        capital: JSON.parse(c.capital || "[]") as string[],
        region: c.region,
        cca2: c.cca2,
        cca3: c.cca3,
        flagEmoji: c.flagEmoji,
      })),
      limit,
    );
    const results: SearchResult[] = ranked.map((r) => ({
      slug: r.slug,
      name: r.name,
      flagEmoji: (r as { flagEmoji: string }).flagEmoji,
      region: r.region ?? "",
      capital: r.capital ?? [],
      score: r.score,
    }));
    return NextResponse.json(results, { headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" } });
  } catch (error) {
    console.error("GET /api/search failed:", error);
    return NextResponse.json({ error: "Search failed" }, { status: 500 });
  }
}
