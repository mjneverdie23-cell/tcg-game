/**
 * Country search ranking.
 *
 * Pure scoring logic shared by the /api/search route and the client-side
 * command palette. Higher scores rank first; 0 means no match.
 */

export type Searchable = {
  slug: string;
  name: string;
  officialName?: string;
  altSpellings?: string[];
  capital?: string[];
  region?: string;
  cca2?: string;
  cca3?: string;
};

function norm(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

/** Score a candidate against a query. Exact > prefix > word-prefix > substring. */
export function scoreCountry(query: string, c: Searchable): number {
  const q = norm(query);
  if (!q) return 0;

  const name = norm(c.name);
  if (name === q) return 100;
  if (name.startsWith(q)) return 90;
  if (name.split(/\s+/).some((w) => w.startsWith(q))) return 80;
  if (name.includes(q)) return 70;

  const code = q.length <= 3 ? q.toUpperCase() : null;
  if (code && (c.cca2 === code || c.cca3 === code)) return 85;

  const official = c.officialName ? norm(c.officialName) : "";
  if (official.startsWith(q)) return 60;
  if (official.includes(q)) return 50;

  for (const alt of c.altSpellings ?? []) {
    const a = norm(alt);
    if (a === q) return 65;
    if (a.startsWith(q)) return 55;
  }

  for (const cap of c.capital ?? []) {
    const capN = norm(cap);
    if (capN === q) return 58;
    if (capN.startsWith(q)) return 48;
    if (capN.includes(q)) return 35;
  }

  if (c.region && norm(c.region).startsWith(q)) return 20;
  return 0;
}

/** Rank candidates for a query; ties broken alphabetically for stability. */
export function rankCountries<T extends Searchable>(
  query: string,
  candidates: T[],
  limit = 10,
): (T & { score: number })[] {
  return candidates
    .map((c) => ({ ...c, score: scoreCountry(query, c) }))
    .filter((c) => c.score > 0)
    .sort((a, b) => b.score - a.score || a.name.localeCompare(b.name))
    .slice(0, limit);
}
