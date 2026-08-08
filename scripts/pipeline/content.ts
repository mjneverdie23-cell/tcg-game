/**
 * Section content generator.
 *
 * Composes the 29 encyclopedia sections for a country from normalized open
 * data plus the curated knowledge base (scripts/pipeline/knowledge.ts).
 * Curated destinations/inventions/foods/festivals/timelines are rendered when
 * present; otherwise sections fall back to data-derived, non-fabricated content
 * with authoritative outbound links.
 */

import type {
  ContentBlock,
  StatItem,
  TimelineEvent,
  LinkItem,
  FactCard,
  ChartDatum,
  FeatureCard,
  GalleryImage,
} from "../../src/lib/types";
import { formatArea, formatCompact, formatCoords, formatDensity, formatNumber, joinNatural } from "../../src/lib/format";
import { SECTION_DEFS } from "../../src/lib/sections";
import {
  commons,
  type Destination,
  type Invention,
  type Food,
  type Festival,
  type TimelineItem,
} from "./knowledge";

export type NeighborRef = { name: string; slug: string; flagEmoji: string; population: number; area: number };

export type CountryRecord = {
  slug: string;
  name: string;
  officialName: string;
  cca2: string;
  cca3: string;
  region: string;
  subregion: string | null;
  continents: string[];
  capital: string[];
  population: number;
  area: number;
  populationDensity: number | null;
  latitude: number;
  longitude: number;
  landlocked: boolean;
  neighbors: NeighborRef[];
  languages: Record<string, string>;
  currencies: Record<string, { name: string; symbol?: string }>;
  timezones: string[];
  tld: string[];
  callingCodes: string[];
  demonyms: { eng?: { m: string; f: string } } | null;
  flagEmoji: string;
  coatOfArmsUrl: string | null;
  unMember: boolean;
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
  altSpellings: string[];
  nativeNames: Record<string, { official: string; common: string }>;
  cities: { name: string; population: number | null; isCapital: boolean }[];
  ranks: { population: number; area: number; density: number | null; total: number };
  regionPeers: { name: string; population: number; area: number }[];
  // Curated knowledge
  hero: string | null;
  destinations: Destination[];
  inventions: Invention[];
  foods: Food[];
  festivals: Festival[];
  curatedTimeline: TimelineItem[];
  continentHistory: TimelineItem[];
};

const ordinal = (n: number): string => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

function wikiLink(c: CountryRecord, topic?: string): string {
  const title = topic ? `${topic} of ${c.name}` : c.name;
  return `https://en.wikipedia.org/wiki/${encodeURIComponent(title.replace(/ /g, "_"))}`;
}
function factbookLink(c: CountryRecord): string {
  const slug = c.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `https://www.cia.gov/the-world-factbook/countries/${slug}/`;
}
function britannicaLink(c: CountryRecord): string {
  return `https://www.britannica.com/place/${encodeURIComponent(c.name.replace(/ /g, "-"))}`;
}
function readMore(c: CountryRecord, topic: string, extra: LinkItem[] = []): ContentBlock {
  return {
    type: "links",
    title: "Learn more",
    items: [
      { label: `${topic} of ${c.name} — Wikipedia`, href: wikiLink(c, topic), source: "Wikipedia" },
      { label: `${c.name} — CIA World Factbook`, href: factbookLink(c), source: "CIA World Factbook" },
      ...extra,
    ],
  };
}

const demonym = (c: CountryRecord): string | null => c.demonyms?.eng?.m ?? null;
const languageList = (c: CountryRecord): string[] => Object.values(c.languages);
const currencyList = (c: CountryRecord): string[] =>
  Object.entries(c.currencies).map(([code, cur]) => `${cur.name} (${code}${cur.symbol ? `, ${cur.symbol}` : ""})`);

/** Curated timeline items → renderable timeline events. */
function toEvents(items: TimelineItem[]): TimelineEvent[] {
  return items.map((t) => ({ when: t.when, era: t.era, title: t.title, description: t.description }));
}

/* ────────────────────────── individual sections ───────────────────────── */

