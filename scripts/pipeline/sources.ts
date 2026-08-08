/**
 * Upstream open-data sources for the World Atlas pipeline.
 *
 * Everything is fetched over HTTPS and cached on disk (.cache/pipeline) so
 * re-runs are fast and the pipeline works offline once primed. Sources:
 *
 *  - REST Countries (restcountries/restcountries) — canonical country facts.
 *  - mledoze/countries — per-country GeoJSON shapes (Natural Earth derived).
 *  - Natural Earth (martynafford/natural-earth-geojson) — world polygons,
 *    admin-1 boundaries, populated places, rivers, lakes.
 *  - samayo/country-json — thematic datasets (religion, dishes, temperatures…).
 */

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

export const CACHE_DIR = path.join(process.cwd(), ".cache", "pipeline");

const GH = "https://raw.githubusercontent.com";

export const SOURCES = {
  restCountries: `${GH}/restcountries/restcountries/master/src/main/resources/countriesV3.1.json`,
  countryShape: (cca3: string) => `${GH}/mledoze/countries/master/data/${cca3.toLowerCase()}.geo.json`,
  neWorld110m: `${GH}/martynafford/natural-earth-geojson/master/110m/cultural/ne_110m_admin_0_countries.json`,
  neAdmin1: `${GH}/martynafford/natural-earth-geojson/master/10m/cultural/ne_10m_admin_1_states_provinces.json`,
  nePlaces: `${GH}/martynafford/natural-earth-geojson/master/50m/cultural/ne_50m_populated_places_simple.json`,
  neRivers: `${GH}/martynafford/natural-earth-geojson/master/50m/physical/ne_50m_rivers_lake_centerlines.json`,
  neLakes: `${GH}/martynafford/natural-earth-geojson/master/50m/physical/ne_50m_lakes.json`,
  samayo: (dataset: string) => `${GH}/samayo/country-json/master/src/country-by-${dataset}.json`,
} as const;

function cacheKey(url: string): string {
  return url.replace(/[^a-zA-Z0-9._-]+/g, "_").slice(-180);
}

export type FetchOptions = { fresh?: boolean; optional?: boolean; retries?: number };

/** Fetch a URL as text with disk caching, retries and backoff. */
export async function fetchCached(url: string, opts: FetchOptions = {}): Promise<string | null> {
  const { fresh = false, optional = false, retries = 3 } = opts;
  await mkdir(CACHE_DIR, { recursive: true });
  const file = path.join(CACHE_DIR, cacheKey(url));

  if (!fresh && existsSync(file)) return readFile(file, "utf8");

  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(60_000) });
      if (res.status === 404) {
        if (optional) return null;
        throw new Error(`404 Not Found: ${url}`);
      }
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      const text = await res.text();
      await writeFile(file, text, "utf8");
      return text;
    } catch (err) {
      lastError = err;
      if (attempt < retries) await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt));
    }
  }
  if (optional) {
    console.warn(`  ⚠ optional source unavailable: ${url}`);
    return null;
  }
  throw lastError;
}

export async function fetchJson<T>(url: string, opts: FetchOptions = {}): Promise<T | null> {
  const text = await fetchCached(url, opts);
  return text == null ? null : (JSON.parse(text) as T);
}

/** Run async jobs with bounded concurrency. */
export async function pool<T, R>(
  items: T[],
  limit: number,
  worker: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const i = next++;
      results[i] = await worker(items[i], i);
    }
  });
  await Promise.all(runners);
  return results;
}
