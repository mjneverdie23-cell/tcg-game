/**
 * World Atlas data pipeline.
 *
 *   npm run pipeline          # incremental (uses .cache/pipeline)
 *   npm run pipeline:fresh    # re-download every source
 *
 * Downloads open datasets, normalizes into one record per sovereign state,
 * merges the curated knowledge base, generates the 29 encyclopedia sections,
 * loads the Prisma database, and emits static geodata + flag SVGs into /public.
 */

import { copyFile, mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import { SOURCES, fetchCached, fetchJson, pool } from "./sources";
import { bboxOf, labelPoint, neIsoA3, neProp, type Feature, type FeatureCollection, type Geometry } from "./geo";
import { generateSections, type CountryRecord, type NeighborRef } from "./content";
import { knowledgeFor, CONTINENT_HISTORY, commons } from "./knowledge";
import { slugify } from "../../src/lib/slug";

const prisma = new PrismaClient();
const FRESH = process.argv.includes("--fresh");
const PUBLIC_DATA = path.join(process.cwd(), "public", "data");
const PUBLIC_FLAGS = path.join(process.cwd(), "public", "flags");

type RestCountry = {
  name: { common: string; official: string; nativeName?: Record<string, { official: string; common: string }> };
  cca2: string;
  ccn3?: string;
  cca3: string;
  independent?: boolean;
  status: string;
  unMember: boolean;
  currencies?: Record<string, { name: string; symbol?: string }>;
  idd?: { root?: string; suffixes?: string[] };
  capital?: string[];
  altSpellings?: string[];
  region: string;
  subregion?: string;
  languages?: Record<string, string>;
  latlng?: [number, number];
  landlocked?: boolean;
  borders?: string[];
  area: number;
  demonyms?: { eng?: { m: string; f: string } };
  flag?: string;
  maps?: { googleMaps?: string; openStreetMaps?: string };
  population: number;
  gini?: Record<string, number>;
  fifa?: string;
  car?: { side?: string };
  timezones?: string[];
  continents?: string[];
  startOfWeek?: string;
  capitalInfo?: { latlng?: [number, number] };
  tld?: string[];
  coatOfArms?: { png?: string; svg?: string };
};

const EXTRA_STATES = new Set(["TWN", "VAT", "PSE", "UNK", "KOS", "XKX"]);
function isSovereign(rc: RestCountry): boolean {
  return rc.unMember || rc.independent === true || EXTRA_STATES.has(rc.cca3);
}

function nameKey(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/^the\s+/, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const SAMAYO_ALIASES: Record<string, string> = {
  "czech republic": "CZE", swaziland: "SWZ", macedonia: "MKD", "the former yugoslav republic of macedonia": "MKD",
  burma: "MMR", myanmar: "MMR", "cape verde": "CPV", "east timor": "TLS", "timor leste": "TLS", "ivory coast": "CIV",
  "cote d ivoire": "CIV", "cote divoire": "CIV", "democratic republic of congo": "COD", "the democratic republic of congo": "COD",
  "congo democratic republic of the": "COD", congo: "COG", "republic of the congo": "COG", "korea south": "KOR",
  "south korea": "KOR", "korea north": "PRK", "north korea": "PRK", "russian federation": "RUS", russia: "RUS",
  "united states of america": "USA", "united states": "USA", "united kingdom of great britain and northern ireland": "GBR",
  "united kingdom": "GBR", "holy see vatican city state": "VAT", "vatican city": "VAT", "holy see": "VAT",
  "brunei darussalam": "BRN", brunei: "BRN", "lao people s democratic republic": "LAO", laos: "LAO",
  "syrian arab republic": "SYR", syria: "SYR", "viet nam": "VNM", vietnam: "VNM", "iran islamic republic of": "IRN",
  iran: "IRN", "tanzania united republic of": "TZA", tanzania: "TZA", "moldova republic of": "MDA", moldova: "MDA",
  "bolivia plurinational state of": "BOL", bolivia: "BOL", "venezuela bolivarian republic of": "VEN", venezuela: "VEN",
  "micronesia federated states of": "FSM", micronesia: "FSM", "saint kitts and nevis": "KNA", "st kitts and nevis": "KNA",
  "saint lucia": "LCA", "st lucia": "LCA", "saint vincent and the grenadines": "VCT", "st vincent and the grenadines": "VCT",
  "sao tome and principe": "STP", gambia: "GMB", "the gambia": "GMB", bahamas: "BHS", "the bahamas": "BHS",
  netherlands: "NLD", "the netherlands": "NLD", kosovo: "UNK", turkey: "TUR", turkiye: "TUR",
};

type SamayoRow = { country: string } & Record<string, unknown>;

async function loadSamayo(dataset: string, keyByCca3: Map<string, string>): Promise<Map<string, unknown>> {
  const rows = await fetchJson<SamayoRow[]>(SOURCES.samayo(dataset), { fresh: FRESH, optional: true });
  const out = new Map<string, unknown>();
  if (!rows) return out;
  for (const row of rows) {
    if (!row?.country) continue;
    const key = nameKey(row.country);
    const cca3 = SAMAYO_ALIASES[key] ?? keyByCca3.get(key);
    if (!cca3) continue;
    const valueKey = Object.keys(row).find((k) => k !== "country");
    if (!valueKey) continue;
    const value = row[valueKey];
    if (value !== null && value !== undefined && value !== "") out.set(cca3, value);
  }
  return out;
}

const num = (v: unknown): number | null => {
  const n = typeof v === "string" ? parseFloat(v) : typeof v === "number" ? v : NaN;
  return Number.isFinite(n) ? n : null;
};
const str = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);

async function main() {
  const t0 = Date.now();
  console.log(`World Atlas pipeline ${FRESH ? "(fresh download)" : "(cached where possible)"}\n`);

  await mkdir(path.join(PUBLIC_DATA, "countries"), { recursive: true });
  await mkdir(path.join(PUBLIC_DATA, "physical"), { recursive: true });
  await mkdir(PUBLIC_FLAGS, { recursive: true });

  /* 1 ── REST Countries master list */
  console.log("→ REST Countries dataset");
  const all = (await fetchJson<RestCountry[]>(SOURCES.restCountries, { fresh: FRESH }))!;
  const sovereign = all.filter(isSovereign).sort((a, b) => a.name.common.localeCompare(b.name.common));
  console.log(`  ${all.length} territories in source, ${sovereign.length} sovereign states selected`);

  const byCca3 = new Map(sovereign.map((rc) => [rc.cca3, rc]));
  const allByCca3 = new Map(all.map((rc) => [rc.cca3, rc]));
  const keyToCca3 = new Map<string, string>();
  for (const rc of sovereign) {
    keyToCca3.set(nameKey(rc.name.common), rc.cca3);
    keyToCca3.set(nameKey(rc.name.official), rc.cca3);
    for (const alt of rc.altSpellings ?? []) if (alt.length > 3) keyToCca3.set(nameKey(alt), rc.cca3);
  }

  /* 2 ── samayo thematic datasets */
  console.log("→ samayo/country-json thematic datasets");
  const [dish, religionMap, government, independence, lifeExp, avgTemp, elevation, symbol] = await Promise.all([
    loadSamayo("national-dish", keyToCca3),
    loadSamayo("religion", keyToCca3),
    loadSamayo("government-type", keyToCca3),
    loadSamayo("independence-date", keyToCca3),
    loadSamayo("life-expectancy", keyToCca3),
    loadSamayo("yearly-average-temperature", keyToCca3),
    loadSamayo("elevation", keyToCca3),
    loadSamayo("national-symbol", keyToCca3),
  ]);
  console.log(`  joined: dish=${dish.size} religion=${religionMap.size} gov=${government.size} indep=${independence.size} lifeExp=${lifeExp.size} temp=${avgTemp.size} elev=${elevation.size} symbol=${symbol.size}`);

  /* 3 ── Natural Earth world polygons (110m) */
  console.log("→ Natural Earth 110m world polygons");
  const neWorld = (await fetchJson<FeatureCollection>(SOURCES.neWorld110m, { fresh: FRESH }))!;
  const worldFeatures: Feature[] = [];
  let sovereignPolygons = 0;
  for (const f of neWorld.features) {
    const iso = neIsoA3(f.properties);
    const rc = iso ? byCca3.get(iso === "KOS" ? "UNK" : iso) ?? allByCca3.get(iso === "KOS" ? "UNK" : iso) : undefined;
    const isSov = Boolean(rc && byCca3.has(rc.cca3));
    const lp = labelPoint(f.geometry);
    const name = rc?.name.common ?? neProp<string>(f.properties, "NAME_EN", "NAME", "ADMIN") ?? "Unknown";
    if (isSov) sovereignPolygons++;
    worldFeatures.push({
      type: "Feature",
      properties: {
        slug: rc && isSov ? slugify(rc.name.common) : null,
        name,
        cca2: rc?.cca2 ?? null,
        cca3: rc?.cca3 ?? iso,
        flag: rc?.flag ?? "",
        region: rc?.region ?? null,
        sovereign: isSov,
        labelLng: lp?.[0] ?? rc?.latlng?.[1] ?? 0,
        labelLat: lp?.[1] ?? rc?.latlng?.[0] ?? 0,
        area: rc?.area ?? 0,
      },
      geometry: f.geometry,
    });
  }
  console.log(`  ${worldFeatures.length} polygons (${sovereignPolygons} sovereign)`);

  /* 4 ── Per-country detailed shapes */
  console.log("→ per-country GeoJSON shapes");
  const shapes = new Map<string, Feature | null>();
  await pool(sovereign, 12, async (rc) => {
    const text = await fetchCached(SOURCES.countryShape(rc.cca3), { fresh: FRESH, optional: true });
    if (!text) return void shapes.set(rc.cca3, null);
    try {
      const fc = JSON.parse(text) as FeatureCollection;
      shapes.set(rc.cca3, fc.features?.[0] ?? null);
    } catch {
      shapes.set(rc.cca3, null);
    }
  });
  console.log(`  ${[...shapes.values()].filter(Boolean).length}/${sovereign.length} shapes downloaded`);

  /* 5 ── Admin-1 boundaries (10m), simplified with mapshaper */
  console.log("→ Natural Earth admin-1 boundaries (10m, simplifying)");
  const admin1Raw = await fetchCached(SOURCES.neAdmin1, { fresh: FRESH, optional: true });
  let admin1: FeatureCollection | null = null;
  if (admin1Raw) {
    type Mapshaper = { applyCommands: (cmd: string, input: Record<string, string>) => Promise<Record<string, string>> };
    const imported = (await import("mapshaper")) as unknown as Mapshaper & { default?: Mapshaper };
    const mapshaper = typeof imported.applyCommands === "function" ? imported : imported.default!;
    const out = await mapshaper.applyCommands(
      "-i admin1.json -simplify visvalingam 12% keep-shapes -filter-fields name,type_en,adm0_a3,sov_a3,iso_3166_2 -o out.json format=geojson precision=0.001",
      { "admin1.json": admin1Raw },
    );
    admin1 = JSON.parse(out["out.json"]) as FeatureCollection;
  }
  const admin1ByCountry = new Map<string, Feature[]>();
  if (admin1) {
    for (const f of admin1.features) {
      const iso = neProp<string>(f.properties, "adm0_a3", "sov_a3");
      if (!iso) continue;
      const cca3 = iso === "KOS" ? "UNK" : iso;
      if (!byCca3.has(cca3)) continue;
      const list = admin1ByCountry.get(cca3) ?? [];
      list.push({
        type: "Feature",
        properties: { name: neProp<string>(f.properties, "name") ?? "", type: neProp<string>(f.properties, "type_en", "type") ?? "" },
        geometry: f.geometry,
      });
      admin1ByCountry.set(cca3, list);
    }
  }
  console.log(`  admin-1 divisions for ${admin1ByCountry.size} countries`);

  /* 6 ── Populated places → cities per country */
  console.log("→ Natural Earth populated places");
  const places = (await fetchJson<FeatureCollection>(SOURCES.nePlaces, { fresh: FRESH }))!;
  type CityRow = { name: string; lat: number; lng: number; population: number | null; isCapital: boolean; rank: number };
  const citiesByCountry = new Map<string, CityRow[]>();
  for (const f of places.features) {
    const props = f.properties;
    const iso = neProp<string>(props, "adm0_a3", "sov_a3");
    if (!iso) continue;
    const cca3 = iso === "KOS" ? "UNK" : iso;
    if (!byCca3.has(cca3)) continue;
    const name = neProp<string>(props, "name", "nameascii");
    const lat = num(neProp(props, "latitude"));
    const lng = num(neProp(props, "longitude"));
    if (!name || lat == null || lng == null) continue;
    const featurecla = neProp<string>(props, "featurecla") ?? "";
    const isCapital = num(neProp(props, "adm0cap")) === 1 || /admin-0 capital/i.test(featurecla);
    const row: CityRow = { name, lat, lng, population: num(neProp(props, "pop_max", "pop_min")), isCapital, rank: num(neProp(props, "scalerank")) ?? 10 };
    const list = citiesByCountry.get(cca3) ?? [];
    list.push(row);
    citiesByCountry.set(cca3, list);
  }
  for (const list of citiesByCountry.values()) {
    list.sort((a, b) => (b.isCapital ? 1 : 0) - (a.isCapital ? 1 : 0) || a.rank - b.rank || (b.population ?? 0) - (a.population ?? 0));
    list.splice(40);
  }
  console.log(`  cities matched for ${citiesByCountry.size} countries`);

  /* 7 ── Physical layers */
  console.log("→ Natural Earth physical layers (rivers, lakes)");
  const rivers = await fetchCached(SOURCES.neRivers, { fresh: FRESH, optional: true });
  const lakes = await fetchCached(SOURCES.neLakes, { fresh: FRESH, optional: true });
  if (rivers) await writeFile(path.join(PUBLIC_DATA, "physical", "rivers.json"), rivers);
  if (lakes) await writeFile(path.join(PUBLIC_DATA, "physical", "lakes.json"), lakes);

  /* 8 ── Ranks + normalized records */
  console.log("→ normalizing records + merging curated knowledge");
  const byPop = [...sovereign].sort((a, b) => b.population - a.population);
  const byArea = [...sovereign].sort((a, b) => b.area - a.area);
  const density = (rc: RestCountry) => (rc.area > 0 ? rc.population / rc.area : null);
  const byDensity = sovereign.filter((rc) => density(rc) != null).sort((a, b) => density(b)! - density(a)!);
  const popRank = new Map(byPop.map((rc, i) => [rc.cca3, i + 1]));
  const areaRank = new Map(byArea.map((rc, i) => [rc.cca3, i + 1]));
  const densityRank = new Map(byDensity.map((rc, i) => [rc.cca3, i + 1]));

  const peersByRegion = new Map<string, { name: string; population: number; area: number }[]>();
  for (const rc of sovereign) {
    const list = peersByRegion.get(rc.region) ?? [];
    list.push({ name: rc.name.common, population: rc.population, area: rc.area });
    peersByRegion.set(rc.region, list);
  }
  for (const list of peersByRegion.values()) list.sort((a, b) => b.population - a.population);

  let curatedCount = 0;
  const records: CountryRecord[] = sovereign.map((rc) => {
    const neighbors: NeighborRef[] = (rc.borders ?? [])
      .map((b) => byCca3.get(b))
      .filter((n): n is RestCountry => Boolean(n))
      .map((n) => ({ name: n.name.common, slug: slugify(n.name.common), flagEmoji: n.flag ?? "", population: n.population, area: n.area }));
    const idd = rc.idd?.root ? (rc.idd.suffixes?.length ? rc.idd.suffixes.map((s) => `${rc.idd!.root}${s}`) : [rc.idd.root]).slice(0, 5) : [];
    const k = knowledgeFor(rc.cca3);
    if (k.destinations?.length || k.timeline?.length) curatedCount++;
    const continents = rc.continents ?? [];
    const continentHistory = CONTINENT_HISTORY[continents[0]] ?? CONTINENT_HISTORY[rc.region] ?? [];
    return {
      slug: slugify(rc.name.common),
      name: rc.name.common,
      officialName: rc.name.official,
      cca2: rc.cca2,
      cca3: rc.cca3,
      region: rc.region,
      subregion: rc.subregion ?? null,
      continents,
      capital: rc.capital ?? [],
      population: rc.population,
      area: rc.area,
      populationDensity: density(rc),
      latitude: rc.latlng?.[0] ?? 0,
      longitude: rc.latlng?.[1] ?? 0,
      landlocked: rc.landlocked ?? false,
      neighbors,
      languages: rc.languages ?? {},
      currencies: rc.currencies ?? {},
      timezones: rc.timezones ?? [],
      tld: rc.tld ?? [],
      callingCodes: idd,
      demonyms: rc.demonyms ?? null,
      flagEmoji: rc.flag ?? "",
      coatOfArmsUrl: rc.coatOfArms?.svg ?? rc.coatOfArms?.png ?? null,
      unMember: rc.unMember,
      independent: rc.independent ?? true,
      status: rc.status,
      gini: rc.gini ?? null,
      carSide: rc.car?.side ?? null,
      startOfWeek: rc.startOfWeek ?? null,
      fifa: rc.fifa ?? null,
      maps: rc.maps ?? null,
      governmentType: str(government.get(rc.cca3)),
      religion: str(religionMap.get(rc.cca3)),
      nationalDish: str(dish.get(rc.cca3)),
      nationalSymbol: str(symbol.get(rc.cca3)),
      independenceDate: str(independence.get(rc.cca3)),
      lifeExpectancy: num(lifeExp.get(rc.cca3)),
      avgTemperature: num(avgTemp.get(rc.cca3)),
      elevation: num(elevation.get(rc.cca3)),
      altSpellings: rc.altSpellings ?? [],
      nativeNames: rc.name.nativeName ?? {},
      cities: (citiesByCountry.get(rc.cca3) ?? []).map((city) => ({ name: city.name, population: city.population, isCapital: city.isCapital })),
      ranks: { population: popRank.get(rc.cca3)!, area: areaRank.get(rc.cca3)!, density: densityRank.get(rc.cca3) ?? null, total: sovereign.length },
      regionPeers: peersByRegion.get(rc.region) ?? [],
      hero: k.hero ?? null,
      destinations: k.destinations ?? [],
      inventions: k.inventions ?? [],
      foods: k.foods ?? [],
      festivals: k.festivals ?? [],
      curatedTimeline: k.timeline ?? [],
      continentHistory,
    };
  });
  console.log(`  ${curatedCount} countries have curated destinations/timelines`);

  /* 9 ── Emit static geodata */
  console.log("→ writing static geodata to /public/data");
  await writeFile(path.join(PUBLIC_DATA, "world.geojson"), JSON.stringify({ type: "FeatureCollection", features: worldFeatures }));
  for (const rc of sovereign) {
    const slug = slugify(rc.name.common);
    const shape = shapes.get(rc.cca3);
    if (shape) await writeFile(path.join(PUBLIC_DATA, "countries", `${slug}.json`), JSON.stringify({ type: "FeatureCollection", features: [shape] }));
    const admin = admin1ByCountry.get(rc.cca3);
    if (admin?.length) await writeFile(path.join(PUBLIC_DATA, "countries", `${slug}.admin1.json`), JSON.stringify({ type: "FeatureCollection", features: admin }));
  }

  /* 10 ── Flag SVGs */
  console.log("→ copying flag SVGs");
  let flagCount = 0;
  for (const rc of sovereign) {
    const cca2 = rc.cca2 === "XK" || rc.cca3 === "UNK" ? "XK" : rc.cca2;
    const src = path.join(process.cwd(), "node_modules", "country-flag-icons", "3x2", `${cca2}.svg`);
    if (existsSync(src)) {
      await copyFile(src, path.join(PUBLIC_FLAGS, `${rc.cca2.toLowerCase()}.svg`));
      flagCount++;
    }
  }
  console.log(`  ${flagCount} flags copied`);

  /* 11 ── Load database */
  console.log("→ loading database");
  await prisma.section.deleteMany();
  await prisma.city.deleteMany();
  await prisma.country.deleteMany();

  for (const r of records) {
    const rc = byCca3.get(r.cca3)!;
    const shape = shapes.get(r.cca3);
    const geometry: Geometry | null = shape?.geometry ?? null;
    const bbox = geometry ? bboxOf(geometry) : null;
    const lp = geometry ? labelPoint(geometry) : null;
    const worldFeature = worldFeatures.find((f) => (f.properties as { cca3: string }).cca3 === r.cca3);
    const wfProps = worldFeature?.properties as { labelLat?: number; labelLng?: number } | undefined;

    const searchText = [r.name, r.officialName, ...r.altSpellings, ...r.capital, r.region, r.subregion ?? "", r.cca2, r.cca3]
      .join(" ")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();

    const sections = generateSections(r);
    const cityRows = citiesByCountry.get(r.cca3) ?? [];
    const gallery = [
      ...(r.hero ? [{ src: commons(r.hero, 1200), alt: r.name, caption: r.name }] : []),
      ...r.destinations.filter((d) => d.image).map((d) => ({ src: commons(d.image!, 1000), alt: d.name, caption: d.name })),
    ];

    await prisma.country.create({
      data: {
        slug: r.slug,
        cca2: r.cca2,
        cca3: r.cca3,
        ccn3: rc.ccn3 ?? null,
        name: r.name,
        officialName: r.officialName,
        nativeNames: JSON.stringify(r.nativeNames),
        altSpellings: JSON.stringify(r.altSpellings),
        capital: JSON.stringify(r.capital),
        capitalLat: rc.capitalInfo?.latlng?.[0] ?? null,
        capitalLng: rc.capitalInfo?.latlng?.[1] ?? null,
        region: r.region,
        subregion: r.subregion,
        continents: JSON.stringify(r.continents),
        population: r.population,
        area: r.area,
        populationDensity: r.populationDensity,
        latitude: r.latitude,
        longitude: r.longitude,
        labelLat: wfProps?.labelLat ?? lp?.[1] ?? r.latitude,
        labelLng: wfProps?.labelLng ?? lp?.[0] ?? r.longitude,
        bbox: bbox ? JSON.stringify(bbox) : null,
        landlocked: r.landlocked,
        borders: JSON.stringify(rc.borders ?? []),
        languages: JSON.stringify(r.languages),
        currencies: JSON.stringify(r.currencies),
        timezones: JSON.stringify(r.timezones),
        tld: JSON.stringify(r.tld),
        callingCodes: JSON.stringify(r.callingCodes),
        demonyms: r.demonyms ? JSON.stringify(r.demonyms) : null,
        flagEmoji: r.flagEmoji,
        coatOfArmsUrl: r.coatOfArmsUrl,
        unMember: r.unMember,
        independent: r.independent,
        status: r.status,
        gini: r.gini ? JSON.stringify(r.gini) : null,
        carSide: r.carSide,
        startOfWeek: r.startOfWeek,
        fifa: r.fifa,
        maps: r.maps ? JSON.stringify(r.maps) : null,
        governmentType: r.governmentType,
        religion: r.religion,
        nationalDish: r.nationalDish,
        nationalSymbol: r.nationalSymbol,
        independenceDate: r.independenceDate,
        lifeExpectancy: r.lifeExpectancy,
        avgTemperature: r.avgTemperature,
        elevation: r.elevation,
        summaryText: null,
        destinations: JSON.stringify(r.destinations),
        inventions: JSON.stringify(r.inventions),
        foods: JSON.stringify(r.foods),
        festivals: JSON.stringify(r.festivals),
        timeline: JSON.stringify(r.curatedTimeline),
        gallery: JSON.stringify(gallery),
        heroImage: r.hero ? commons(r.hero, 1600) : null,
        searchText,
        cities: { create: cityRows.map((city) => ({ name: city.name, lat: city.lat, lng: city.lng, population: city.population, isCapital: city.isCapital, rank: city.rank })) },
        sections: { create: sections.map((s) => ({ key: s.key, title: s.title, order: s.order, blocks: JSON.stringify(s.blocks) })) },
      },
    });
  }

  /* 12 ── Static index for offline/search bootstrapping */
  const index = records
    .map((r) => ({
      slug: r.slug, name: r.name, officialName: r.officialName, cca2: r.cca2, cca3: r.cca3,
      flagEmoji: r.flagEmoji, region: r.region, subregion: r.subregion, capital: r.capital,
      population: r.population, area: r.area, latitude: r.latitude, longitude: r.longitude,
      altSpellings: r.altSpellings.slice(0, 6), unMember: r.unMember,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
  await writeFile(path.join(PUBLIC_DATA, "countries-index.json"), JSON.stringify(index));

  const counts = { countries: await prisma.country.count(), cities: await prisma.city.count(), sections: await prisma.section.count() };
  console.log(`\n✔ done in ${((Date.now() - t0) / 1000).toFixed(1)}s — ${counts.countries} countries, ${counts.cities} cities, ${counts.sections} sections`);
}

main()
  .catch((err) => {
    console.error("\n✖ pipeline failed:", err);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