function overview(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const caps = c.capital.length ? joinNatural(c.capital) : null;
  const langs = languageList(c);

  if (c.hero) {
    blocks.push({
      type: "gallery",
      images: [{ src: commons(c.hero, 1400), alt: `${c.name}`, caption: `${c.flagEmoji} ${c.name}`, credit: "Wikimedia Commons" }],
    });
  }

  const intro: string[] = [];
  intro.push(
    `**${c.name}** (officially the *${c.officialName}*) is a ${c.landlocked ? "landlocked " : ""}country in **${c.subregion ?? c.region}**${
      caps ? `, with ${c.capital.length > 1 ? "capitals at" : "its capital at"} **${caps}**` : ""
    }.`,
  );
  intro.push(
    `It covers **${formatArea(c.area)}** and is home to about **${formatCompact(c.population)} people**, making it the ${ordinal(c.ranks.population)} most populous and ${ordinal(c.ranks.area)} largest of the ${c.ranks.total} countries in this atlas.`,
  );
  if (langs.length) intro.push(`${langs.length > 1 ? "Languages spoken include" : "The national language is"} ${joinNatural(langs)}.`);
  blocks.push({ type: "prose", markdown: intro.join(" ") });

  const stats: StatItem[] = [
    { label: "Capital", value: caps ?? "—" },
    { label: "Population", value: formatNumber(c.population), hint: `${ordinal(c.ranks.population)} in the world` },
    { label: "Area", value: formatArea(c.area), hint: `${ordinal(c.ranks.area)} in the world` },
    { label: "Region", value: c.subregion ?? c.region },
    { label: "Languages", value: langs.length ? langs.slice(0, 3).join(", ") + (langs.length > 3 ? "…" : "") : "—" },
    { label: "Currency", value: Object.values(c.currencies)[0]?.name ?? "—" },
    { label: "UN member", value: c.unMember ? "Yes" : "No" },
    { label: "Demonym", value: demonym(c) ?? "—" },
  ];
  blocks.push({ type: "stats", items: stats });

  if (c.neighbors.length) {
    blocks.push({
      type: "prose",
      markdown: `${c.name} shares land borders with ${joinNatural(c.neighbors.map((n) => `[${n.flagEmoji} ${n.name}](/country/${n.slug})`))}.`,
    });
  } else {
    blocks.push({
      type: "prose",
      markdown: `${c.name} has no land borders — ${c.landlocked ? "an enclave state" : "it is surrounded entirely by sea"}.`,
    });
  }

  blocks.push(readMore(c, "Overview", [{ label: `${c.name} — Britannica`, href: britannicaLink(c), source: "Britannica" }]));
  return blocks;
}

function history(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const parts: string[] = [];
  if (c.independenceDate) parts.push(`${c.name} marks its independence on **${c.independenceDate}**.`);
  parts.push(
    c.unMember
      ? `Today it is a sovereign state and a member of the United Nations.`
      : `Its current status is recorded as “${c.status.replace(/-/g, " ")}”${c.independent ? ", an independent state" : ""}.`,
  );
  blocks.push({ type: "prose", markdown: parts.join(" ") });

  // Curated national timeline (BCE/CE) when available.
  if (c.curatedTimeline.length) {
    blocks.push({ type: "prose", markdown: `**Key moments in the history of ${c.name}:**` });
    blocks.push({ type: "timeline", events: toEvents(c.curatedTimeline) });
  }

  // Broader continental story (ancient civilizations → modern era).
  if (c.continentHistory.length) {
    const cont = c.continents[0] ?? c.region;
    blocks.push({ type: "prose", markdown: `**${c.name} in the wider history of ${cont}:**` });
    blocks.push({ type: "timeline", events: toEvents(c.continentHistory) });
  }

  if (!c.curatedTimeline.length) {
    const events: TimelineEvent[] = [];
    if (c.independenceDate) {
      const year = c.independenceDate.match(/\d{4}/)?.[0] ?? c.independenceDate;
      events.push({ when: year, era: "CE", title: "Independence", description: `National independence date: ${c.independenceDate}.` });
    }
    if (c.unMember) events.push({ when: "—", era: "CE", title: "United Nations membership", description: `${c.name} is one of the UN member states.` });
    if (events.length) blocks.push({ type: "timeline", events });
  }

  blocks.push(readMore(c, "History"));
  return blocks;
}

function geography(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const parts: string[] = [];
  parts.push(
    `${c.name} lies in **${c.subregion ?? c.region}** on the continent${c.continents.length > 1 ? "s" : ""} of **${joinNatural(c.continents)}**, centred near ${formatCoords(c.latitude, c.longitude)}.`,
  );
  parts.push(
    `Its territory spans **${formatArea(c.area)}** — the ${ordinal(c.ranks.area)} largest in the world — ${
      c.landlocked ? "and is **landlocked**, with no direct access to the open sea." : "with a coastline on the open sea."
    }`,
  );
  if (c.elevation != null) parts.push(`The country's mean elevation is about **${formatNumber(Math.round(c.elevation))} m** above sea level.`);
  blocks.push({ type: "prose", markdown: parts.join(" ") });

  blocks.push({
    type: "stats",
    items: [
      { label: "Total area", value: formatArea(c.area) },
      { label: "Coordinates", value: formatCoords(c.latitude, c.longitude) },
      { label: "Mean elevation", value: c.elevation != null ? `${formatNumber(Math.round(c.elevation))} m` : "—" },
      { label: "Landlocked", value: c.landlocked ? "Yes" : "No" },
      { label: "Land borders", value: String(c.neighbors.length) },
      { label: "Continent", value: joinNatural(c.continents) || c.region },
    ],
  });

  if (c.neighbors.length) {
    blocks.push({
      type: "table",
      caption: "Neighboring countries",
      headers: ["Country", "Population", "Area"],
      rows: c.neighbors.map((n) => [`[${n.flagEmoji} ${n.name}](/country/${n.slug})`, formatNumber(n.population), formatArea(n.area)]),
    });
    const chartData: ChartDatum[] = [
      { name: c.name, value: Math.round(c.area) },
      ...c.neighbors.slice(0, 7).map((n) => ({ name: n.name, value: Math.round(n.area) })),
    ];
    blocks.push({ type: "chart", chart: "bar", title: "Land area vs. neighboring countries", unit: "km²", data: chartData, note: "Source: REST Countries / Natural Earth" });
  }

  blocks.push(readMore(c, "Geography"));
  return blocks;
}

