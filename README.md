# Primordia — Dinosaur Trading Card Game

An original dinosaur trading card game inspired by Pokémon TCG Pocket, with
a Field Card mechanic (à la Adventure Time Card Wars) as its signature twist.

**This repository contains two implementations:**

- **`godot/`** — the go-forward **Godot 4.7** project (GDScript, hybrid
  2D/3D). Open `godot/project.godot` in the Godot editor.
- root (`src/`, `index.html`, …) — the original **React + TypeScript** web
  prototype the Godot version is migrated from. Its card generator and data
  remain the source of `godot/database/cards.json` via `npm run export:godot`
  until the Python scraper (Milestone G2) takes over.
- **`tools/`** — cross-project tooling (card exporter; Python wiki scraper
  arrives in Milestone G2).

## Godot migration milestones

- [x] **G1 — Project setup**: project.godot, folder structure, autoloads
      (GameData/PlayerData/Settings/SceneRouter), typed data models,
      JSON card database (66 cards), navigable placeholder scenes,
      hybrid 2D/3D battle stage
- [x] **G2 — Python scraper** (`tools/jurassic_scraper.py`): scrapes the
      JW:TG wiki, downloads card art to `godot/assets/textures/cards/`,
      writes `godot/database/creatures.json` and regenerates the dinos in
      `cards.json` with deterministic stats (Python port verified
      byte-identical to the web generator). Run it where the wiki is
      reachable: `pip install -r tools/requirements.txt && python
      tools/jurassic_scraper.py` — resumable, `--force` re-downloads art.
- [x] **G3 — Card rendering + collection screen**: CardFace renderer for all
      four card kinds (type/rarity theming, art with emblem fallback),
      full-screen CardViewer, filterable collection grid with owned counts,
      rule-based starter collection for new profiles
- [x] **G4 — Deck builder**: 20-card decks (max 2 copies, ≤10 Instinct,
      ≥1 basic dino, owned-limited), live validation + composition panel,
      multiple saved decks, auto-build, starter deck for new profiles
- [x] **G5 — Battle system**: rules engine with a legal-actions API,
      statuses, weakness/resistance, evolution, retreat, trainer effects,
      win conditions; battle HUD over the 3D stage; baseline AI; headless
      AI-vs-AI test:
      `godot --headless --path godot res://scenes/tests/battle_sim.tscn`
- [x] **G6 — AI**: KO-first attack choice, threat assessment, intelligent
      retreat/switch, energy planning, trainer timing, field evaluation
- [x] **G7 — Field card mechanics**: fields playable in battle, all six
      effects live, KO re-check on field swaps, auto-build slots a field
- [x] **G8 — Demo completion**: shop with daily free pack (24 h) and
      premium pack, simple pack opening with duplicate protection
- [x] **G9 — Quest matches**: four AI rivals on the battle tab, each
      unlocked by beating the one before and paying 100/120/150/200 coins
      on a Claim button; difficulty is expressed as beginner mistakes the
      rival stops making rather than as stat bonuses
- [x] **G10 — Versus player**: two copies of the game play each other over
      the network. The host opens a port (via UPnP where the router allows
      it), the guest types the address, and from then on only moves cross
      the wire — both sides run the same seeded engine and checksum every
      move against each other. See
      [`godot/PLAYING_ONLINE.md`](godot/PLAYING_ONLINE.md).

### Headless tests (require a Godot 4.7 binary)

```sh
godot --headless --path godot res://scenes/tests/battle_sim.tscn  # 25 AI-vs-AI games
godot --headless --path godot res://scenes/tests/pack_sim.tscn    # 400 pack openings
```

---

## The original web prototype

A premium, offline-first trading card game for the browser. Collect
dinosaurs, build decks, open packs and battle an AI opponent. Installable as
a PWA on desktop and mobile; everything (including save data) lives
on-device.

## Tech stack

- **React 19 + TypeScript (strict)** on **Vite**
- **TailwindCSS 4** — design tokens for class/rarity colors, glassmorphism
- **Framer Motion** — screen transitions and card animations
- **Zustand** — state management, persisted to **IndexedDB** (via `idb`)
- **vite-plugin-pwa** — installable, fully offline
- **Vitest + Testing Library** — unit tests for game logic and UI wiring

## Getting started

```sh
npm install
npm run dev        # start the dev server
npm test           # run the test suite
npm run lint       # eslint
npm run build      # typecheck + production build (dist/)
npm run preview    # serve the production build
npm run icons      # regenerate PWA icons from public/favicon.svg
npm run scrape     # build the creature database (see below)
```

### Building the creature database

`npm run scrape` scrapes creature data (name, class, rarity, generation,
evolution tier, description) from the
[Jurassic World: The Game wiki](https://jurassic-world-the-mobile-game.fandom.com/wiki/List_of_All_Creatures),
downloads every creature's art as resized WebP into `src/assets/creatures/`
and writes `src/database/creatures.json`. Images are bundled with the app —
nothing is hotlinked at runtime. The script is idempotent (`--force` to
re-download art) and needs outbound access to
`jurassic-world-the-mobile-game.fandom.com` and `static.wikia.nocookie.net`.
The scraped art is Universal/Ludia property — fine for a personal fan
project, not for commercial distribution.

## Project structure

```
src/
  components/        shared UI + feature components
    ui/              primitives (ScreenShell, ScreenHeader, Toggle, …)
    game/            app shell: main menu, settings, background
    cards/           card rendering                     (Milestone 3)
    packopening/     pack opening flow                  (Milestone 5)
    deckbuilder/     deck builder                       (Milestone 6)
    battle/          battle screen                      (Milestone 7)
    shop/            shop                               (Milestone 5+)
  ai/                battle AI                          (Milestone 8)
  assets/            downloaded card art                (Milestone 2)
  database/          dinosaur card database (JSON)      (Milestone 2)
  hooks/             shared React hooks
  stores/            zustand stores (navigation, settings, …)
  utils/             storage (IndexedDB), helpers
scripts/             node tooling (icon generation, card scraper)
```

Screens register themselves in `SCREENS` in `src/App.tsx`; main-menu entries
unlock automatically once their screen exists.

## Game design pillars

- **Four classes** (replace Pokémon energy types): Carnivore, Herbivore,
  Pterosaur, Amphibian. Energy cards are called **Instinct**.
- **Card types**: Dinosaur, Trainer (Item / Support), Field, Instinct.
- **Field cards** (new mechanic, inspired by Card Wars): one shared field on
  the battlefield modifies rules for both players until replaced.
- **Rarities**: Common, Rare, Epic, Legendary, Mythic (animated).

## Milestones

- [x] **M1 — Project setup**: tooling, PWA, design tokens, app shell,
      navigation, IndexedDB save layer, settings
- [x] **M2 — Card database scraper**: scraper + schema + integrity tests
      (running it needs wiki network access — see above)
- [ ] **M3 — Card rendering engine**
- [ ] **M4 — Collection**
- [ ] **M5 — Pack opening** (+ daily pack, shop currency)
- [ ] **M6 — Deck builder**
- [ ] **M7 — Battle engine**
- [ ] **M8 — Battle AI**
- [ ] **M9 — Field card system**
- [ ] **M10 — Polish**
