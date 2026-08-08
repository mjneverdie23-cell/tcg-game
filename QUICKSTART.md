# Running World Atlas

## Prerequisites

- **Node.js 20+** (tested on Node 22) and npm.

## Setup (from a fresh clone)

```bash
npm install        # installs deps + generates the Prisma client
npx prisma db push # creates the SQLite database
npm run pipeline   # imports open datasets, builds DB + map data (~15s, needs internet)
```

Then run it:

```bash
npm run dev        # development, http://localhost:3000
# or
npm run build && npm start   # optimized production build
```

Open **http://localhost:3000**.

> If this project was delivered as an archive that already includes
> `prisma/dev.db`, `public/data/` and `public/flags/`, you can skip
> `npx prisma db push` and `npm run pipeline` — just `npm install` then
> `npm run dev`.

## What you can do

- **Home** – interactive world map: hover countries, filter by continent, click
  any country to open its page.
- **/browse** – all 197 countries; filter, sort, jump A–Z.
- **/country/italy** (or any slug) – detailed layered map + 29 encyclopedia tabs,
  including **Tourism** (famous destinations with photos), **Inventions**,
  **Cuisine**, **Holidays & Festivals** and a **BCE/CE Timeline** of ancient
  civilizations through the modern era.
- **⌘K / Ctrl-K** – global search. Favorites, bookmarks and learning progress
  persist locally.

## Other commands

```bash
npm test          # unit tests (Vitest)
npm run typecheck # TypeScript, no emit
npm run lint      # ESLint
npm run pipeline:fresh   # re-download every dataset
```

## Notes

- **Photographs** come from Wikimedia Commons and load in your browser; any that
  fail to resolve are hidden gracefully. **Streets** and **Terrain** map layers
  stream from OSM/OpenTopoMap and need a network connection. Everything else —
  boundaries, cities, rivers, lakes — works offline from the bundled data.
- To use PostgreSQL instead of SQLite, see "Switching to PostgreSQL" in `README.md`.