function politics(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const parts: string[] = [];
  if (c.governmentType) parts.push(`${c.name} is governed as a **${c.governmentType.toLowerCase()}**.`);
  parts.push(
    c.unMember
      ? `It is a full member of the **United Nations** and participates in international bodies under the ISO code **${c.cca3}**.`
      : `It is not a UN member state; its international status is recorded as “${c.status.replace(/-/g, " ")}”.`,
  );
  if (c.capital.length) parts.push(`Political institutions are seated in **${joinNatural(c.capital)}**.`);
  blocks.push({ type: "prose", markdown: parts.join(" ") });
  blocks.push({
    type: "facts",
    cards: [
      { title: "Form of government", body: c.governmentType ?? "See references for current details.", icon: "Scale" },
      { title: "Sovereignty", body: c.independent ? "Independent sovereign state" : `Status: ${c.status.replace(/-/g, " ")}`, icon: "Flag" },
      { title: "UN membership", body: c.unMember ? "Member of the United Nations" : "Not a UN member", icon: "Globe2" },
    ],
  });
  blocks.push(readMore(c, "Politics"));
  return blocks;
}

function government(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  blocks.push({
    type: "prose",
    markdown: [
      c.governmentType ? `The state is organised as a **${c.governmentType.toLowerCase()}**.` : `Details of ${c.name}'s constitutional structure are maintained in the references below.`,
      c.capital.length ? `The seat of government is **${joinNatural(c.capital)}**.` : "",
      `Administrative boundaries of ${c.name}'s first-level divisions are drawn on the map alongside this page.`,
    ].filter(Boolean).join(" "),
  });
  blocks.push({
    type: "stats",
    items: [
      { label: "Government type", value: c.governmentType ?? "—" },
      { label: "Capital", value: c.capital.length ? joinNatural(c.capital) : "—" },
      { label: "Driving side", value: c.carSide ? c.carSide[0].toUpperCase() + c.carSide.slice(1) : "—" },
      { label: "Week starts on", value: c.startOfWeek ? c.startOfWeek[0].toUpperCase() + c.startOfWeek.slice(1) : "—" },
      { label: "Internet TLD", value: c.tld.join(", ") || "—" },
      { label: "Calling code", value: c.callingCodes.join(", ") || "—" },
    ],
  });
  blocks.push(readMore(c, "Government"));
  return blocks;
}

function economy(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const curs = currencyList(c);
  const parts: string[] = [];
  if (curs.length) parts.push(`The official currency of ${c.name} is the **${curs[0]}**${curs.length > 1 ? `, alongside ${joinNatural(curs.slice(1))}` : ""}.`);
  const giniEntries = c.gini ? Object.entries(c.gini) : [];
  if (giniEntries.length) {
    const [year, value] = giniEntries[giniEntries.length - 1];
    parts.push(`The most recent **Gini index** on record is **${value}** (${year}) — lower values indicate a more equal income distribution.`);
  }
  parts.push(`With ${formatCompact(c.population)} inhabitants across ${formatArea(c.area)}, ${c.name} ranks ${ordinal(c.ranks.population)} in population worldwide, a key driver of its market size.`);
  blocks.push({ type: "prose", markdown: parts.join(" ") });
  blocks.push({
    type: "stats",
    items: [
      { label: "Currency", value: curs[0] ?? "—" },
      { label: "Gini index", value: giniEntries.length ? `${giniEntries[giniEntries.length - 1][1]} (${giniEntries[giniEntries.length - 1][0]})` : "—" },
      { label: "Population (market size)", value: formatCompact(c.population) },
      { label: "Internet TLD", value: c.tld.join(", ") || "—" },
    ],
  });
  blocks.push(readMore(c, "Economy", [{ label: `${c.name} — World Bank data`, href: `https://data.worldbank.org/country/${c.cca3}`, source: "World Bank" }]));
  return blocks;
}

function culture(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const langs = languageList(c);
  const parts: string[] = [];
  parts.push(
    `${c.name}'s culture is shaped by its place in ${c.subregion ?? c.region}${
      langs.length ? ` and expressed through ${langs.length > 1 ? `its ${langs.length} languages — ${joinNatural(langs)}` : `the ${langs[0]} language`}` : ""
    }.`,
  );
  if (c.religion) parts.push(`The predominant religious tradition is **${c.religion}**.`);
  if (c.nationalDish) parts.push(`Its celebrated national dish is **${c.nationalDish}**.`);
  if (demonym(c)) parts.push(`The people of ${c.name} are known as **${demonym(c)}s**.`);
  blocks.push({ type: "prose", markdown: parts.join(" ") });

  const cards: FactCard[] = [];
  if (c.nationalDish) cards.push({ title: "National dish", body: c.nationalDish, icon: "UtensilsCrossed" });
  if (c.religion) cards.push({ title: "Main religion", body: c.religion, icon: "Church" });
  if (c.nationalSymbol) cards.push({ title: "National symbol", body: c.nationalSymbol, icon: "Star" });
  if (langs.length) cards.push({ title: "Languages", body: joinNatural(langs), icon: "MessageSquare" });
  if (cards.length) blocks.push({ type: "facts", cards });

  if (c.festivals.length) {
    blocks.push({ type: "prose", markdown: `**Cultural celebrations** include ${joinNatural(c.festivals.slice(0, 3).map((f) => `**${f.name}**`))}. See the Holidays & Festivals tab for details.` });
  }
  blocks.push(readMore(c, "Culture"));
  return blocks;
}

