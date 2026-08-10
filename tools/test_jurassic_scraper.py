"""Unit tests for jurassic_scraper.py — run with: pytest tools/

Covers the pure helpers, HTML parsing against fixture markup, and — most
importantly — stat parity: the Python card generator must produce exactly
the same cards as the original TypeScript generator (tools/export-cards.ts),
verified against the committed godot/database/cards.json.
"""

import json
from pathlib import Path

from jurassic_scraper import (
    CARDS_JSON,
    Rng,
    build_evolution_chains,
    fnv1a,
    generate_dino_card,
    map_rarity,
    normalize_type,
    original_image_url,
    parse_creature_page,
    parse_roster,
    slugify,
    tidy_description,
)


# ── pure helpers ──────────────────────────────────────────────────────


def test_slugify():
    assert slugify("Tyrannosaurus rex") == "tyrannosaurus-rex"
    assert slugify("Segnosuchus (Hybrid)") == "segnosuchus-hybrid"
    assert slugify("Métriorhynchus") == "metriorhynchus"


def test_normalize_type():
    assert normalize_type("Carnivores") == "carnivore"
    assert normalize_type(" herbivore ") == "herbivore"
    assert normalize_type("Aquatic") is None
    assert normalize_type("Hybrids") is None


def test_map_rarity():
    assert map_rarity("Common") == "common"
    assert map_rarity("Super Rare") == "epic"
    assert map_rarity("VIP") == "mythic"
    assert map_rarity("Ultra Mega") is None


def test_original_image_url():
    url = "https://static.wikia.nocookie.net/x/images/a/ab/Trex.png/revision/latest?cb=1"
    assert original_image_url(url) == "https://static.wikia.nocookie.net/x/images/a/ab/Trex.png"


def test_tidy_description():
    assert tidy_description("  A  mighty\n hunter. ") == "A mighty hunter."
    long_text = "The apex predator ruled the land. " * 20
    tidied = tidy_description(long_text)
    assert len(tidied) <= 280 and tidied.endswith(".")


# ── deterministic RNG ─────────────────────────────────────────────────


def test_rng_is_deterministic_and_bounded():
    a = Rng("seed-1")
    b = Rng("seed-1")
    assert [a.next() for _ in range(5)] == [b.next() for _ in range(5)]
    r = Rng("range")
    values = {r.int(1, 3) for _ in range(500)}
    assert values == {1, 2, 3}
    assert fnv1a("a") != fnv1a("b")


# ── stat parity with the TypeScript generator ─────────────────────────


def _creatures_from_cards() -> list[dict]:
    catalog = json.loads(Path(CARDS_JSON).read_text())
    return [
        {
            "id": dino["id"].removeprefix("dino:"),
            "name": dino["name"],
            "type": dino["type"],
            "rarity": dino["rarity"],
            "tier": dino["stage"],
            "description": dino["description"],
            "image": dino["image"],
        }
        for dino in catalog["dinos"]
    ]


def test_python_generator_matches_typescript_generator_exactly():
    """The committed cards.json was produced by the TS generator; regenerating
    every dino with the Python port must be byte-identical (hp, attack names,
    costs, damage, retreat, evolution links)."""
    catalog = json.loads(Path(CARDS_JSON).read_text())
    creatures = _creatures_from_cards()
    chains = build_evolution_chains(creatures)
    assert len(creatures) >= 48
    for expected in catalog["dinos"]:
        creature = next(c for c in creatures if f"dino:{c['id']}" == expected["id"])
        actual = generate_dino_card(creature, chains.get(creature["id"], ""))
        assert actual == expected, f"stat drift on {expected['id']}"


