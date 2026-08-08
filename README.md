# World Atlas 🌍

A modern, production-quality interactive **digital encyclopedia of every sovereign
country on Earth** — a blend of Google Earth, National Geographic and Britannica.
Explore a fully interactive world map, then dive into any country's detailed map
and 29 richly formatted encyclopedia sections.

Built with **Next.js 15 (App Router)**, **React 19**, **TypeScript**, **Tailwind
CSS**, **shadcn/ui**, **Framer Motion**, **Leaflet**, **Recharts** and **Prisma**
(SQLite for the demo, PostgreSQL-ready). All data comes from open datasets,
imported and normalized by a repeatable pipeline, and enriched with a curated
knowledge base of destinations, inventions, foods, festivals and history.

---

## Features

**Interactive world map (homepage)**
- Every continent, ocean and sovereign country with accurate Natural Earth
  political boundaries; dependent territories shown as muted fills.
- Flag + English-name labels at each country's *pole of inaccessibility*,
  revealed progressively by zoom and country size.
- Hover effects: region highlight, scale, glow, animated marching-ants outline
  and a rich flag/stat tooltip. Continent filter chips fly to each region.
- Smooth zoom/pan, responsive, full light/dark theming.

**Country pages (`/country/[slug]`)**
- **Left:** a detailed Leaflet map with togglable layers — administrative
  divisions, neighboring countries (clickable), coastlines, major cities &
  capital, rivers, lakes, plus optional OpenStreetMap streets/roads and
  OpenTopoMap terrain/relief (mountains) basemaps.
- **Right:** a tabbed interface with **29 sections** — Overview, History,
  Geography, Politics, Government, Economy, Culture, Religion, Languages,
  Population, Education, Military, Tourism, Cuisine, Wildlife, Climate,
  Infrastructure, Famous People, Inventions, Science & Technology, Sports,
  National Symbols, Holidays & Festivals, Current Situation, International
  Relations, Timeline, Interesting Facts, Photo Gallery and References.
- Rich content blocks: formatted prose, stat grids, tables, **BCE/CE timelines**,
  interactive charts (Recharts + accessible table toggle), expandable fact
  cards, **image feature-cards**, photo galleries, citations and related links.

**Curated encyclopedic content**
- Famous **destinations**, notable **inventions**, signature **foods** and major
  **festivals** authored for a broad set of countries across every continent.
- A **historical timeline in BCE/CE** covering ancient civilizations — Sumer,
  Ancient Egypt, Greece, Rome, the Indus Valley, the Maya, Aztec and Inca, the
  Mali and Ghana empires and more — plus per-continent history.