function religion(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: c.religion
        ? `The most widely followed religion in ${c.name} is **${c.religion}**. Religious practice varies across regions and communities; the references below track current demographic surveys.`
        : `Reliable open data on religious demographics for ${c.name} is not bundled in this atlas — the references below lead to current surveys.`,
    },
    readMore(c, "Religion", [{ label: `Religion in ${c.name} — Pew Research`, href: `https://www.pewresearch.org/?s=${encodeURIComponent(c.name + " religion")}`, source: "Pew Research" }]),
  ];
}

function languagesSection(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const entries = Object.entries(c.languages);
  if (entries.length) {
    blocks.push({
      type: "prose",
      markdown: `${c.name} has ${entries.length === 1 ? "one official or national language" : `**${entries.length}** recognised languages`}: ${joinNatural(entries.map(([, l]) => `**${l}**`))}.`,
    });
    blocks.push({ type: "table", caption: "Recognised languages", headers: ["ISO 639-3", "Language"], rows: entries.map(([code, lang]) => [code, lang]) });
  } else {
    blocks.push({ type: "prose", markdown: `No language entries are recorded for ${c.name} in the bundled dataset — see the references for linguistic surveys.` });
  }
  const native = Object.entries(c.nativeNames);
  if (native.length) {
    blocks.push({
      type: "table",
      caption: "The country's name in its own languages",
      headers: ["Language", "Common name", "Official name"],
      rows: native.map(([code, n]) => [c.languages[code] ?? code, n.common, n.official]),
    });
  }
  blocks.push(readMore(c, "Languages", [{ label: `Languages of ${c.name} — Ethnologue`, href: `https://www.ethnologue.com/country/${c.cca2}/`, source: "Ethnologue" }]));
  return blocks;
}

function population(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const parts: string[] = [];
  parts.push(`${c.name} has a population of **${formatNumber(c.population)}**, the ${ordinal(c.ranks.population)} largest in the world.`);
  if (c.populationDensity != null) parts.push(`Average density is **${formatDensity(c.populationDensity)}**.`);
  if (c.lifeExpectancy != null) parts.push(`Life expectancy at birth is about **${c.lifeExpectancy.toFixed(1)} years**.`);
  blocks.push({ type: "prose", markdown: parts.join(" ") });
  blocks.push({
    type: "stats",
    items: [
      { label: "Population", value: formatNumber(c.population) },
      { label: "Density", value: formatDensity(c.populationDensity) },
      { label: "Life expectancy", value: c.lifeExpectancy != null ? `${c.lifeExpectancy.toFixed(1)} yrs` : "—" },
      { label: "World rank", value: ordinal(c.ranks.population) },
    ],
  });
  if (c.regionPeers.length > 1) {
    blocks.push({
      type: "chart",
      chart: "bar",
      title: `Most populous countries in ${c.region}`,
      unit: "people",
      data: c.regionPeers.slice(0, 8).map((p) => ({ name: p.name, value: p.population })),
      note: "Source: REST Countries",
    });
  }
  const topCities = c.cities.filter((x) => x.population).slice(0, 10);
  if (topCities.length >= 3) {
    blocks.push({
      type: "table",
      caption: "Major cities (Natural Earth populated places)",
      headers: ["City", "Population (est.)", ""],
      rows: topCities.map((city) => [city.name, formatNumber(city.population), city.isCapital ? "★ Capital" : ""]),
    });
  }
  blocks.push(readMore(c, "Demographics"));
  return blocks;
}

function education(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: `Education systems change quickly, so this atlas links to live statistical sources rather than baking in numbers that go stale. ${
        languageList(c).length ? `Instruction in ${c.name} is primarily delivered in ${joinNatural(languageList(c).slice(0, 3))}.` : ""
      }`,
    },
    {
      type: "links",
      title: "Authoritative education data",
      items: [
        { label: `${c.name} — UNESCO Institute for Statistics`, href: `https://uis.unesco.org/en/country/${c.cca2.toLowerCase()}`, source: "UNESCO" },
        { label: `Education in ${c.name} — Wikipedia`, href: wikiLink(c, "Education"), source: "Wikipedia" },
        { label: `${c.name} — World Bank education indicators`, href: `https://data.worldbank.org/country/${c.cca3}`, source: "World Bank" },
      ],
    },
  ];
}

function military(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: `${c.name}${c.unMember ? ", as a UN member state," : ""} maintains its defence arrangements under the government seated in ${c.capital[0] ?? "its capital"}. Force structure and spending figures shift year to year; consult the sources below for current, audited numbers.`,
    },
    {
      type: "links",
      title: "Defence data sources",
      items: [
        { label: `Military of ${c.name} — Wikipedia`, href: wikiLink(c, "Military"), source: "Wikipedia" },
        { label: "SIPRI Military Expenditure Database", href: "https://www.sipri.org/databases/milex", source: "SIPRI" },
        { label: `${c.name} — CIA World Factbook (Military and Security)`, href: factbookLink(c), source: "CIA World Factbook" },
      ],
    },
  ];
}

