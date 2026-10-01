"""Team-name canonicalisation across sources + fuzzy user-input resolution."""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz, process

# variant -> canonical. Canonical names are the common full English names.
BUILTIN_ALIASES = {
    # England
    "Man City": "Manchester City", "Man Utd": "Manchester United",
    "Man United": "Manchester United", "Manchester Utd": "Manchester United",
    "Spurs": "Tottenham", "Tottenham Hotspur": "Tottenham",
    "Newcastle": "Newcastle United", "Newcastle Utd": "Newcastle United",
    "Wolves": "Wolverhampton", "Wolverhampton Wanderers": "Wolverhampton",
    "Nott'm Forest": "Nottingham Forest", "Nottm Forest": "Nottingham Forest",
    "Brighton & Hove Albion": "Brighton", "Brighton and Hove Albion": "Brighton",
    "West Ham United": "West Ham", "Sheffield Utd": "Sheffield United",
    "Leicester City": "Leicester", "Leeds United": "Leeds",
    "AFC Bournemouth": "Bournemouth", "Ipswich Town": "Ipswich",
    "Luton Town": "Luton",
    # Spain
    "Ath Madrid": "Atletico Madrid", "Atlético Madrid": "Atletico Madrid",
    "Atletico de Madrid": "Atletico Madrid", "Ath Bilbao": "Athletic Bilbao",
    "Athletic Club": "Athletic Bilbao", "Betis": "Real Betis",
    "Sociedad": "Real Sociedad", "Celta": "Celta Vigo", "Vallecano": "Rayo Vallecano",
    "Espanol": "Espanyol", "Alaves": "Alaves", "Deportivo Alaves": "Alaves",
    "Barca": "Barcelona", "FC Barcelona": "Barcelona", "Real": "Real Madrid",
    # Italy
    "Inter": "Inter Milan", "Internazionale": "Inter Milan", "Milan": "AC Milan",
    "Roma": "AS Roma", "Napoli": "Napoli", "Verona": "Hellas Verona",
    "Parma Calcio 1913": "Parma",
    # Germany
    "Bayern Munich": "Bayern Munich", "Bayern": "Bayern Munich",
    "FC Bayern Munich": "Bayern Munich", "Dortmund": "Borussia Dortmund",
    "M'gladbach": "Borussia Monchengladbach", "Gladbach": "Borussia Monchengladbach",
    "Borussia M.Gladbach": "Borussia Monchengladbach", "Leverkusen": "Bayer Leverkusen",
    "RB Leipzig": "RB Leipzig", "Leipzig": "RB Leipzig",
    "Ein Frankfurt": "Eintracht Frankfurt", "FC Koln": "Cologne", "Koln": "Cologne",
    "Mainz": "Mainz 05", "Hoffenheim": "Hoffenheim", "Stuttgart": "Stuttgart",
    # France
    "Paris SG": "Paris Saint-Germain", "PSG": "Paris Saint-Germain",
    "Paris Saint Germain": "Paris Saint-Germain", "Marseille": "Marseille",
    "St Etienne": "Saint-Etienne", "Lyon": "Lyon",
    # Netherlands / Portugal
    "PSV Eindhoven": "PSV", "Ajax Amsterdam": "Ajax", "Feyenoord Rotterdam": "Feyenoord",
    "Sp Lisbon": "Sporting CP", "Sporting": "Sporting CP", "Sporting Lisbon": "Sporting CP",
    "Benfica": "Benfica", "FC Porto": "Porto", "Sp Braga": "Braga",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


_NORM_ALIASES = {_norm(k): v for k, v in BUILTIN_ALIASES.items()}


def canonical(name: str, extra: dict[str, str] | None = None) -> str:
    """Map a source-specific spelling to the canonical name."""
    name = name.strip()
    if extra and name in extra:
        return extra[name]
    return BUILTIN_ALIASES.get(name) or _NORM_ALIASES.get(_norm(name)) or name


class TeamNameError(ValueError):
    pass


class NameResolver:
    """Resolve free-text user input ('man city', 'Barca') to a known team."""

    def __init__(self, known_teams: list[str], extra_aliases: dict[str, str] | None = None):
        self.known = sorted(set(known_teams))
        self._norm_known = {_norm(t): t for t in self.known}
        self.aliases = {**BUILTIN_ALIASES, **(extra_aliases or {})}

    def resolve(self, text: str) -> str:
        if text in self.known:
            return text
        n = _norm(text)
        if n in self._norm_known:
            return self._norm_known[n]
        alias = canonical(text, self.aliases)
        if alias in self.known:
            return alias
        best = process.extractOne(n, list(self._norm_known), scorer=fuzz.WRatio)
        if best and best[1] >= 85:
            return self._norm_known[best[0]]
        sugg = process.extract(n, list(self._norm_known), scorer=fuzz.WRatio, limit=3)
        raise TeamNameError(
            f"unknown team '{text}'. Did you mean: "
            + ", ".join(self._norm_known[s[0]] for s in sugg) + "?")
