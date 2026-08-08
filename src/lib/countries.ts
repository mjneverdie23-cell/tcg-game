import { prisma } from "./prisma";
import { toSummary, toDetail } from "./serialize";
import type { CountryDetail, CountrySummary } from "./types";

/** All countries as summaries, alphabetical. Cached by the page's revalidate. */
export async function getAllSummaries(): Promise<CountrySummary[]> {
  const rows = await prisma.country.findMany({ orderBy: { name: "asc" } });
  return rows.map(toSummary);
}

export async function getAllSlugs(): Promise<string[]> {
  const rows = await prisma.country.findMany({ select: { slug: true } });
  return rows.map((r) => r.slug);
}

export async function getCountryDetail(slug: string): Promise<CountryDetail | null> {
  const country = await prisma.country.findUnique({ where: { slug }, include: { cities: true, sections: true } });
  if (!country) return null;
  const borders = JSON.parse(country.borders || "[]") as string[];
  const neighbors = borders.length ? await prisma.country.findMany({ where: { cca3: { in: borders } } }) : [];
  return toDetail(country, neighbors);
}