function tourism(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  blocks.push({
    type: "prose",
    markdown: `Planning a visit? ${c.name} uses the **${Object.values(c.currencies)[0]?.name ?? "local currency"}**, drives on the **${c.carSide ?? "—"}**, and observes ${
      c.timezones.length > 1 ? `${c.timezones.length} time zones (${c.timezones[0]}…)` : `the ${c.timezones[0] ?? "local"} time zone`
    }.${c.avgTemperature != null ? ` The yearly average temperature is about **${c.avgTemperature.toFixed(1)} °C**.` : ""}`,
  });

  if (c.destinations.length) {
    blocks.push({
      type: "feature-cards",
      title: "Famous destinations",
      cards: c.destinations.map<FeatureCard>((d) => ({ name: d.name, blurb: d.blurb, image: d.image ? commons(d.image, 900) : undefined })),
    });
  } else {
    // Fallback: use the capital and major cities we actually have from data.
    const cards: FeatureCard[] = [];
    if (c.capital.length) cards.push({ name: joinNatural(c.capital), blurb: `The capital ${c.capital.length > 1 ? "cities are" : "city is"} the usual gateway for visitors.` });
    for (const city of c.cities.filter((x) => !x.isCapital).slice(0, 4)) {
      cards.push({ name: city.name, blurb: city.population ? `Major city, ~${formatCompact(city.population)} inhabitants.` : "A major population centre." });
    }
    if (cards.length) blocks.push({ type: "feature-cards", title: "Places to visit", cards });
  }

  blocks.push(
    readMore(c, "Tourism", [{ label: `${c.name} — Wikivoyage travel guide`, href: `https://en.wikivoyage.org/wiki/${encodeURIComponent(c.name.replace(/ /g, "_"))}`, source: "Wikivoyage" }]),
  );
  return blocks;
}

function cuisine(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  blocks.push({
    type: "prose",
    markdown: c.nationalDish
      ? `The signature dish of ${c.name} is **${c.nationalDish}**. Regional kitchens build on local staples and the food cultures of ${c.subregion ?? c.region}.`
      : `${c.name}'s food tradition draws on the wider cuisine of ${c.subregion ?? c.region}.`,
  });
  if (c.foods.length) {
    blocks.push({
      type: "feature-cards",
      title: "Signature foods",
      cards: c.foods.map<FeatureCard>((f) => ({ name: f.name, blurb: f.blurb, image: f.image ? commons(f.image, 800) : undefined })),
    });
  } else if (c.nationalDish) {
    blocks.push({ type: "facts", cards: [{ title: "National dish", body: c.nationalDish, icon: "UtensilsCrossed" }] });
  }
  blocks.push(readMore(c, "Cuisine"));
  return blocks;
}

function wildlife(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: `${c.nationalSymbol ? `${c.name}'s national symbol is the **${c.nationalSymbol}**. ` : ""}Its ecosystems span the ${joinNatural(c.continents) || c.region} biogeographic realm${
        c.landlocked ? " (entirely inland habitats)" : ", including coastal and marine habitats"
      }. Explore the live biodiversity records below for verified species data.`,
    },
    {
      type: "links",
      title: "Biodiversity data",
      items: [
        { label: `${c.name} — GBIF occurrence records`, href: `https://www.gbif.org/country/${c.cca2}/summary`, source: "GBIF" },
        { label: `Wildlife of ${c.name} — Wikipedia`, href: wikiLink(c, "Wildlife"), source: "Wikipedia" },
        { label: "IUCN Red List", href: "https://www.iucnredlist.org/", source: "IUCN" },
      ],
    },
  ];
}

function climate(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const lat = Math.abs(c.latitude);
  const band = lat < 23.5 ? "tropical" : lat < 35 ? "subtropical" : lat < 55 ? "temperate" : lat < 66.5 ? "cold-temperate" : "polar";
  blocks.push({
    type: "prose",
    markdown: `Centred at ${formatCoords(c.latitude, c.longitude)}, ${c.name} lies mainly in the **${band}** latitude band.${
      c.avgTemperature != null ? ` Its yearly average temperature is **${c.avgTemperature.toFixed(1)} °C**.` : ""
    }${c.elevation != null ? ` Mean elevation of about ${formatNumber(Math.round(c.elevation))} m also shapes local climates.` : ""}`,
  });
  blocks.push({
    type: "stats",
    items: [
      { label: "Latitude band", value: band[0].toUpperCase() + band.slice(1) },
      { label: "Avg. yearly temperature", value: c.avgTemperature != null ? `${c.avgTemperature.toFixed(1)} °C` : "—" },
      { label: "Mean elevation", value: c.elevation != null ? `${formatNumber(Math.round(c.elevation))} m` : "—" },
      { label: "Time zones", value: String(c.timezones.length) },
    ],
  });
  blocks.push(readMore(c, "Climate", [{ label: `${c.name} — World Bank Climate Knowledge Portal`, href: `https://climateknowledgeportal.worldbank.org/country/${c.cca3.toLowerCase()}`, source: "World Bank" }]));
  return blocks;
}

