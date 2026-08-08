/**
 * Geometry helpers for the pipeline: bounding boxes, label points
 * (pole of inaccessibility) and Natural Earth property normalization.
 */

import polylabel from "polylabel";

export type Position = [number, number];
export type PolygonCoords = number[][][];
export type MultiPolygonCoords = number[][][][];

export type Geometry =
  | { type: "Polygon"; coordinates: PolygonCoords }
  | { type: "MultiPolygon"; coordinates: MultiPolygonCoords }
  | { type: string; coordinates: unknown };

export type Feature<P = Record<string, unknown>> = {
  type: "Feature";
  properties: P;
  geometry: Geometry;
};

export type FeatureCollection<P = Record<string, unknown>> = {
  type: "FeatureCollection";
  features: Feature<P>[];
};

/** [west, south, east, north] of any (Multi)Polygon geometry. */
export function bboxOf(geometry: Geometry): [number, number, number, number] | null {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  const visit = (coords: unknown): void => {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === "number") {
      const [x, y] = coords as number[];
      if (x < w) w = x;
      if (x > e) e = x;
      if (y < s) s = y;
      if (y > n) n = y;
      return;
    }
    for (const c of coords) visit(c);
  };
  visit((geometry as { coordinates?: unknown }).coordinates);
  if (!Number.isFinite(w)) return null;
  return [w, s, e, n];
}

/** Shoelace area of a ring (planar approximation — used only for ranking). */
function ringArea(ring: number[][]): number {
  let area = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    area += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
  }
  return Math.abs(area / 2);
}

/**
 * Visual label point for a country: the pole of inaccessibility of its
 * largest polygon. Much better than a centroid for concave shapes,
 * archipelagos and countries with overseas territories.
 */
export function labelPoint(geometry: Geometry): Position | null {
  let polygons: PolygonCoords[] = [];
  if (geometry.type === "Polygon") {
    polygons = [(geometry as { coordinates: PolygonCoords }).coordinates];
  } else if (geometry.type === "MultiPolygon") {
    polygons = (geometry as { coordinates: MultiPolygonCoords }).coordinates;
  }
  if (polygons.length === 0) return null;

  let best: PolygonCoords | null = null;
  let bestArea = -1;
  for (const poly of polygons) {
    if (!poly[0] || poly[0].length < 4) continue;
    const area = ringArea(poly[0]);
    if (area > bestArea) {
      bestArea = area;
      best = poly;
    }
  }
  if (!best) return null;
  const [x, y] = polylabel(best, 0.05);
  return [x, y];
}

/**
 * Resolve the ISO 3166-1 alpha-3 code of a Natural Earth admin-0 feature.
 * NE marks some codes as "-99" (France, Norway…), so fall back through the
 * _EH variants and finally ADM0_A3.
 */
export function neIsoA3(props: Record<string, unknown>): string | null {
  const candidates = ["ISO_A3", "iso_a3", "ISO_A3_EH", "iso_a3_eh", "ADM0_A3", "adm0_a3", "SOV_A3", "sov_a3"];
  for (const key of candidates) {
    const v = props[key];
    if (typeof v === "string" && /^[A-Z]{3}$/i.test(v) && v !== "-99") return v.toUpperCase();
  }
  return null;
}

/** Read the first defined property among the given (case-variant) keys. */
export function neProp<T = unknown>(props: Record<string, unknown>, ...keys: string[]): T | undefined {
  for (const key of keys) {
    if (props[key] !== undefined && props[key] !== null) return props[key] as T;
    const lower = key.toLowerCase();
    if (props[lower] !== undefined && props[lower] !== null) return props[lower] as T;
    const upper = key.toUpperCase();
    if (props[upper] !== undefined && props[upper] !== null) return props[upper] as T;
  }
  return undefined;
}
