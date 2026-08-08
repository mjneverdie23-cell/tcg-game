/**
 * Shared domain types for World Atlas.
 *
 * `ContentBlock` is the unit of encyclopedia content: the data pipeline writes
 * arrays of typed blocks into the database, and `SectionRenderer` renders them.
 * Adding a new block type means extending this union, the pipeline generator,
 * and the renderer — nothing else.
 */

export type StatItem = { label: string; value: string; hint?: string };
export type TimelineEvent = {
  when: string; // e.g. "c. 3500 BCE", "1789 CE", "Today"
  era?: "BCE" | "CE";
  title: string;
  description?: string;
};
export type ChartDatum = { name: string; value: number; hint?: string };
export type FactCard = { title: string; body: string; icon?: string };
export type LinkItem = { label: string; href: string; source?: string };
export type GalleryImage = { src: string; alt: string; caption?: string; credit?: string };
export type FeatureCard = { name: string; blurb: string; image?: string; meta?: string };

export type ContentBlock =
  | { type: "prose"; markdown: string }
  | { type: "stats"; items: StatItem[] }
  | { type: "table"; caption?: string; headers: string[]; rows: string[][] }
  | { type: "timeline"; events: TimelineEvent[] }
  | { type: "chart"; chart: "bar" | "pie" | "line" | "area"; title: string; unit?: string; data: ChartDatum[]; note?: string }
  | { type: "facts"; cards: FactCard[] }
  | { type: "feature-cards"; title?: string; cards: FeatureCard[] }
  | { type: "links"; title?: string; items: LinkItem[] }
  | { type: "gallery"; images: GalleryImage[] }
  | { type: "quote"; text: string; attribution?: string }
  | { type: "references"; items: LinkItem[] };

/** Lightweight country shape used for lists, search and the world map. */
export type CountrySummary = {
  slug: string;
  cca2: string;
  cca3: string;
  name: string;
  officialName: string;
  flagEmoji: string;
  region: string;
  subregion: string | null;
  capital: string[];
  population: number;
  area: number;
  latitude: number;
  longitude: number;
  labelLat: number | null;
  labelLng: number | null;
  unMember: boolean;
};

export type CityDto = {
  name: string;
  lat: number;
  lng: number;
  population: number | null;
  isCapital: boolean;
  rank: number;
};

export type SectionDto = { key: string; title: string; order: number; blocks: ContentBlock[] };

/** Full country detail returned by /api/countries/[slug]. */
export type CountryDetail = CountrySummary & {
  ccn3: string | null;
  nativeNames: Record<string, { official: string; common: string }>;
  altSpellings: string[];
  capitalLat: number | null;
  capitalLng: number | null;
  continents: string[];
  populationDensity: number | null;
  bbox: [number, number, number, number] | null;
  landlocked: boolean;
  borders: string[];
  languages: Record<string, string>;
  currencies: Record<string, { name: string; symbol?: string }>;
  timezones: string[];
  tld: string[];
  callingCodes: string[];
  demonyms: { eng?: { m: string; f: string } } | null;
  coatOfArmsUrl: string | null;
  independent: boolean;
  status: string;
  gini: Record<string, number> | null;
  carSide: string | null;
  startOfWeek: string | null;
  fifa: string | null;
  maps: { googleMaps?: string; openStreetMaps?: string } | null;
  governmentType: string | null;
  religion: string | null;
  nationalDish: string | null;
  nationalSymbol: string | null;
  independenceDate: string | null;
  lifeExpectancy: number | null;
  avgTemperature: number | null;
  elevation: number | null;
  heroImage: string | null;
  cities: CityDto[];
  neighbors: CountrySummary[];
  sections: SectionDto[];
};

export type SearchResult = {
  slug: string;
  name: string;
  flagEmoji: string;
  region: string;
  capital: string[];
  score: number;
};