function infrastructure(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: `${c.name} drives on the **${c.carSide ?? "—"}** side of the road and uses the **${c.tld.join(", ") || "—"}** internet domain with calling code${c.callingCodes.length > 1 ? "s" : ""} **${c.callingCodes.join(", ") || "—"}**. The country spans ${c.timezones.length} time zone${c.timezones.length > 1 ? "s" : ""}: ${c.timezones.join(", ")}. Roads, railways and utility networks are drawn live on the OpenStreetMap layer of the country map.`,
    },
    {
      type: "stats",
      items: [
        { label: "Driving side", value: c.carSide ? c.carSide[0].toUpperCase() + c.carSide.slice(1) : "—" },
        { label: "Internet TLD", value: c.tld.join(", ") || "—" },
        { label: "Calling code", value: c.callingCodes.join(", ") || "—" },
        { label: "Time zones", value: c.timezones.join(", ") },
      ],
    },
    {
      type: "links",
      title: "Live infrastructure maps",
      items: [
        { label: `${c.name} on OpenStreetMap`, href: c.maps?.openStreetMaps ?? `https://www.openstreetmap.org/search?query=${encodeURIComponent(c.name)}`, source: "OpenStreetMap" },
        { label: `Transport in ${c.name} — Wikipedia`, href: wikiLink(c, "Transport"), source: "Wikipedia" },
      ],
    },
  ];
}

function famousPeople(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: `${demonym(c) ? `Notable **${demonym(c)}s**` : `Notable people from ${c.name}`} span science, politics, arts and sport. Rather than freeze a subjective list into the database, this atlas links to continuously curated biographical indexes.`,
    },
    {
      type: "links",
      title: "Curated biographical indexes",
      items: [
        { label: `People from ${c.name} — Wikipedia category`, href: `https://en.wikipedia.org/wiki/Category:${encodeURIComponent(`People from ${c.name}`.replace(/ /g, "_"))}`, source: "Wikipedia" },
        { label: `${c.name} Nobel laureates — NobelPrize.org`, href: `https://www.nobelprize.org/search/?s=${encodeURIComponent(c.name)}`, source: "Nobel Foundation" },
        { label: `${c.name} — Britannica biographies`, href: britannicaLink(c), source: "Britannica" },
      ],
    },
  ];
}

function inventions(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  if (c.inventions.length) {
    blocks.push({ type: "prose", markdown: `${c.name} has given the world a number of notable inventions and discoveries:` });
    blocks.push({
      type: "feature-cards",
      title: "Inventions & discoveries",
      cards: c.inventions.map<FeatureCard>((i) => ({ name: i.name, blurb: i.blurb, meta: i.year })),
    });
  } else {
    blocks.push({
      type: "prose",
      markdown: `Innovation records for ${c.name} — patents, landmark inventions and scientific firsts — are maintained by the global patent system and encyclopedic sources linked here.`,
    });
  }
  blocks.push({
    type: "links",
    title: "Innovation records",
    items: [
      { label: `Inventions & discoveries in ${c.name} — Wikipedia`, href: `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(`inventions ${c.name}`)}`, source: "Wikipedia" },
      { label: "WIPO country statistics", href: `https://www.wipo.int/ipstats/en/statistics/country_profile/profile.jsp?code=${c.cca2}`, source: "WIPO" },
    ],
  });
  return blocks;
}

function scienceTechnology(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: `${c.name} participates in the global research system under the ISO code **${c.cca3}**; its universities and institutes publish under the **${c.tld[0] ?? "national"}** domain. Live bibliometrics and R&D indicators are tracked by the sources below.`,
    },
    {
      type: "links",
      title: "Research & technology indicators",
      items: [
        { label: `Science and technology in ${c.name} — Wikipedia`, href: wikiLink(c, "Science and technology"), source: "Wikipedia" },
        { label: `${c.name} — UNESCO science report`, href: "https://www.unesco.org/reports/science/2021/en", source: "UNESCO" },
        { label: `${c.name} — World Bank R&D indicators`, href: `https://data.worldbank.org/country/${c.cca3}`, source: "World Bank" },
      ],
    },
  ];
}

function sports(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: `${c.name} competes internationally${c.fifa ? ` under the FIFA code **${c.fifa}**` : ""}${c.cca3 ? ` and the IOC-style code **${c.cca3}**` : ""}. National teams and athletes appear in continental championships across ${c.region}.`,
    },
    {
      type: "facts",
      cards: [
        { title: "FIFA code", body: c.fifa ?? "Not affiliated", icon: "Trophy" },
        { title: "Olympic participation", body: `Competes as ${c.cca3} at the Olympic Games.`, icon: "Medal" },
      ],
    },
    readMore(c, "Sport"),
  ];
}

function nationalSymbols(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const cards: FactCard[] = [{ title: "Flag", body: `${c.flagEmoji} The national flag of ${c.name} (shown throughout this atlas).`, icon: "Flag" }];
  if (c.nationalSymbol) cards.push({ title: "National symbol", body: c.nationalSymbol, icon: "Star" });
  if (c.coatOfArmsUrl) cards.push({ title: "Coat of arms", body: "Official heraldic emblem — shown in the photo gallery.", icon: "Shield" });
  if (c.nationalDish) cards.push({ title: "National dish", body: c.nationalDish, icon: "UtensilsCrossed" });
  blocks.push({ type: "prose", markdown: `State symbols distil ${c.name}'s identity: its flag ${c.flagEmoji}${c.nationalSymbol ? `, the ${c.nationalSymbol}` : ""}${c.coatOfArmsUrl ? ", and its coat of arms" : ""}.` });
  blocks.push({ type: "facts", cards });
  blocks.push(readMore(c, "National symbols"));
  return blocks;
}

