#!/usr/bin/env python3
"""Creature scraper + card generator for the Primordia Godot project.

Scrapes every land creature from the Jurassic World: The Game wiki
(https://jurassic-world-the-mobile-game.fandom.com/wiki/List_of_All_Creatures),
downloads its art, and regenerates the Godot card database:

  1. godot/database/creatures.json   — scraped identities
     [{id, name, type, rarity, image, description}, ...]
  2. godot/assets/textures/cards/    — one resized PNG per creature
  3. godot/database/cards.json       — the "dinos" section is regenerated
     from the creatures with deterministic battle stats (same algorithm as
     the original web prototype, so stats never shift between reruns);
     trainers/fields/instincts in the file are preserved untouched.

Usage:
    python tools/jurassic_scraper.py [--force] [--limit N] [--skip-images]

Properties: skips duplicates, retries failed downloads with backoff, resumes
interrupted runs (existing images are kept unless --force), sanitizes
filenames, prints progress, and is safe to rerun whenever the wiki updates.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image

WIKI_BASE = "https://jurassic-world-the-mobile-game.fandom.com"
LIST_URL = f"{WIKI_BASE}/wiki/List_of_All_Creatures"
USER_AGENT = "PrimordiaScraper/2.0 (personal fan project)"

REPO_ROOT = Path(__file__).resolve().parent.parent
CREATURES_JSON = REPO_ROOT / "godot" / "database" / "creatures.json"
CARDS_JSON = REPO_ROOT / "godot" / "database" / "cards.json"
IMAGES_DIR = REPO_ROOT / "godot" / "assets" / "textures" / "cards"

IMAGE_MAX_SIZE = 512
MIN_EXPECTED_CREATURES = 50

# The four game types; list-page section headings and infobox values map here.
GAME_TYPES = ("carnivore", "herbivore", "pterosaur", "amphibian")

# Wiki rarity ladder -> game rarity. Special tiers become mythic.
RARITY_MAP = {
    "common": "common",
    "rare": "rare",
    "super rare": "epic",
    "super-rare": "epic",
    "legendary": "legendary",
    "tournament": "mythic",
    "tournament legendary": "mythic",
    "vip": "mythic",
    "boss": "mythic",
}

# ──────────────────────────────────────────────────────────────────────
# Pure helpers (unit-tested in test_jurassic_scraper.py)
# ──────────────────────────────────────────────────────────────────────


def slugify(name: str) -> str:
    """Sanitize a creature name into a stable id / filename."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


def normalize_type(raw: str) -> str | None:
    cleaned = raw.strip().lower().rstrip("s")  # "Carnivores" -> "carnivore"
    return cleaned if cleaned in GAME_TYPES else None


def map_rarity(raw: str) -> str | None:
    return RARITY_MAP.get(raw.strip().lower())