- **Photographs** from Wikimedia Commons (loaded in the visitor's browser via
  `Special:FilePath`, with graceful fallback for any that don't resolve).

**Discovery & personalization**
- Global ⌘K search with debounced autocomplete + offline fallback.
- Alphabetical country browser with continent filters, A–Z jump and sorting by
  name / population / area.
- Favorites, recently viewed, per-section bookmarks and per-country learning
  progress — stored locally (Zustand + `localStorage`), private to the device.

**Platform**
- SEO: per-country metadata, Open Graph, JSON-LD `Country` schema, dynamic
  `sitemap.xml` and `robots.txt`.
- PWA: installable, offline service worker (cache-first geodata, network-first
  pages, offline fallback).
- Performance: 197 country pages statically generated (SSG), lazy-loaded maps,
  cached immutable geodata, code-split client islands.
- Accessibility: keyboard nav, ARIA roles/labels, focus rings, reduced-motion
  support, and a table view for every chart.

---

## Quick start

```bash
npm install              # installs deps, generates the Prisma client
npx prisma db push       # creates the SQLite database (dev.db)
npm run pipeline         # downloads open data, builds the DB + geodata (~15s)
npm run dev              # http://localhost:3000
```

> The pipeline caches downloads under `.cache/pipeline`, so re-runs are fast.
> `npm run pipeline:fresh` forces a re-download. See `QUICKSTART.md` for the
> shortest path if the generated data is already bundled.

### Production build

```bash
npm run build && npm start
```

---

## Data pipeline

`npm run pipeline` (`scripts/pipeline/`) is idempotent and does everything:

1. **Download** open datasets (cached, retried with backoff).
2. **Normalize** into one record per sovereign state (197 total).
3. **Merge** the curated knowledge base (`scripts/pipeline/knowledge.ts`).
4. **Generate** 29 encyclopedia sections per country.
5. **Load** the Prisma database (countries, cities, sections).
6. **Emit** static geodata into `public/data` (world map, per-country shapes,
   admin-1 boundaries, rivers, lakes) and flag SVGs into `public/flags`.

### Sources

| Source | Used for |
|---|---|
| [REST Countries](https://restcountries.com/) | Names, capitals, population, area, languages, currencies, borders, codes |
| [Natural Earth](https://www.naturalearthdata.com/) | Political boundaries (110m world, 10m admin-1), populated places, rivers, lakes |
| [mledoze/countries](https://github.com/mledoze/countries) | Per-country GeoJSON shapes |
| [samayo/country-json](https://github.com/samayo/country-json) | Religion, government type, national dish, independence date, life expectancy, temperature, elevation |
| [Wikimedia Commons](https://commons.wikimedia.org/) | Destination & landmark photographs (client-side, via `Special:FilePath`) |
| [OpenStreetMap](https://www.openstreetmap.org/) / [OpenTopoMap](https://opentopomap.org/) | Optional street/road and terrain basemaps |
| [country-flag-icons](https://github.com/catamphetamine/country-flag-icons) | SVG national flags |

Admin-1 boundaries use Natural Earth 10m, simplified in-memory with mapshaper
(Visvalingam 12%) so every country has provinces without shipping a 60 MB file.

### A note on the curated knowledge base

Descriptions of destinations, inventions, foods, festivals and the BCE/CE
timelines were authored for this atlas and summarised from well-established
general knowledge; each section links out to Wikipedia, the CIA World Factbook,
Britannica and the World Bank for citable depth. Photographs reference exact
Wikimedia Commons file names and load directly in the visitor's browser — the
build environment does not need access to Wikimedia. To extend coverage, add an
entry keyed by ISO alpha-3 code in `scripts/pipeline/knowledge.ts` and re-run
the pipeline; countries without an entry fall back to data-derived content.

---

## Architecture

```
src/
  app/                      # Next.js App Router
    page.tsx                # homepage (world map + stats)
    country/[slug]/page.tsx # SSG country pages (map + tabs)
    browse/  favorites/  about/  offline/
    api/                    # countries, countries/[slug], search
    sitemap.ts robots.ts manifest.ts
  components/
    map/                    # WorldMap, CountryMap, region styling
    content/                # SectionRenderer, ChartBlock, RichText, SmartImage
    country/  browse/  home/  search/  layout/  pwa/
    ui/                     # shadcn/ui primitives
  lib/                      # types, prisma, serialize, search, sections, store…
scripts/pipeline/           # sources, geo, knowledge base, content, orchestrator
prisma/schema.prisma        # Country / City / Section models
public/data/                # generated geodata   public/flags/  flag SVGs
```

**Content model.** Every section is an array of typed `ContentBlock`s
(`src/lib/types.ts`). The pipeline produces them; `SectionRenderer` renders them.
Add a block type by extending the union, the generator and the renderer.

**Maps.** Leaflet is used directly (not `react-leaflet`) for explicit layer
lifecycle control. Map components are client-only islands, dynamically imported
with `ssr: false`.

---

## Switching to PostgreSQL

1. In `prisma/schema.prisma`, set `datasource.provider = "postgresql"`.
2. Set `DATABASE_URL` (see `.env.example`) to your Postgres string.
3. `npx prisma db push && npm run pipeline`.

Models are portable — array/object fields are stored as JSON strings.

---

## Testing & quality

```bash
npm test         # Vitest unit tests (slug, search ranking, formatting, geo)
npm run typecheck
npm run lint
```

---

## Accuracy & attribution

Boundaries follow Natural Earth's de-facto representation and imply no
endorsement of any territorial claim. Fast-changing topics link to live sources
rather than storing numbers that go stale. Map tiles are © OpenStreetMap
contributors and © OpenTopoMap (CC-BY-SA); photographs are © their respective
authors via Wikimedia Commons.

## License

Code: MIT (see `LICENSE`). Data belongs to the upstream sources under their
respective licenses.