function holidays(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  if (c.festivals.length) {
    blocks.push({ type: "prose", markdown: `${c.name} celebrates a range of festivals and public holidays through the year:` });
    blocks.push({
      type: "feature-cards",
      title: "Major festivals",
      cards: c.festivals.map<FeatureCard>((f) => ({ name: f.name, blurb: f.blurb, meta: f.when })),
    });
  }
  const rows: string[][] = [];
  if (c.independenceDate) rows.push(["Independence / National Day", c.independenceDate, "National day"]);
  rows.push(["New Year", "1 January", "Widely observed"]);
  blocks.push({
    type: "prose",
    markdown: `${c.independenceDate ? `${c.name}'s national day commemorates independence (**${c.independenceDate}**).` : `${c.name} observes national and religious holidays through the year.`} The week begins on **${c.startOfWeek ? c.startOfWeek[0].toUpperCase() + c.startOfWeek.slice(1) : "Monday"}**.`,
  });
  blocks.push({ type: "table", caption: "Key dates", headers: ["Holiday", "Date", "Note"], rows });
  blocks.push(readMore(c, "Public holidays", [{ label: `Public holidays in ${c.name} — timeanddate.com`, href: `https://www.timeanddate.com/holidays/${c.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}/`, source: "timeanddate" }]));
  return blocks;
}

function currentSituation(c: CountryRecord): ContentBlock[] {
  return [
    {
      type: "prose",
      markdown: `Fast-moving facts — leadership, elections, conflicts, disasters — go stale the day they are written, so this atlas deliberately links to live sources instead of storing them. Baseline verified facts: ${c.name} is ${
        c.unMember ? "a UN member state" : `recorded as “${c.status.replace(/-/g, " ")}”`
      } with ${formatCompact(c.population)} people and its seat of government in ${c.capital[0] ?? "—"}.`,
    },
    {
      type: "links",
      title: "Live coverage",
      items: [
        { label: `${c.name} — Reuters`, href: `https://www.reuters.com/site-search/?query=${encodeURIComponent(c.name)}`, source: "Reuters" },
        { label: `${c.name} — BBC News`, href: `https://www.bbc.co.uk/search?q=${encodeURIComponent(c.name)}`, source: "BBC" },
        { label: `${c.name} — Wikipedia`, href: wikiLink(c), source: "Wikipedia" },
      ],
    },
  ];
}

function internationalRelations(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  blocks.push({
    type: "prose",
    markdown: `${c.name} ${c.unMember ? "is a member of the **United Nations**" : "is not a UN member"}${
      c.neighbors.length ? ` and manages land-border relations with ${joinNatural(c.neighbors.map((n) => `[${n.name}](/country/${n.slug})`))}` : ""
    }. Its diplomatic footprint is catalogued in the sources below.`,
  });
  if (c.neighbors.length) {
    blocks.push({ type: "table", caption: "Bordering states", headers: ["Country", "Region"], rows: c.neighbors.map((n) => [`[${n.flagEmoji} ${n.name}](/country/${n.slug})`, c.region]) });
  }
  blocks.push(readMore(c, "Foreign relations"));
  return blocks;
}

function timeline(c: CountryRecord): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  if (c.curatedTimeline.length) {
    blocks.push({ type: "prose", markdown: `A chronology of ${c.name} from antiquity to the present (BCE = Before Common Era, CE = Common Era).` });
    blocks.push({ type: "timeline", events: toEvents(c.curatedTimeline) });
  } else {
    const events: TimelineEvent[] = [];
    if (c.continentHistory.length) events.push(...toEvents(c.continentHistory));
    if (c.independenceDate) {
      const year = c.independenceDate.match(/\d{4}/)?.[0] ?? c.independenceDate;
      events.push({ when: year, era: "CE", title: "Independence", description: `${c.name} marks its independence on ${c.independenceDate}.` });
    }
    events.push({ when: "Today", era: "CE", title: "Present day", description: `${formatCompact(c.population)} people across ${formatArea(c.area)}; ${c.governmentType ? `governed as a ${c.governmentType.toLowerCase()}` : "see Government section"}.` });
    blocks.push({ type: "prose", markdown: `Key milestones for ${c.name}, set against the history of ${c.continents[0] ?? c.region}.` });
    blocks.push({ type: "timeline", events });
  }
  blocks.push(readMore(c, "History"));
  return blocks;
}

function interestingFacts(c: CountryRecord): ContentBlock[] {
  const cards: FactCard[] = [];
  cards.push({ title: "Name origins", body: `Also known as: ${c.altSpellings.filter((a) => a.length > 3).slice(0, 4).join(" · ") || c.officialName}.`, icon: "BookOpen" });
  if (c.timezones.length > 1) cards.push({ title: `${c.timezones.length} time zones`, body: `From ${c.timezones[0]} to ${c.timezones[c.timezones.length - 1]}.`, icon: "Clock" });
  if (c.landlocked) cards.push({ title: "Landlocked", body: `${c.name} has no coastline — every route to the sea crosses a neighbor.`, icon: "Mountain" });
  if (c.neighbors.length >= 5) cards.push({ title: `${c.neighbors.length} neighbors`, body: `One of the most-bordered countries in ${c.region}.`, icon: "Users" });
  if (c.populationDensity != null && c.populationDensity < 5) cards.push({ title: "Vast and empty", body: `Only ${formatDensity(c.populationDensity)} — among the least dense countries on Earth.`, icon: "Mountain" });
  if (c.populationDensity != null && c.populationDensity > 400) cards.push({ title: "Densely settled", body: `${formatDensity(c.populationDensity)} — among the most densely populated countries.`, icon: "Building2" });
  if (c.nationalDish) cards.push({ title: "Taste of the nation", body: `${c.nationalDish} is the celebrated national dish.`, icon: "UtensilsCrossed" });
  if (c.fifa) cards.push({ title: "On the pitch", body: `Plays international football under the code ${c.fifa}.`, icon: "Trophy" });
  return [
    { type: "prose", markdown: `A handful of details that make ${c.name} distinctive — every one backed by the atlas datasets.` },
    { type: "facts", cards },
  ];
}