def tidy_description(text: str, max_length: int = 280) -> str:
    """Collapse whitespace; cut long text at a sentence, else a word boundary."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_length:
        return text
    cut = text[:max_length]
    sentence_end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if sentence_end > max_length * 0.4:
        return cut[: sentence_end + 1]
    return cut[: cut.rfind(" ")] + "…"


def original_image_url(src: str) -> str:
    """Fandom thumbnails append /revision/... — strip it for the original."""
    return src.split("/revision/")[0]


# ──────────────────────────────────────────────────────────────────────
# Deterministic stat generation — exact port of the web prototype's
# generator (src/game/rng.ts + src/game/cardgen.ts). The parity test
# verifies the two implementations produce identical cards.
# ──────────────────────────────────────────────────────────────────────

_U32 = 0xFFFFFFFF


def fnv1a(text: str) -> int:
    """FNV-1a 32-bit hash, matching the JS implementation bit-for-bit."""
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch) & _U32
        h = (h * 0x01000193) & _U32
    return h


def mulberry32(seed: int):
    """Mulberry32 PRNG yielding floats in [0, 1), matching the JS version."""
    state = seed & _U32

    def next_float() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & _U32
        t = ((state ^ (state >> 15)) * (state | 1)) & _U32
        t = ((t + ((t ^ (t >> 7)) * (t | 61) & _U32)) & _U32) ^ t
        return ((t ^ (t >> 14)) & _U32) / 4294967296

    return next_float


class Rng:
    """Seeded RNG with the same int/pick semantics as the web prototype."""

    def __init__(self, seed: str) -> None:
        self._next = mulberry32(fnv1a(seed))

    def next(self) -> float:
        return self._next()

    def int(self, low: int, high: int) -> int:
        return low + int(self.next() * (high - low + 1))

    def pick(self, items: list):
        return items[self.int(0, len(items) - 1)]


HP_RANGE = {
    "common": (60, 80),
    "rare": (80, 110),
    "epic": (110, 140),
    "legendary": (140, 170),
    "mythic": (170, 200),
}

DAMAGE_FACTOR = 0.45

ATTACK_NAMES = {
    "carnivore": ["Savage Bite", "Rending Claws", "Apex Strike", "Bone Crusher", "Blood Frenzy", "Ambush"],
    "herbivore": ["Tail Slam", "Stampede", "Horn Charge", "Thorned Hide", "Ground Shaker", "Canopy Crush"],
    "pterosaur": ["Dive Bomb", "Wing Slash", "Sky Screech", "Talon Snatch", "Gale Force", "Updraft"],
    "amphibian": ["Tidal Snap", "Swamp Ambush", "Drowning Grip", "Mud Spray", "River Rush", "Deep Lurk"],
}


def _round10(value: float) -> int:
    # JS Math.round rounds half toward +infinity; Python's round() is
    # banker's rounding, so implement JS semantics explicitly.
    import math

    return int(math.floor(value / 10 + 0.5)) * 10


def _build_attack(creature: dict, hp: int, slot: int, used_names: set) -> dict:
    rng = Rng(f"attack:{creature['id']}:{slot}")
    names = [n for n in ATTACK_NAMES[creature["type"]] if n not in used_names]
    name = rng.pick(names)
    used_names.add(name)

    pip_count = rng.int(1, 2) if slot == 0 else rng.int(2, 3)
    cost = [creature["type"]]
    for _ in range(1, pip_count):
        cost.append(creature["type"] if rng.next() < 0.5 else "neutral")

    base = hp * DAMAGE_FACTOR * (0.6 if slot == 0 else 1)
    damage = max(10, _round10(base + (rng.int(0, 2) - 1) * 10))
    return {"name": name, "cost": cost, "damage": damage}


def build_evolution_chains(creatures: list[dict]) -> dict[str, str]:
    """creature id -> id of the same-type creature one tier below."""
    by_type_tier: dict[str, list[dict]] = {}
    for creature in creatures:
        key = f"{creature['type']}:{creature.get('tier', 1)}"
        by_type_tier.setdefault(key, []).append(creature)
    for bucket in by_type_tier.values():
        bucket.sort(key=lambda c: c["id"])

    chains: dict[str, str] = {}
    for creature in creatures:
        tier = creature.get("tier", 1)
        if tier <= 1:
            continue
        candidates = by_type_tier.get(f"{creature['type']}:{tier - 1}", [])
        if not candidates:
            continue
        chains[creature["id"]] = Rng(f"evo:{creature['id']}").pick(candidates)["id"]
    return chains


def generate_dino_card(creature: dict, evolves_from: str = "") -> dict:
    """Deterministic battle stats for one creature (Godot cards.json schema)."""
    rng = Rng(f"dino:{creature['id']}")
    min_hp, max_hp = HP_RANGE[creature["rarity"]]
    tier = creature.get("tier", 1)
    stage_bonus = (min(tier, 3) - 1) * 20
    hp = _round10(rng.int(min_hp, max_hp)) + stage_bonus

    used_names: set = set()
    attack_count = rng.int(1, 2) if creature["rarity"] == "common" else 2
    attacks = [_build_attack(creature, hp, slot, used_names) for slot in range(attack_count)]

    return {
        "id": f"dino:{creature['id']}",
        "name": creature["name"],
        "type": creature["type"],
        "rarity": creature["rarity"],
        "hp": hp,
        "stage": tier,
        "evolves_from": f"dino:{evolves_from}" if evolves_from else "",
        "attacks": attacks,
        "retreat_cost": 3 if hp >= 150 else 2 if hp >= 100 else 1,
        "description": creature.get("description", ""),
        "image": creature.get("image", ""),
    }


# ──────────────────────────────────────────────────────────────────────
# HTML parsing (unit-tested against fixture HTML)
# ──────────────────────────────────────────────────────────────────────


@dataclass
class RosterEntry:
    title: str
    href: str
    type_hint: str | None  # from the list page's section heading


def parse_roster(html: str) -> list[RosterEntry]:
    """Creature links from the list page, grouped by their section heading.

    Walks the article top-to-bottom; headings switch the current section and
    wiki links under a section become roster entries. Duplicates are skipped.
    """
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".mw-parser-output") or soup
    seen: set[str] = set()
    roster: list[RosterEntry] = []
    current_type: str | None = None

    for element in content.descendants:
        if element.name in ("h2", "h3"):
            current_type = normalize_type(element.get_text(strip=True))
            continue
        if element.name != "a":
            continue
        href = element.get("href") or ""
        if not href.startswith("/wiki/"):
            continue
        if re.search(r"/wiki/(File|Category|Template|Help|User|Special)[:_]", href, re.I):
            continue
        title = (element.get("title") or element.get_text(strip=True)).strip()
        if not title or href in seen:
            continue
        seen.add(href)
        roster.append(RosterEntry(title=title, href=href, type_hint=current_type))
    return roster


@dataclass
class CreaturePage:
    dino_type: str | None = None
    rarity: str | None = None
    image_url: str | None = None
    description: str = ""
    infobox: dict = field(default_factory=dict)


def parse_creature_page(html: str) -> CreaturePage:
    """Type/rarity/image/description from a creature page's portable infobox."""
    soup = BeautifulSoup(html, "lxml")
    page = CreaturePage()

    box = soup.select_one("aside.portable-infobox")
    if box is not None:
        for item in box.select(".pi-item.pi-data"):
            label = item.select_one(".pi-data-label")
            value = item.select_one(".pi-data-value")
            if label is None or value is None:
                continue
            page.infobox[label.get_text(strip=True).lower()] = value.get_text(" ", strip=True)
        thumb = box.select_one("img")
        if thumb is not None and thumb.get("src", "").startswith("http"):
            page.image_url = original_image_url(thumb["src"])

    for key in ("class", "type", "creature type"):
        if key in page.infobox:
            page.dino_type = normalize_type(page.infobox[key])
            if page.dino_type is not None:
                break
    for key in ("rarity", "rarity level"):
        if key in page.infobox:
            page.rarity = map_rarity(page.infobox[key])
            if page.rarity is not None:
                break

    if page.image_url is None:
        og_image = soup.select_one('meta[property="og:image"]')
        if og_image is not None and og_image.get("content", "").startswith("http"):
            page.image_url = original_image_url(og_image["content"])

    content = soup.select_one(".mw-parser-output")
    if content is not None:
        for paragraph in content.find_all("p", recursive=False):
            text = paragraph.get_text(" ", strip=True)
            if len(text) > 40:
                page.description = tidy_description(text)
                break
    return page