def test_evolution_chains_link_same_type_lower_tier():
    roster = [
        {"id": "raptor-a", "type": "carnivore", "rarity": "common", "tier": 1, "name": "A"},
        {"id": "raptor-b", "type": "carnivore", "rarity": "common", "tier": 1, "name": "B"},
        {"id": "hybrid-x", "type": "carnivore", "rarity": "epic", "tier": 2, "name": "X"},
        {"id": "lonely", "type": "herbivore", "rarity": "rare", "tier": 2, "name": "L"},
    ]
    chains = build_evolution_chains(roster)
    assert chains["hybrid-x"] in ("raptor-a", "raptor-b")
    assert chains == build_evolution_chains(roster)  # deterministic
    assert "lonely" not in chains  # no tier-1 herbivore exists


# ── HTML parsing against fixtures ─────────────────────────────────────

LIST_FIXTURE = """
<div class="mw-parser-output">
  <p>Intro with an <a href="/wiki/Jurassic_World" title="Jurassic World">off-topic link</a>.</p>
  <h2><span class="mw-headline">Herbivores</span></h2>
  <table><tr>
    <td><a href="/wiki/Triceratops" title="Triceratops">Triceratops</a></td>
    <td><a href="/wiki/File:Tric.png" title="File:Tric.png">img</a></td>
  </tr><tr>
    <td><a href="/wiki/Stegosaurus" title="Stegosaurus">Stego</a></td>
  </tr></table>
  <h2><span class="mw-headline">Carnivores</span></h2>
  <ul>
    <li><a href="/wiki/Tyrannosaurus_rex" title="Tyrannosaurus rex">T. rex</a></li>
    <li><a href="/wiki/Tyrannosaurus_rex" title="Tyrannosaurus rex">T. rex again</a></li>
  </ul>
  <h2><span class="mw-headline">Trivia</span></h2>
  <p><a href="/wiki/Category:Creatures" title="Category:Creatures">cat</a></p>
</div>
"""


def test_parse_roster_groups_types_and_skips_noise():
    roster = parse_roster(LIST_FIXTURE)
    by_title = {entry.title: entry for entry in roster}
    assert by_title["Triceratops"].type_hint == "herbivore"
    assert by_title["Stegosaurus"].type_hint == "herbivore"
    assert by_title["Tyrannosaurus rex"].type_hint == "carnivore"
    assert by_title["Jurassic World"].type_hint is None  # before any heading
    titles = [entry.title for entry in roster]
    assert titles.count("Tyrannosaurus rex") == 1  # duplicates skipped
    assert not any("File:" in t or "Category:" in t for t in titles)


CREATURE_FIXTURE = """
<html><head>
  <meta property="og:image" content="https://static.wikia.nocookie.net/jw/images/T.png/revision/latest?cb=2"/>
</head><body>
<aside class="portable-infobox">
  <figure class="pi-item pi-image">
    <img src="https://static.wikia.nocookie.net/jw/images/Trex_infobox.png/revision/latest/scale-to-width/300?cb=1"/>
  </figure>
  <div class="pi-item pi-data"><h3 class="pi-data-label">Class</h3>
    <div class="pi-data-value">Carnivore</div></div>
  <div class="pi-item pi-data"><h3 class="pi-data-label">Rarity</h3>
    <div class="pi-data-value">Super Rare</div></div>
</aside>
<div class="mw-parser-output">
  <p>short</p>
  <p>Tyrannosaurus rex is a carnivore in Jurassic World: The Game, unlocked by winning battles.</p>
</div>
</body></html>
"""


def test_parse_creature_page_reads_infobox():
    page = parse_creature_page(CREATURE_FIXTURE)
    assert page.dino_type == "carnivore"
    assert page.rarity == "epic"  # Super Rare -> epic
    assert page.image_url == "https://static.wikia.nocookie.net/jw/images/Trex_infobox.png"
    assert page.description.startswith("Tyrannosaurus rex is a carnivore")


def test_parse_creature_page_falls_back_to_og_image():
    html = CREATURE_FIXTURE.replace('src="https://static.wikia.nocookie.net/jw/images/Trex_infobox.png/revision/latest/scale-to-width/300?cb=1"', 'src="data:image/gif;base64,x"')
    page = parse_creature_page(html)
    assert page.image_url == "https://static.wikia.nocookie.net/jw/images/T.png"
