"""Terminal picker: choose league -> home team -> away team from numbered
lists (or type a name), then get the full four-market report.

    footy pick
"""

from __future__ import annotations

import shutil

import pandas as pd

from footypred.data.names import NameResolver, TeamNameError
from footypred.predict.report import render


def _columns(items: list[str], width: int | None = None) -> str:
    width = width or min(shutil.get_terminal_size((100, 20)).columns, 120)
    labels = [f"{i:>3}. {t}" for i, t in enumerate(items, 1)]
    colw = max(len(s) for s in labels) + 3
    ncol = max(1, width // colw)
    nrow = -(-len(labels) // ncol)
    lines = []
    for r in range(nrow):
        lines.append("".join(labels[c * nrow + r].ljust(colw)
                             for c in range(ncol) if c * nrow + r < len(labels)))
    return "\n".join(lines)


class Menu:
    def __init__(self, service, input_fn=input, print_fn=print):
        self.svc = service
        self.ask = input_fn
        self.out = print_fn

    def _choose(self, prompt: str, items: list[str], default: int | None = None,
                resolver: NameResolver | None = None) -> int:
        """Return the 0-based index chosen by number or (fuzzy) name."""
        while True:
            hint = f" [{default + 1}]" if default is not None else ""
            raw = self.ask(f"{prompt}{hint}: ").strip()
            if not raw and default is not None:
                return default
            if raw.lower() in ("q", "quit", "exit"):
                raise KeyboardInterrupt
            if raw.isdigit() and 1 <= int(raw) <= len(items):
                return int(raw) - 1
            if resolver is not None and raw:
                try:
                    name = resolver.resolve(raw)
                    if name in items:
                        return items.index(name)
                except TeamNameError as exc:
                    self.out(f"  {exc}")
                    continue
            matches = [i for i, s in enumerate(items) if raw.lower() and raw.lower() in s.lower()]
            if len(matches) == 1:
                return matches[0]
            self.out(f"  please enter a number 1-{len(items)}" + (" or a name" if resolver else ""))

    def _pick_league(self, prompt: str, default: int | None = None) -> str:
        leagues = self.svc.leagues()
        labels = [f"{l['name']}" + (f" ({l['country']})" if l["country"] else "") +
                  f" · {l['teams']} teams" for l in leagues]
        self.out(_columns(labels))
        return leagues[self._choose(prompt, labels, default)]["code"]

    def _pick_team(self, prompt: str, league: str, exclude: str | None = None) -> str:
        teams = [t for t in self.svc.teams(league) if t != exclude]
        self.out(_columns(teams))
        return teams[self._choose(prompt, teams, resolver=NameResolver(teams))]

    def run_once(self) -> None:
        codes = [l["code"] for l in self.svc.leagues()]
        self.out("\n── Home team ─────────────────────────────")
        hl = self._pick_league("League")
        home = self._pick_team("Home team (number or name)", hl)
        self.out("\n── Away team ─────────────────────────────")
        al_raw = self.ask(f"Away league: Enter = same ({self.svc.league_name(hl)}), "
                          "or 'l' to list leagues: ").strip().lower()
        al = hl if al_raw in ("", "s", "same") else self._pick_league("League", codes.index(hl))
        away = self._pick_team("Away team (number or name)", al, exclude=home)
        today = str(pd.Timestamp.today().date())
        date = self.ask(f"Match date YYYY-MM-DD [{today}]: ").strip() or today
        neutral = self.ask("Neutral venue? [y/N]: ").strip().lower() in ("y", "yes")
        self.out("\nPredicting …\n")
        pred, _ = self.svc.predict(home, away, date, neutral, chart=False)
        self.out(render(pred))
        if self.ask("\nSave the analysis dashboard PNG? [y/N]: ").strip().lower() in ("y", "yes"):
            from footypred.predict.charts import plot_prediction
            safe = lambda s: "".join(c if c.isalnum() else "_" for c in s)
            path = (self.svc.cfg.paths.data_dir / "charts" /
                    f"{safe(pred.home)}_vs_{safe(pred.away)}_{pred.date}.png")
            self.out(f"Chart saved: {plot_prediction(pred, path)}")

    def run(self) -> None:
        self.out("footypred — pick a fixture (type q to quit at any prompt)")
        try:
            while True:
                try:
                    self.run_once()
                except (TeamNameError, ValueError) as exc:
                    self.out(f"Error: {exc}")
                if self.ask("\nAnother fixture? [Y/n]: ").strip().lower() in ("n", "no", "q"):
                    break
        except (KeyboardInterrupt, EOFError):
            self.out("\nbye")