# ──────────────────────────────────────────────────────────────────────
# Network + files
# ──────────────────────────────────────────────────────────────────────


_EGRESS_HELP = (
    "If this runs inside a restricted environment, allow "
    "jurassic-world-the-mobile-game.fandom.com and "
    "static.wikia.nocookie.net in the network policy first."
)


def fetch(session: requests.Session, url: str, attempts: int = 4) -> requests.Response:
    """GET with retry/backoff. Policy blocks (HTTP or proxy 403) fail fast."""
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 403:
                raise SystemExit(f"403 Forbidden for {url}\n{_EGRESS_HELP}")
            if response.status_code >= 500 and attempt < attempts:
                raise requests.RequestException(f"HTTP {response.status_code}")
            response.raise_for_status()
            return response
        except requests.exceptions.ProxyError as error:
            if "403" in str(error):
                raise SystemExit(f"Proxy refused the connection to {url}\n{_EGRESS_HELP}") from error
            raise
        except (requests.ConnectionError, requests.Timeout, requests.RequestException) as error:
            if attempt >= attempts:
                raise
            delay = 0.5 * 2**attempt
            print(f"    retry {attempt}/{attempts - 1} in {delay:.1f}s: {error}")
            time.sleep(delay)
    raise AssertionError("unreachable")