function photoGallery(c: CountryRecord): ContentBlock[] {
  const images: GalleryImage[] = [];
  if (c.hero) images.push({ src: commons(c.hero, 1200), alt: c.name, caption: c.name, credit: "Wikimedia Commons" });
  for (const d of c.destinations) {
    if (d.image) images.push({ src: commons(d.image, 1000), alt: d.name, caption: d.name, credit: "Wikimedia Commons" });
  }
  for (const f of c.foods) {
    if (f.image) images.push({ src: commons(f.image, 800), alt: f.name, caption: f.name, credit: "Wikimedia Commons" });
  }
  images.push({ src: `/flags/${c.cca2.toLowerCase()}.svg`, alt: `Flag of ${c.name}`, caption: `Flag of ${c.name}` });
  if (c.coatOfArmsUrl) images.push({ src: c.coatOfArmsUrl, alt: `Coat of arms of ${c.name}`, caption: `Coat of arms of ${c.name}` });

  return [
    { type: "prose", markdown: `Photos of ${c.name}. Images are served from Wikimedia Commons under their respective licenses; any that fail to load are hidden automatically.` },
    { type: "gallery", images },
    {
      type: "links",
      title: "Open photo collections",
      items: [
        { label: `${c.name} — Wikimedia Commons`, href: `https://commons.wikimedia.org/wiki/Category:${encodeURIComponent(c.name.replace(/ /g, "_"))}`, source: "Wikimedia Commons" },
        { label: `${c.name} — Unsplash`, href: `https://unsplash.com/s/photos/${encodeURIComponent(c.name)}`, source: "Unsplash" },
      ],
    },
  ];
}

function references(c: CountryRecord): ContentBlock[] {
  const items: LinkItem[] = [
    { label: `${c.name} — Wikipedia`, href: wikiLink(c), source: "Wikipedia" },
    { label: `${c.name} — CIA World Factbook`, href: factbookLink(c), source: "CIA World Factbook" },
    { label: `${c.name} — Britannica`, href: britannicaLink(c), source: "Britannica" },
    { label: `${c.name} — World Bank`, href: `https://data.worldbank.org/country/${c.cca3}`, source: "World Bank" },
    { label: "REST Countries (facts dataset)", href: "https://restcountries.com/", source: "REST Countries" },
    { label: "mledoze/countries (country data & shapes)", href: "https://github.com/mledoze/countries", source: "GitHub" },
    { label: "Natural Earth (boundaries, cities, rivers, lakes)", href: "https://www.naturalearthdata.com/", source: "Natural Earth" },
    { label: "samayo/country-json (thematic datasets)", href: "https://github.com/samayo/country-json", source: "GitHub" },
    { label: "Wikimedia Commons (photographs)", href: "https://commons.wikimedia.org/", source: "Wikimedia Commons" },
    ...(c.maps?.openStreetMaps ? [{ label: `${c.name} — OpenStreetMap`, href: c.maps.openStreetMaps, source: "OpenStreetMap" }] : []),
    ...(c.maps?.googleMaps ? [{ label: `${c.name} — Google Maps`, href: c.maps.googleMaps, source: "Google Maps" }] : []),
  ];
  return [
    { type: "prose", markdown: `Structured data on this page derives from the open datasets below, normalized by the World Atlas pipeline. Curated descriptions of destinations, inventions, foods, festivals and history were authored for this atlas and are summarised from well-established general knowledge; follow the links for in-depth, citable sources.` },
    { type: "references", items },
  ];
}

/* ─────────────────────────────── registry ─────────────────────────────── */

const GENERATORS: Record<string, (c: CountryRecord) => ContentBlock[]> = {
  overview,
  history,
  geography,
  politics,
  government,
  economy,
  culture,
  religion,
  languages: languagesSection,
  population,
  education,
  military,
  tourism,
  cuisine,
  wildlife,
  climate,
  infrastructure,
  "famous-people": famousPeople,
  inventions,
  "science-technology": scienceTechnology,
  sports,
  "national-symbols": nationalSymbols,
  holidays,
  "current-situation": currentSituation,
  "international-relations": internationalRelations,
  timeline,
  "interesting-facts": interestingFacts,
  "photo-gallery": photoGallery,
  references,
};

export function generateSections(c: CountryRecord): { key: string; title: string; order: number; blocks: ContentBlock[] }[] {
  return SECTION_DEFS.map((def, order) => {
    const gen = GENERATORS[def.key];
    if (!gen) throw new Error(`No generator for section "${def.key}"`);
    return { key: def.key, title: def.title, order, blocks: gen(c) };
  });
}
