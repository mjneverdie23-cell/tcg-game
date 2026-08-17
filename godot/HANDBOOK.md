# Primordia — Handbook

Every part of the Godot game, what it is responsible for, and how to change
it. Two ways to read this:

- **Working out where something lives** → [The map](#the-map) and the
  component sections after it.
- **Wanting to change one specific thing** → jump to
  [How do I change…](#how-do-i-change) and follow the recipe.

Everything here describes `godot/`. The `src/` tree at the repository root
is the retired React prototype; only `database/cards.json` still crosses
between them.

---

## Contents

- [Running it](#running-it)
- [House rules](#house-rules)
- [The map](#the-map)
- [Layer 1 — card data](#layer-1--card-data)
- [Layer 2 — rules](#layer-2--rules)
- [Layer 3 — global state (autoloads)](#layer-3--global-state-autoloads)
- [Layer 4 — screens](#layer-4--screens)
- [Layer 5 — drawn UI components](#layer-5--drawn-ui-components)
- [The battle screen in depth](#the-battle-screen-in-depth)
- [Playing another person](#playing-another-person)
- [How do I change…](#how-do-i-change)
- [Testing what you changed](#testing-what-you-changed)
- [Traps worth knowing](#traps-worth-knowing)

---

## Running it

Open `godot/project.godot` in **Godot 4.7** and press Play. The game starts
on the home screen (`scenes/menus/main_menu.tscn`).

Nothing needs installing. There are no addons, no C#, no external assets —
every icon, dinosaur silhouette, coin and card face in the game is drawn in
code, so nothing can go missing.

Save files live in Godot's user directory (`user://save.json` and
`user://settings.json`) — Settings → *Reset save data* clears the profile.

---

## House rules

Conventions the code already follows. Keeping to them is what keeps the
project navigable.

| Rule | Why |
|---|---|
| Every file opens with a `##` block saying what it is **for**, not what it contains | The file listing already says what it contains |
| Comments explain **why**, never what the next line does | The line says what it does |
| No file over **1000 lines**, no class over **20 public methods** | `gdlint` fails the build; when a file grows past it, something inside it wanted to be its own class |
| Rules never touch nodes; screens never re-implement rules | The engine runs headless in tests and over the network |
| Constants at the top, named, with a comment when the value was chosen rather than obvious | Tuning should never mean hunting through a function body |

Check your work with:

```sh
gdparse <files>   # syntax
gdlint <files>    # style, file length, method counts
godot --headless --path godot res://scenes/tests/compile_check.tscn
```

---

## The map

```
godot/
├── project.godot            autoload registry, window size, renderer
├── database/cards.json      the card catalog — every card in the game
├── autoload/                global state, alive on every screen
│   ├── game_data.gd         loads cards.json, typed lookups
│   ├── player_data.gd       the profile: cards, coins, decks, ladder, quests
│   ├── settings.gd          audio + reduced motion
│   ├── scene_router.gd      screen navigation by name
│   └── net.gd               the online match session
├── scripts/
│   ├── data/                one class per card kind (pure data)
│   ├── cards/card_style.gd  colours and panel styles for card faces
│   ├── decks/               deck legality + what surplus cards are worth
│   ├── battle/              the rules engine (no nodes anywhere)
│   ├── ai/battle_ai.gd      the opponent
│   ├── progression/         trophy ladder, quest chain
│   ├── shop/pack_rules.gd   pack contents and rarity rolls
│   └── ui/                  drawn widgets, reusable across screens
├── scenes/
│   ├── menus/               home, profile, settings, the bottom tab bar
│   ├── collection/          browse the catalog + build decks
│   ├── shop/  packs/        coins and pack opening
│   ├── online/              versus-player lobby
│   ├── cards/               card face, 3D card, pile, full-screen viewer
│   ├── battle/              the battle screen and its seven helpers
│   └── tests/               headless test scenes
├── HANDBOOK.md              this file
└── PLAYING_ONLINE.md        how two people connect
```

The dependency direction is one-way and worth preserving:

```
data  →  rules  →  autoloads  →  screens  →  UI components
```

A rule may read card data. A screen may call a rule. Nothing ever points
back up: the engine has no idea a screen exists.

---

## Layer 1 — card data

### `database/cards.json`

The whole catalog: **62 cards** (48 dinosaurs, 8 trainers, 6 environments).
Four arrays under one root object.

```jsonc
{
  "version": 1,
  "dinos": [{
    "id": "dino:velociraptor",        // unique; the prefix is convention
    "name": "Velociraptor",
    "type": "carnivore",              // carnivore | herbivore | pterosaur | amphibian
    "rarity": "common",               // common | rare | epic | legendary | mythic
    "hp": 70,
    "stage": 1,                       // 1 = basic (the only stage shipped)
    "evolves_from": "",               // a stage-1 card id turns this into a stage 2
    "attacks": [
      {"name": "Bone Crusher", "cost": ["carnivore"], "damage": 30}
    ],
    "retreat_cost": 1,                // energy to step back to the bench
    "description": "…",
    "image": ""                       // optional res:// path; a drawn emblem fills in
  }],
  "trainers": [{
    "id": "trainer:dino-berry",
    "trainer_kind": "spell",          // spell = free, any turn; support = one per turn, turn 2+
    "text": "Heal 30 damage from your active dinosaur.",
    "effect": {"type": "heal", "amount": 30}
  }],
  "fields": [{
    "id": "field:dense-jungle",
    "type": "herbivore",              // which dinosaurs it empowers
    "buff": {"type": "hp-bonus", "amount": 20}
  }],
  "instincts": []                     // energy cards; unused — energy is auto-generated
}
```

**Effect types a Trainer may use** (anything else resolves as a no-op):

| `effect.type` | Fields | What happens |
|---|---|---|
| `heal` | `amount` | Heals your Active |
| `heal-all` | `amount` | Heals every dinosaur you have in play |
| `draw` | `count` | Draw that many cards |
| `draw-to` | `hand_size` | Draw until your hand holds that many |
| `search-dino` | — | Pull a basic Dinosaur out of your deck |
| `damage-boost` | `amount` | Your attacks hit harder this turn |
| `switch` | — | Swap your Active with a chosen benched dinosaur |
| `bonus-energy` | — | +1 energy to attach this turn |

**Buff types an Environment may use:**

| `buff.type` | Effect on your matching Active |
|---|---|
| `hp-bonus` | +`amount` max HP |
| `damage-bonus` | +`amount` damage dealt |
| `heal-per-turn` | Heals `amount` between turns |
| `free-retreat` | Retreat costs no energy |

### `scripts/data/*.gd`

One class per card kind, all pure data with no behaviour:

| Class | Notes |
|---|---|
| `CardData` | Base: `id`, `display_name`, `kind`, `rarity` |
| `DinoCardData` | `dino_type`, `hp`, `stage`, `evolves_from`, `attacks`, `retreat_cost`, `weakness`, `resistance`, `description`, `image`, plus optional `model` / `model_scale` for a 3D model standing on the card |
| `TrainerCardData` | `trainer_kind` (`KIND_SPELL` / `KIND_SUPPORT`), `text`, `effect` |
| `FieldCardData` | `dino_type`, `text`, `buff` |
| `InstinctCardData` | Energy card; nothing in the shipped catalog uses it |
| `AttackData` | `name`, `cost` (array of type names), `damage` |
| `CardCatalogTypes` | The enums — `DinoType`, `Rarity`, `CardKind` — and their string maps |

---

## Layer 2 — rules

Pure static classes and `RefCounted` objects. No nodes, no signals to the
UI, no `get_tree()`. This is what makes them testable headlessly and safe
to run in lockstep across a network.

### `scripts/decks/deck_rules.gd` — what a legal deck is

```
DECK_SIZE = 23      MAX_COPIES = 2
MAX_SUPPORT = 6     MAX_SPELL = 6      MAX_ENVIRONMENT = 2
```

Plus: at least one Environment and at least one basic Dinosaur, never more
copies than you own, and everything that is not a Trainer or Environment
must be a Dinosaur. Energy is auto-generated and is not a deck card.

| Function | Use |
|---|---|
| `validate(card_ids)` | `PackedStringArray` of problems; empty means legal |
| `can_add(card_ids, card, owned)` | Whether the builder should allow one more |
| `category_counts(card_ids)` | `{dino, support, spell, environment, other}` |
| `breakdown(card_ids)` | The one-line summary in the builder |
| `auto_build(owned, forced_type)` | Builds a legal deck from a collection |
| `primary_type(owned)` | The type someone collects most of |

### `scripts/battle/battle_engine.gd` — the rules

The heart of the game. Both the human UI and the AI drive it exclusively
through `get_legal_actions()` and `apply(action)`, so neither can cheat and
neither can drift from the other.

```
POINTS_TO_WIN = 2          BENCH_SIZE = 3          OPENING_HAND = 6
MIN_OPENING_BASICS = 2     MULLIGAN_ATTEMPTS = 20
EMPTY_ACTIVE_GRACE_TURNS = 2                       SURRENDER_TURN = 10
POISON_DAMAGE = 10
```

**The action vocabulary.** Every move in the game is one of these
dictionaries, and `get_legal_actions()` returns exactly the ones allowed
right now for `current`:

| Action | Shape |
|---|---|
| Attach energy | `{"type": "attach", "target": -1 or bench index}` |
| Field a basic | `{"type": "place_basic", "hand": i, "slot": -1 or 0..2}` |
| Evolve | `{"type": "evolve", "hand": i, "target": -1 or bench index}` |
| Play a Trainer | `{"type": "trainer", "hand": i}` (+ `"target"` for `switch`) |
| Set an Environment | `{"type": "environment", "hand": i}` |
| Retreat | `{"type": "retreat", "bench": b}` |
| Attack | `{"type": "attack", "index": a}` |
| Concede | `{"type": "surrender"}` |
| End the turn | `{"type": "end_turn"}` |

`slot` on `place_basic` is the **physical place**: `-1` is the Active slot,
`0..2` are the bench places left to right. The bench array stays packed;
each `DinoInPlay` remembers its `slot`, which is why a dinosaur can be
benched anywhere and never shuffles sideways afterwards.

**The turn.** Draw → attach one energy → play cards → attack once → end.
Turn 1 withholds attacks and Supports, nothing else. Losing your last
dinosaur leaves the Active slot empty rather than ending the battle; you
are only beaten if you still cannot field one at the start of a later turn,
and never before `EMPTY_ACTIVE_GRACE_TURNS` has passed.

**Determinism.** One seeded `RandomNumberGenerator` decides the coin toss
and both shuffles. Same decks + same seed + same actions = same battle,
which is the entire basis of online play.

### `scripts/battle/battle_player_state.gd` / `dino_in_play.gd`

One side's zones (`deck`, `hand`, `discard`, `active`, `bench`), points,
`element`, and per-turn flags (`energy_budget`, `support_played`,
`retreated`, `damage_boost`). `DinoInPlay` is one dinosaur on the table:
`card_id`, `damage`, `energy`, `statuses`, `turn_entered`, `slot`.

### `scripts/ai/battle_ai.gd` — the opponent

Picks from the same legal actions a human gets. Difficulty is expressed as
**mistakes it stops making**, not as stat bonuses:

```gdscript
const PROFILES: Array = [
    {"skip_energy": 0.5,  "end_early": 0.3,  "idle_retreat": 0.25, …},  # level 0
    …                                                                    # level 3 = 0.0
]
```

| Blunder | What it looks like at the table |
|---|---|
| `skip_energy` | Ends a turn without attaching its energy |
| `end_early` | Walks away with cards still in hand |
| `idle_retreat` | Retreats for no reason, burning energy |
| `waste_trainer` | Spends a Support with nothing to gain |
| `stop_attacking` | Attacks once, then goes quiet |

Two guards keep blunders sloppy rather than suicidal: a lethal attack is
never skipped, and a doomed Active never idly retreats.

`configure(level, rng_seed)` sets the profile. Level 3 is the sharp AI used
by free battles.

### `scripts/progression/arena_rules.gd` — the ladder

Ten arenas from *Fossil Flats* (0 trophies) to *Primordia Summit* (3600).
`WIN_TROPHIES = 30`, `LOSS_TROPHIES = 15`. A loss never takes you below
zero, so a bad run costs progress but cannot spiral.

### `scripts/progression/quest_rules.gd` — the quest chain

Four matches on the Battle tab, each unlocked by beating the one before:

| # | Rival | Their deck | Reward | AI level |
|---|---|---|---|---|
| 1 | Field Scout | herbivores, ≤ rare | 100 | 0 |
| 2 | Bone Tracker | amphibians, ≤ epic | 120 | 1 |
| 3 | Ridge Warden | pterosaurs, ≤ legendary | 150 | 2 |
| 4 | The Alpha | carnivores, ≤ mythic | 200 | 3 |

State per match is `locked` / `ready` / `won` / `claimed`, derived from
`PlayerData` — nothing is cached. `build_rival_deck(index)` drafts the
rival's deck under the rarity cap (which always admits rares, because every
Environment is rare or epic and a deck without one is not legal).

### `scripts/shop/pack_rules.gd` — packs

Two packs, five cards each, rolled per slot from rarity weights:

| Pack | Price | Slots |
|---|---|---|
| Dawn Pack | free, every 24 h | 4 standard + 1 premium |
| Primal Pack | 100 coins | 3 standard + 1 premium + 1 chase (epic or better) |

### `scripts/decks/collection_economy.gd`

What surplus copies are worth. A deck may hold `MAX_COPIES` of a card;
anything beyond that is sellable from the Shop.

---

## Layer 3 — global state (autoloads)

Registered in `project.godot`, alive on every screen, addressable by name
from anywhere.

### `GameData` — the catalog

Loads `cards.json` once at startup into typed arrays.

```gdscript
GameData.get_card("dino:velociraptor")   # -> CardData (push_error + null if unknown)
GameData.has_card(id)
GameData.all_cards()                     # dinos + trainers + fields + instincts
GameData.dinos / .trainers / .fields / .instincts
```

### `PlayerData` — the profile

Everything that persists, saved to `user://save.json` after **every**
mutation, so the file can never drift from what is on screen.

| Field | Meaning |
|---|---|
| `owned_cards` | `card_id -> copies` |
| `coins` | `STARTING_COINS = 1290` for a new profile |
| `decks` | `[{name, card_ids}]` |
| `trophies`, `best_trophies` | Ladder standing |
| `battles_played/won`, `packs_opened`, `cards_gained` | Career counters |
| `quest_wins`, `quests_claimed` | Quest-chain progress, by match id |
| `last_daily_claim`, `last_coin_claim` | 24 h cooldowns |

Key calls: `add_card`, `spend_coins`, `earn_coins`, `record_battle(won, ranked)`,
`record_quest_win(i)`, `claim_quest(i)`, `save_deck`, `sell_surplus`,
`reset_all`.

`SAVE_VERSION` is **5**. `_migrate_save()` upgrades older files; new fields
that default cleanly need no migration entry.

### `Settings`

`music_enabled`, `sfx_enabled`, `reduced_motion`, saved to
`user://settings.json`. **`Settings.reduced_motion` is checked by every
animation in the game** — respect it in anything new you animate.

### `SceneRouter` — navigation

Screens are addressed by name, never by path:

```gdscript
SceneRouter.go_to("collection")
SceneRouter.back()
SceneRouter.current()          # the tab bar highlights this
```

`SCREENS` maps name → scene path. `TAB_SCREENS` lists the six that the tab
bar owns: switching between them replaces the visited path instead of
stacking, so tab-hopping cannot build an unbounded back stack.

Two navigation-scoped variables describe a transition rather than the
profile, and deliberately do not survive a restart:

- `battle_ranked` — whether the next battle stakes trophies
- `quest_match` — the quest index the next battle should run, or `-1`

### `Net` — the online session

See [Playing another person](#playing-another-person).

---

## Layer 4 — screens

Each screen is a `.tscn` + a `.gd` of the same name. Nodes the script talks
to are marked **unique** in the scene (`unique_name_in_owner`), so the
script says `%CoinsLabel` and never a node path — moving a node in the tree
cannot break the script.

Every tab screen instances `scenes/menus/nav_bar.tscn` at the bottom and
keeps its content clear of `MenuStyle.NAV_CLEARANCE`.

| Screen | File | What it is |
|---|---|---|
| **Home / Battle** | `scenes/menus/main_menu.gd` | Trophies, arena badge, mode dropdown, the quest path, and the way into a match |
| **Collection** | `scenes/collection/collection.gd` | Two tabs in one screen: browse the catalog, and build decks |
| **Shop** | `scenes/shop/shop.gd` | Free daily coins (`DAILY_COINS = 200`) and selling surplus cards |
| **Packs** | `scenes/packs/packs.gd` | The two packs and the reveal animation |
| **Profile** | `scenes/menus/profile.gd` | Name, ladder position, career stats |
| **Settings** | `scenes/menus/settings_menu.gd` | Audio, reduced motion, reset save |
| **Versus lobby** | `scenes/online/online.gd` | Host or join a match |
| **Battle** | `scenes/battle/battle.gd` | The match itself — [in depth below](#the-battle-screen-in-depth) |

**Home screen detail.** The mode dropdown (`MODES`) has three entries;
picking *Versus player* turns the BATTLE button into FIND OPPONENT and
routes to the lobby instead of a match. The quest path down the right is
`QuestPath`, and the mission panel beside it shows whatever the chain wants
next: play the open match, or claim a reward waiting to be collected.

---

## Layer 5 — drawn UI components

Everything in `scripts/ui/` is drawn in `_draw()` rather than imported.
That is why the game has no image assets, re-tints for free, and stays
crisp at any window size. All are reusable `Control`s.

| Class | What it draws | Main knobs |
|---|---|---|
| `MenuStyle` | *(not a widget)* the palette and panel/button styles for the whole menu shell | `ACCENT`, `PANEL`, `EDGE`, `NAV_HEIGHT` |
| `CardStyle` | *(not a widget)* colours and panels for **cards** — kept separate so the two never fight | `TYPE_COLORS`, `RARITY_COLORS`, `BASE_SIZE` |
| `NavIcon` | The six tab glyphs | `kind`, `color` |
| `HeroEmblem` | The theropod silhouette on the home screen | `dino_type`, `SHAPE_*` |
| `ArenaBadge` | The hexagonal arena plaque | `arena_number`, `arena_name` |
| `QuestPath` | The four quest nodes and the trail between them | `NODE_RADIUS` |
| `FanHand` | A hand of cards in an arc, and every gesture on it | `CARD_SCALE`, `HOLD_SECONDS`, `MAX_SPREAD`, `HOVER_LIFT` |
| `EnergyOrb` | The energy ball | `color`, `spent` |
| `DropSlot` | The hollow dashed frame in the middle of the table | `DASH`, `GAP`, `active` |
| `CoinFlip` | The opening coin toss | `SPIN_TIME`, `HALF_TURNS`, `HOLD_TIME` |
| `CardFace` | The 2D face of any card — the one renderer used everywhere | `CardStyle.BASE_SIZE` |
| `Card3D` | A card as a tabletop object (the face rendered to a texture on a quad) | `WIDTH`, `HEIGHT`, `HOVER_RAISE` |
| `CardPile3D` | A deck or discard pile as a physical stack | `CARD_THICKNESS`, `MAX_HEIGHT` |
| `CardViewer` | The full-screen card reader | `VIEW_SCALE` |

**`CardFace` is the single card renderer.** The collection grid, the pack
reveal, the hand, the zoom and the 3D board all instance the same scene at
different scales, so a change to a card's look lands everywhere at once.

---

## The battle screen in depth

`scenes/battle/battle.gd` is the only screen with helpers of its own,
because it is doing several unrelated jobs at once. Each helper is a class
that owns one of them:

| File | Class | Owns |
|---|---|---|
| `battle.gd` | *(scene root)* | The state machine: whose turn, what is legal, what the player is doing |
| `battle_fx.gd` | `BattleFx` | Camera moves, card ghosts, the turn banner, the notice line |
| `board_slots.gd` | `BoardSlots` | Where a slot **is** on the table, and how brightly it is lit |
| `battle_piles.gd` | `BattlePiles` | The four piles and the used-cards viewer |
| `battle_zoom.gd` | `BattleZoom` | The zoomed card, with attacks and retreat laid on it |
| `energy_drag.gd` | `EnergyDrag` | Carrying energy from its well onto a dinosaur |
| `battle_result.gd` | `BattleResult` | The closing panel — and the only place a battle pays out |
| `battle_link.gd` | `BattleLink` | Keeping an online match in step with the opponent's |

### Seats: "you" is not always player 0

The engine numbers its players 0 and 1. The screen always draws **you** on
the near row, whichever seat you hold (an online guest is seat 1). Three
helpers do the translating, and everything in the screen goes through them:

```gdscript
_me()                  # your BattlePlayerState
_foe()                 # theirs
_table_side(owner)     # 0 = near half (yours), 1 = far half
_place_of(dino, owner) # 0 = Active, 1..3 = bench places left to right
```

Never write `_engine.players[0]` in this screen. That is the bug the seat
helpers exist to prevent.

### How a card gets played

1. `FanHand` sees a press and reports one of three gestures:
   **drag** (moved past `DRAG_THRESHOLD`), **hold** (still for
   `HOLD_SECONDS`), or **tap** (released where it started).
2. On drag start, `_show_targets()` asks `_targets_for(hand_index)` which
   places on the table would accept this card. Dinosaurs name board places;
   Spells, Supports and Environments name the centre `DropSlot`.
3. Each target lights at one of three levels (`BoardSlots.OFF` / `LEGAL` /
   `ARMED`). An occupied slot also haloes the card standing in it.
4. On drop, `_target_under(at)` finds which target the pointer is over. One
   action → apply it. Several → the card returns to the fan and a
   **dinosaur choice** opens.
5. A drop on nothing returns the card to the fan, having cost nothing.

### The dinosaur choice

Retreating, playing a switch card and clicking the energy well all end in
the same question: *which of your dinosaurs?* Rather than a list of names,
`_begin_choice()` haloes every candidate, pushes the camera in on the bench
(`battle.gd` → `BENCH_FOCUS`, `BENCH_FOCUS_DISTANCE`) when they are all benched, and takes
the answer as a click on the card you mean.

### Refusing a move

`_apply_player_action()` checks legality **before** applying. An illegal
move raises a notice through `_why_refused()` instead of silently doing
nothing — and is never put on the wire in an online match.

---

## Playing another person

`autoload/net.gd` plus `scenes/battle/battle_link.gd`. The player-facing
instructions are in **`PLAYING_ONLINE.md`**; this is how it works.

1. The host opens UDP port `PORT` (24567) and asks the router to forward it
   over UPnP, on a background thread. The lobby prints whichever address is
   actually true — the internet one only once the router agreed.
2. The guest connects and sends its deck and name.
3. The host validates the deck with `DeckRules.validate`, picks
   `battle_seed`, and sends both decks and the seed back.
4. Both build `BattleEngine.new(host_deck, guest_deck, seed)`. Host = seat
   0, guest = seat 1. **Identical engines.**
5. From then on only moves cross the wire, each with a checksum of the
   state it produced. `BattleLink` checks an arriving move against the rules
   before applying it, then compares checksums. A mismatch stops the match
   on both sides rather than letting them drift.

**Trust model:** the host checks the guest's deck and both sides check
every move, so neither can play a card they do not hold or act out of turn.
But each holds a full copy of the engine, opposing hand included, so a
modified build could read it. Play with people you would play across a
table.

---

## How do I change…

Each recipe names the file, the symbol, and anything that changes with it.

### Cards and content

| I want to… | Do this |
|---|---|
| **Add a card** | Append an object to the right array in `database/cards.json`, using an unused `id`. It appears everywhere immediately — collection, packs, decks. No code change |
| **Change a card's stats** | Edit its entry in `cards.json`. `hp`, `attacks[].damage`, `retreat_cost`, `rarity` |
| **Add an evolution** | Give a new dino `"stage": 2` and `"evolves_from": "<basic card id>"`. The engine, the AI and the drag targets already handle evolution; nothing in the shipped catalog uses it yet |
| **Give a card 3D art** | Set `model` (a `res://` path to a `PackedScene`) and `model_scale` on a `DinoCardData`. `Card3D` stands it on the card face and it inherits every animation |
| **Add a new Trainer effect** | Add a `case` to the `match card.effect["type"]` in `BattleEngine._do_trainer`, and if it needs a target, one in `_add_trainer_actions` too |
| **Add a new Environment buff** | Add the name to `FieldCardData.KNOWN_BUFFS`, then read it with `BattleEngine._buff_amount()` (or `_has_buff()`) wherever it should apply |

### Balance and rules

| I want to… | Do this |
|---|---|
| **Change deck size / copy limits** | `DeckRules.DECK_SIZE`, `MAX_COPIES`, `MAX_SUPPORT`, `MAX_SPELL`, `MAX_ENVIRONMENT`. The builder, validation, auto-build and the starter deck all read these |
| **Change hand size** | `BattleEngine.OPENING_HAND` (currently 6) |
| **Change knockouts needed to win** | `BattleEngine.POINTS_TO_WIN` |
| **Change bench size** | `BattleEngine.BENCH_SIZE`. `BoardSlots` builds that many outlines automatically; check they still fit the table |
| **Change when surrender unlocks** | `BattleEngine.SURRENDER_TURN` (the button's tooltip reads it) |
| **Change the opening grace period** | `BattleEngine.EMPTY_ACTIVE_GRACE_TURNS` |
| **Make the AI harder or softer** | The rates in `BattleAI.PROFILES`. Lower = better play. Level 3 is all zeroes |
| **Change quest rewards or rivals** | `QuestRules.MATCHES` — `title`, `type`, `max_rarity`, `level`, `reward`. Adding a fifth entry works; `QuestPath` draws however many there are |
| **Change trophies per battle** | `ArenaRules.WIN_TROPHIES` / `LOSS_TROPHIES` |
| **Add or rename an arena** | `ArenaRules.ARENAS` — a name and its trophy threshold, in ascending order |
| **Change battle payouts** | `BattleResult.WIN_COINS` / `LOSS_COINS` |
| **Change pack contents or price** | `PackRules.PACKS`; the rarity odds are the `*_SLOT` weight dictionaries above it |
| **Change the free daily coins** | `scenes/shop/shop.gd` → `DAILY_COINS`; the cooldown is `PlayerData.DAILY_PACK_COOLDOWN_SECONDS` |
| **Change starting coins / starter cards** | `PlayerData.STARTING_COINS` and `PlayerData._grant_starter_collection()` |

### Battle feel

| I want to… | Do this |
|---|---|
| **Change hold-to-read time** | `FanHand.HOLD_SECONDS` (1.2 s) |
| **Make cards easier/harder to drag** | `FanHand.DRAG_THRESHOLD` (pixels before a press becomes a drag) |
| **Change the hand's fan shape** | `FanHand.MAX_SPREAD` (tilt), `ARC_DEPTH` (curve), `MAX_STEP` (spacing), `HOVER_LIFT`, `CARD_SCALE` |
| **Speed up or slow down the AI's turn** | `scenes/battle/battle.gd` → `AI_ACTION_DELAY`, `ATTACK_SETTLE_DELAY` |
| **Change how long a notice stays up** | `BattleFx.NOTICE_SECONDS` |
| **Change the coin toss** | `CoinFlip.SPIN_TIME`, `HALF_TURNS`, `ARC_HEIGHT`, `HOLD_TIME`; the faces are `_draw_claw()` and `_draw_bone()` |
| **Move the deck/discard piles** | `BattlePiles.PILE_X`, `DECK_DEPTH`, `USED_DEPTH` |
| **Move the board slots** | `BoardSlots.transform_for()` — the one place that decides where a card stands. The board rendering and the drop tests both ask it, so they cannot disagree |
| **Change slot highlight strength** | `BoardSlots.ALPHA` (`[OFF, LEGAL, ARMED]`) |
| **Change the camera** | The `Camera3D` node in `battle.tscn` is the resting pose; `BattleFx` captures it at `setup()` and returns to it. Bench framing is `battle.gd` → `BENCH_FOCUS` + `BENCH_FOCUS_DISTANCE` |
| **Change card size on the table** | `Card3D.WIDTH` / `HEIGHT`; `BoardSlots` and `CardPile3D` size themselves from these |

### Look and layout

| I want to… | Do this |
|---|---|
| **Recolour the whole app** | `MenuStyle` — `ACCENT`, `PANEL`, `PANEL_SOFT`, `EDGE`, `TEXT`, `BG_TOP`/`BG_BOTTOM` |
| **Recolour cards** | `CardStyle` — `TYPE_COLORS` (per dinosaur type), `RARITY_COLORS`, `SURFACE`, `GOLD` |
| **Change a card's layout** | `CardFace._rebuild()`. Every card in the game is drawn by this one function |
| **Change button or panel styling** | `MenuStyle.style_button()`, `style_tab()`, `style_pill()`, `panel()` |
| **Change the tab bar** | `NavBar.TABS` — screen name, label and icon per tab. Add an entry and a `SceneRouter.SCREENS` route and the bar builds itself |
| **Add a tab-bar icon** | Add a constant to `NavIcon`, then a branch in its `_draw()` |
| **Reposition anything on a screen** | Open the `.tscn` in the editor and move the node. Scripts address nodes by unique name (`%Thing`), so layout changes never break them |
| **Change the window size** | `project.godot` → `display/window/size/viewport_width` and `viewport_height`. The UI is anchored and reflows; the battle table is checked at both 16:9 and 4:3 |

### Structure

| I want to… | Do this |
|---|---|
| **Add a screen** | Create `scenes/<area>/<name>.tscn` + `.gd`, add it to `SceneRouter.SCREENS`, and route to it with `SceneRouter.go_to("<name>")`. Add it to `TAB_SCREENS` only if it belongs to the bottom bar |
| **Add a persisted profile field** | Add the `var` to `PlayerData`, save it in `save_game()`, read it in `load_game()` with a default, and bump `SAVE_VERSION`. Add a `_migrate_save()` entry only if old saves need repair |
| **Add a setting** | Add the `var` to `Settings`, a case to `set_setting()`, and a toggle in `settings.tscn` wired in `settings_menu.gd` |
| **Change the online port** | `Net.PORT`. Both players need the same build; `PLAYING_ONLINE.md` documents the port for router forwarding |
| **Add state to the online checksum** | `BattleLink.checksum()` and `_fingerprint()`. Anything both engines must agree on belongs there |

---

## Testing what you changed

Three headless scenes, no editor needed:

```sh
godot --headless --path godot res://scenes/tests/compile_check.tscn  # every script compiles
godot --headless --path godot res://scenes/tests/battle_sim.tscn     # 25 AI-vs-AI games
godot --headless --path godot res://scenes/tests/pack_sim.tscn       # 400 pack openings
```

**Run `compile_check` after any rename.** GDScript compiles a file only
when something loads it, so a dangling identifier in a branch no test walks
through will not surface until a player finds it. `gdparse` and `gdlint`
will not catch it either — they check syntax and style, not names.

`battle_sim` is the one to run after any engine or AI change: it asserts
every game terminates legally.

To test something interactively without clicking through the game, add a
temporary autoload that drives the real screens with real input events —
`get_viewport().push_input(event, true)` (the `true` matters; without it
the stretch transform remaps your coordinates). That is how every
interaction in this project was verified.

---

## Traps worth knowing

Godot behaviours that cost real debugging time here. Worth reading before
you spend the same hours.

| Trap | What actually happens |
|---|---|
| **Stale `.godot/` cache** | After pulling new files, `class_name` scripts may not register and screens fail to parse — the UI looks alive but nothing responds. Fix: Project → Reload Current Project, or delete `godot/.godot/` |
| **`flat = true` on a Button** | Skips stylebox drawing entirely. Hover styles you set are simply never drawn. Use a non-flat button with a transparent `normal` box instead |
| **Containers lay out their children** | Anything you position or size by hand must be parented to a plain `Control`, not to an `HBoxContainer`/`PanelContainer` |
| **Tween ownership** | A tween created on a node dies with that node. A damage number that outlives its card must create its tween on *itself* |
| **`Control.get_global_mouse_position()`** | Asks the display server, which returns (0, 0) with no OS pointer. Read positions off the input event instead — it always carries where it happened |
| **`_gui_input` coordinates** | Arrive in the control's own space, not the viewport's. Convert with `get_global_transform() * event.position` |
| **Typed array literals** | `Array[String]` only converts a literal at *declaration*. Assigning `[]` or a ternary later fails at runtime. Use `.clear()` + `.append()` |
| **`autowrap_mode` with no pinned width** | Inflates the control's minimum height enormously, and it silently swallows clicks meant for whatever is behind it |
| **3D picking is off by default** | `Area3D` hover and click never fire until `get_viewport().physics_object_picking = true` |
| **Tearing down a network peer in its own callback** | `peer_disconnected` is raised from inside the multiplayer poll; closing the connection there frees what the poll is still walking. Defer it (`call_deferred`) |
