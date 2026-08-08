import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { toSummary } from "@/lib/serialize";

export const revalidate = 3600;

/** GET /api/countries — every country as a lightweight summary. */
export async function GET() {
  try {
    const countries = await prisma.country.findMany({ orderBy: { name: "asc" } });
    return NextResponse.json(countries.map(toSummary), {
      headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" },
    });
  } catch (error) {
    console.error("GET /api/countries failed:", error);
    return NextResponse.json({ error: "Failed to load countries" }, { status: 500 });
  }
}