def download_image(session: requests.Session, url: str, dest: Path, force: bool) -> bool:
    """Download, convert to PNG and fit inside 512x512. True if written/kept."""
    if dest.exists() and not force:
        return True
    response = fetch(session, url)
    image = Image.open(BytesIO(response.content))
    image = image.convert("RGBA")
    image.thumbnail((IMAGE_MAX_SIZE, IMAGE_MAX_SIZE), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, "PNG", optimize=True)
    return True


def regenerate_cards_json(creatures: list[dict]) -> None:
    """Rebuild the dinos section of cards.json; keep authored cards intact."""
    catalog = {"version": 1, "dinos": [], "trainers": [], "fields": [], "instincts": []}
    if CARDS_JSON.exists():
        catalog.update(json.loads(CARDS_JSON.read_text()))
    chains = build_evolution_chains(creatures)
    catalog["dinos"] = [
        generate_dino_card(creature, chains.get(creature["id"], "")) for creature in creatures
    ]
    CARDS_JSON.write_text(json.dumps(catalog, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download existing images")
    parser.add_argument("--limit", type=int, default=0, help="only process first N creatures (testing)")
    parser.add_argument("--skip-images", action="store_true", help="metadata only, no image downloads")
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    print(f"Fetching roster from {LIST_URL}")
    roster = parse_roster(fetch(session, LIST_URL).text)
    print(f"  {len(roster)} linked pages found")
    if args.limit > 0:
        roster = roster[: args.limit]

    creatures: list[dict] = []
    skipped: list[str] = []
    seen_ids: set[str] = set()

    for index, entry in enumerate(roster, start=1):
        print(f"[{index}/{len(roster)}] {entry.title}")
        page = parse_creature_page(fetch(session, WIKI_BASE + entry.href).text)
        dino_type = page.dino_type or entry.type_hint
        if dino_type is None:
            skipped.append(f"{entry.title} (not one of the four land classes)")
            continue
        if page.image_url is None:
            skipped.append(f"{entry.title} (no image)")
            continue
        creature_id = slugify(entry.title)
        if not creature_id or creature_id in seen_ids:
            skipped.append(f"{entry.title} (duplicate)")
            continue
        seen_ids.add(creature_id)
        rarity = page.rarity or "common"
        if page.rarity is None and page.infobox.get("rarity"):
            print(f"    unmapped rarity '{page.infobox['rarity']}' -> common")
        creatures.append({
            "id": creature_id,
            "name": entry.title,
            "type": dino_type,
            "rarity": rarity,
            "tier": 1,
            "image": f"assets/textures/cards/{creature_id}.png",
            "description": page.description,
            "_image_url": page.image_url,
        })

    if not args.skip_images:
        print(f"Downloading art for {len(creatures)} creatures → {IMAGES_DIR}")
        failures = []
        for index, creature in enumerate(creatures, start=1):
            dest = IMAGES_DIR / f"{creature['id']}.png"
            try:
                download_image(session, creature["_image_url"], dest, args.force)
                print(f"  [{index}/{len(creatures)}] {dest.name}")
            except Exception as error:  # noqa: BLE001 — collect, report, fail at end
                failures.append(f"{creature['name']}: {error}")
        if failures:
            print("\n".join(f"  FAILED {f}" for f in failures))
            raise SystemExit(f"{len(failures)} image downloads failed; rerun to resume")

    for creature in creatures:
        creature.pop("_image_url", None)

    creatures.sort(key=lambda c: (c["type"], c["name"]))
    CREATURES_JSON.parent.mkdir(parents=True, exist_ok=True)
    CREATURES_JSON.write_text(json.dumps(creatures, indent=2) + "\n")
    regenerate_cards_json(creatures)

    by_type: dict[str, int] = {}
    for creature in creatures:
        by_type[creature["type"]] = by_type.get(creature["type"], 0) + 1
    print(f"\nWrote {len(creatures)} creatures → {CREATURES_JSON.relative_to(REPO_ROOT)}")
    print(f"Regenerated dinos in     → {CARDS_JSON.relative_to(REPO_ROOT)}")
    print("  by type: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items())))
    if skipped:
        print(f"  skipped {len(skipped)}:")
        for reason in skipped:
            print(f"    - {reason}")
    if len(creatures) < MIN_EXPECTED_CREATURES:
        raise SystemExit(
            f"Only {len(creatures)} creatures scraped (expected >= {MIN_EXPECTED_CREATURES}) — "
            "the wiki layout may have changed."
        )


if __name__ == "__main__":
    main()
