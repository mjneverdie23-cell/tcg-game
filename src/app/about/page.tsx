import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About & sources",
  description: "How World Atlas is built, and the open datasets it draws on.",
};

const SOURCES = [
  { name: "REST Countries", href: "https://restcountries.com/", use: "Names, capitals, population, area, languages, currencies, borders, codes." },
  { name: "Natural Earth", href: "https://www.naturalearthdata.com/", use: "Political boundaries, admin-1 divisions, populated places, rivers and lakes." },
  { name: "mledoze/countries", href: "https://github.com/mledoze/countries", use: "Per-country GeoJSON shapes." },
  { name: "samayo/country-json", href: "https://github.com/samayo/country-json", use: "Religion, government type, national dish, independence date, life expectancy, temperature, elevation." },
  { name: "Wikimedia Commons", href: "https://commons.wikimedia.org/", use: "Photographs of destinations and landmarks (loaded client-side under their licenses)." },
  { name: "OpenStreetMap / OpenTopoMap", href: "https://www.openstreetmap.org/copyright", use: "Optional street/road and terrain basemap tiles." },
];

export default function AboutPage() {
  return (
    <div className="container max-w-3xl py-10">
      <h1 className="text-3xl font-bold tracking-tight">About World Atlas</h1>
      <div className="mt-4 space-y-4 leading-relaxed text-foreground/90">
        <p>
          World Atlas is an interactive digital encyclopedia of every sovereign country on Earth — a blend of a Google-Earth-style map and a Britannica-style reference. An automated data pipeline imports open datasets, normalizes them into a local database, and generates 29 encyclopedia sections per country.
        </p>
        <p>
          Curated descriptions of famous destinations, inventions, foods, festivals and a BCE/CE historical timeline (including ancient civilizations such as Sumer, Egypt, Greece and Rome) were authored for this atlas from well-established general knowledge. Every section links out to authoritative sources — Wikipedia, the CIA World Factbook, Britannica and the World Bank — for citable depth.
        </p>
        <h2 className="pt-2 text-xl font-semibold">Data sources</h2>
        <ul className="space-y-2">
          {SOURCES.map((s) => (
            <li key={s.name} className="rounded-lg border bg-card p-3">
              <a href={s.href} target="_blank" rel="noreferrer" className="font-medium text-primary underline underline-offset-2">{s.name}</a>
              <span className="text-muted-foreground"> — {s.use}</span>
            </li>
          ))}
        </ul>
        <h2 className="pt-2 text-xl font-semibold">Accuracy & attribution</h2>
        <p className="text-muted-foreground">
          Boundaries follow Natural Earth&apos;s de-facto representation and imply no endorsement of any territorial claim. Fast-changing topics (current events, statistics) link to live sources rather than storing numbers that go stale. Map tiles are © OpenStreetMap contributors and © OpenTopoMap (CC-BY-SA); photographs are © their respective authors via Wikimedia Commons.
        </p>
      </div>
    </div>
  );
}
