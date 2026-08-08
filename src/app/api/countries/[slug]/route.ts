import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { toDetail } from "@/lib/serialize";

export const revalidate = 3600;

/** GET /api/countries/[slug] — full country detail with cities and sections. */
export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  try {
    const country = await prisma.country.findUnique({ where: { slug }, include: { cities: true, sections: true } });
    if (!country) return NextResponse.json({ error: `No country with slug "${slug}"` }, { status: 404 });
    const borders = JSON.parse(country.borders || "[]") as string[];
    const neighbors = borders.length ? await prisma.country.findMany({ where: { cca3: { in: borders } } }) : [];
    return NextResponse.json(toDetail(country, neighbors), {
      headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" },
    });
  } catch (error) {
    console.error(`GET /api/countries/${slug} failed:`, error);
    return NextResponse.json({ error: "Failed to load country" }, { status: 500 });
  }
}
