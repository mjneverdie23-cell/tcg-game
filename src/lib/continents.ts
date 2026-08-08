/** Continent and region metadata used by filters, browse pages and the map. */

export const CONTINENTS = [
  "Africa",
  "Antarctica",
  "Asia",
  "Europe",
  "North America",
  "Oceania",
  "South America",
] as const;

export type Continent = (typeof CONTINENTS)[number];

export const REGIONS = ["Africa", "Americas", "Antarctic", "Asia", "Europe", "Oceania"] as const;
export type Region = (typeof REGIONS)[number];

export const REGION_EMOJI: Record<string, string> = {
  Africa: "🌍",
  Americas: "🌎",
  Antarctic: "🧊",
  Asia: "🌏",
  Europe: "🏰",
  Oceania: "🏝️",
};

/** Major oceans, labeled on the world map at fixed positions. */
export const OCEANS: { name: string; lat: number; lng: number }[] = [
  { name: "Pacific Ocean", lat: 0, lng: -150 },
  { name: "Pacific Ocean", lat: 5, lng: 165 },
  { name: "Atlantic Ocean", lat: 25, lng: -40 },
  { name: "South Atlantic Ocean", lat: -30, lng: -18 },
  { name: "Indian Ocean", lat: -18, lng: 78 },
  { name: "Arctic Ocean", lat: 79, lng: 0 },
  { name: "Southern Ocean", lat: -62, lng: 60 },
];
