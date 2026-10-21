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


# Official names (football-data.org) -> the short common names used throughout.
OFFICIAL_ALIASES = {
    # England
    "Brighton & Hove Albion": "Brighton", "Wolverhampton Wanderers": "Wolverhampton",
    "Tottenham Hotspur": "Tottenham", "West Ham United": "West Ham",
    "Leeds United": "Leeds", "Leicester City": "Leicester", "Ipswich Town": "Ipswich",
    "Luton Town": "Luton", "Sheffield United": "Sheffield United",
    # Spain
    "Club Atletico de Madrid": "Atletico Madrid", "Atletico de Madrid": "Atletico Madrid",
    "Athletic Club": "Athletic Bilbao", "Real Betis Balompie": "Real Betis",
    "Real Sociedad de Futbol": "Real Sociedad", "RC Celta de Vigo": "Celta Vigo",
    "Celta de Vigo": "Celta Vigo", "Rayo Vallecano de Madrid": "Rayo Vallecano",
    "RCD Espanyol de Barcelona": "Espanyol", "Espanyol de Barcelona": "Espanyol",
    "Deportivo Alaves": "Alaves", "Real Valladolid CF": "Real Valladolid",
    "CD Leganes": "Leganes", "UD Las Palmas": "Las Palmas", "Cadiz CF": "Cadiz",
    "Granada CF": "Granada", "UD Almeria": "Almeria",
    # Italy
    "FC Internazionale Milano": "Inter Milan", "Internazionale Milano": "Inter Milan",
    "SS Lazio": "Lazio", "ACF Fiorentina": "Fiorentina", "Atalanta BC": "Atalanta",
    "Bologna FC 1909": "Bologna", "Genoa CFC": "Genoa", "US Sassuolo Calcio": "Sassuolo",
    "Hellas Verona FC": "Hellas Verona", "Parma Calcio 1913": "Parma", "Como 1907": "Como",
    "AC Pisa 1909": "Pisa", "US Cremonese": "Cremonese", "US Lecce": "Lecce",
    "AC Monza": "Monza", "US Salernitana 1919": "Salernitana", "Frosinone Calcio": "Frosinone",
    "Spezia Calcio": "Spezia", "Venezia FC": "Venezia", "Empoli FC": "Empoli",
    # Germany
    "FC Bayern Munchen": "Bayern Munich", "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "Borussia Monchengladbach": "Borussia Monchengladbach", "1. FC Koln": "Cologne",
    "VfB Stuttgart": "Stuttgart", "SC Freiburg": "Freiburg", "VfL Wolfsburg": "Wolfsburg",
    "TSG 1899 Hoffenheim": "Hoffenheim", "1. FSV Mainz 05": "Mainz 05",
    "SV Werder Bremen": "Werder Bremen", "1. FC Union Berlin": "Union Berlin",
    "FC Augsburg": "Augsburg", "1. FC Heidenheim 1846": "Heidenheim",
    "FC St. Pauli 1910": "St Pauli", "FC St. Pauli": "St Pauli", "Hamburger SV": "Hamburg",
    "VfL Bochum 1848": "Bochum", "SV Darmstadt 98": "Darmstadt", "FC Schalke 04": "Schalke 04",
    "Hertha BSC": "Hertha", "Holstein Kiel": "Holstein Kiel",
    # France
    "Paris Saint-Germain FC": "Paris Saint-Germain", "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon", "AS Monaco FC": "Monaco", "Lille OSC": "Lille",
    "LOSC Lille": "Lille", "Stade Rennais FC 1901": "Rennes", "OGC Nice": "Nice",
    "Racing Club de Lens": "Lens", "RC Lens": "Lens", "RC Strasbourg Alsace": "Strasbourg",
    "Stade Brestois 29": "Brest", "Montpellier HSC": "Montpellier", "Stade de Reims": "Reims",
    "AS Saint-Etienne": "Saint-Etienne", "AJ Auxerre": "Auxerre", "Angers SCO": "Angers",
    "Le Havre AC": "Le Havre", "Paris FC": "Paris FC", "Clermont Foot 63": "Clermont",
    "FC Lorient": "Lorient", "FC Metz": "Metz", "FC Nantes": "Nantes",
    "Toulouse FC": "Toulouse",
    # Netherlands
    "AFC Ajax": "Ajax", "PSV": "PSV", "Feyenoord Rotterdam": "Feyenoord", "AZ": "AZ Alkmaar",
    "FC Twente '65": "Twente", "FC Twente": "Twente", "FC Utrecht": "Utrecht",
    "NEC": "NEC Nijmegen", "SC Heerenveen": "Heerenveen", "Heracles Almelo": "Heracles",
    "SBV Excelsior": "Excelsior", "Willem II Tilburg": "Willem II", "FC Groningen": "Groningen",
    "FC Volendam": "Volendam", "Almere City FC": "Almere City",
    # Portugal / others seen in the Champions League
    "Sport Lisboa e Benfica": "Benfica", "Sporting Clube de Portugal": "Sporting CP",
    "FC Porto": "Porto", "Sporting Clube de Braga": "Braga", "Celtic FC": "Celtic",
    "Club Brugge KV": "Club Brugge", "FK Crvena Zvezda": "Crvena Zvezda",
    "GNK Dinamo Zagreb": "Dinamo Zagreb", "FC Red Bull Salzburg": "Salzburg",
    "BSC Young Boys": "Young Boys", "SK Sturm Graz": "Sturm Graz", "FC Shakhtar Donetsk": "Shakhtar Donetsk",
    "AC Sparta Praha": "Sparta Prague", "SK Slavia Praha": "Slavia Prague",
    "FC Kobenhavn": "Copenhagen", "Ferencvarosi TC": "Ferencvaros",
    # Turkey
    "Galatasaray SK": "Galatasaray", "Fenerbahce SK": "Fenerbahce", "Besiktas JK": "Besiktas",
    "Trabzonspor AS": "Trabzonspor", "Istanbul Basaksehir FK": "Basaksehir",
    "Basaksehir": "Basaksehir", "Buyuksehyr": "Basaksehir", "Kasimpasa SK": "Kasimpasa",
    "Konyaspor": "Konyaspor", "Sivasspor": "Sivasspor", "Antalyaspor": "Antalyaspor",
    "Gaziantep FK": "Gaziantep", "Kayserispor": "Kayserispor", "Alanyaspor": "Alanyaspor",
    "Samsunspor": "Samsunspor", "Goztepe SK": "Goztepe", "Eyupspor": "Eyupspor",
    "Goztep": "Goztepe", "Ad. Demirspor": "Adana Demirspor", "MKE Ankaragucu": "Ankaragucu",
    "Fatih Karagumruk": "Karagumruk", "Caykur Rizespor": "Rizespor",
    # Norway
    "FK Bodo/Glimt": "Bodo/Glimt", "Bodo Glimt": "Bodo/Glimt", "Molde FK": "Molde",
    "Rosenborg BK": "Rosenborg", "SK Brann": "Brann", "Viking FK": "Viking",
    "Valerenga Fotball": "Valerenga", "Lillestrom SK": "Lillestrom", "Tromso IL": "Tromso",
    "Stromsgodset IF": "Stromsgodset", "Sarpsborg 08 FF": "Sarpsborg 08",
    "Fredrikstad FK": "Fredrikstad", "Ham-Kam": "HamKam", "Odds BK": "Odd", "Odd": "Odd",
    "Sandefjord Fotball": "Sandefjord", "KFUM Oslo": "KFUM Oslo", "Kristiansund BK": "Kristiansund",
    "Hamarkameratene": "HamKam", "KFUM-Kameratene Oslo": "KFUM Oslo", "Aalesunds": "Aalesund",
}
_AFFIX_TOKENS = {"FC", "AFC", "CF", "CFC", "SK", "FK", "JK", "BK", "IL", "IF", "FF", "SC", "CD",
                 "UD", "SD", "RCD", "RC", "SAD", "AC", "AS", "SS", "SSC", "US", "ACF", "BC", "CA",
                 "OGC", "AJ", "SCO", "HSC", "SBV", "TC", "KV", "Calcio", "Fotball", "Balompie",
                 "de", "Futbol"}


# letters that don't decompose into base letter + accent
_TRANSLIT = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "ł": "l",
                           "Ł": "L", "đ": "d", "Đ": "D", "ı": "i", "œ": "oe", "Œ": "OE",
                           "þ": "th", "ð": "d"})


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s.translate(_TRANSLIT)).encode("ascii", "ignore").decode()


def clean_team_name(name: str, extra: dict[str, str] | None = None) -> str:
    """Official API name -> short common name ("FC Bayern München" ->
    "Bayern Munich", "Arsenal FC" -> "Arsenal"), consistent with the
    football-data.co.uk names after `canonical()`."""
    raw = _ascii(name).strip()
    if extra and (name in extra or raw in extra):
        return extra.get(name) or extra[raw]
    if raw in OFFICIAL_ALIASES:
        return OFFICIAL_ALIASES[raw]
    tokens = [t for t in raw.replace("1. ", "").split()
              if t not in _AFFIX_TOKENS and not (t.isdigit() and len(t) == 4 and 1850 <= int(t) <= 1950)]
    short = " ".join(tokens) or raw
    if short in OFFICIAL_ALIASES:
        return OFFICIAL_ALIASES[short]
    return canonical(short)


def _norm(s: str) -> str:
    s = _ascii(s)
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
