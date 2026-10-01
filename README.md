# footypred 2.1 — four-market football prediction

Offline football prediction built around four markets, driven by each
team's past match details:

| Market | Output |
|---|---|
| **1X2** | home / draw / away probabilities, fair odds, pick + strength |
| **Over/Under 2.5 goals** | over / under probabilities |
| **Team goals Over/Under 0.5 · 1.5 · 2.5** | per team, all three lines |
| **Both teams to score** | yes / no |

All of these come from one joint score distribution. The probabilities are
therefore always consistent with each other: BTTS can never exceed either
team's chance of scoring, Over 2.5 agrees with both team totals, and so on.

## Pick league and teams (interactive)

```bash
footy app        # web app at http://127.0.0.1:8765 — League + Team dropdowns
footy pick       # same in the terminal: numbered lists, or type a team name
```

The **web app** has a League and a Team dropdown for each side, so it
handles fixtures within one league and across leagues (European cups,
internationals). Set the date and neutral venue, then press **Predict**. It
shows:
* the four market cards with picks, fair odds and confidence
* most likely scores
* past-match evidence for both teams and the head-to-head record
* what moved each market
* a model comparison table
* the full analysis dashboard (downloadable PNG)

A **Model report** tab shows the out-of-sample evaluation. It runs locally
with no extra dependencies, works on phones, supports light and dark mode,
and remembers your last fixture.

## Quick start

```bash
pip install -r requirements.txt && pip install -e .
footy bootstrap                 # offline synthetic dataset (no network needed)
#   or: footy update            # scrape real data (see Data sources)
footy train                     # tune, cross-validate, select, save (~6 min)
footy predict "Arsenal" "Chelsea"
footy predict "Man City" "Liverpool" --chart          # + 9-panel dashboard PNG
footy predict "Brazil" "Argentina" --neutral --date 2026-11-15
footy predict "Barca" "Real Madrid" --json
footy evaluate --chart          # out-of-sample report + reliability diagrams
footy teams --league E0
```

For automatic refreshes, schedule `footy update && footy train` with cron.
`footy predict` uses the saved feature state and replays only results added
since training, so a prediction takes about 4 s.

## What drives the predictions: past match details

Features are built by replaying every match in date order. A fixture's
features use only matches played before its date, and the tests check this.
For each team:

* **Market-event rates**: scored 1+/2+/3+ (the team-total lines), conceded
  1+/2+/3+, BTTS rate, over-2.5 rate, win/draw rate, points per game.
* **Windows**: last 5, last 10, venue-specific (the home side's home games,
  the away side's away games), and exponentially weighted form.
* **Volume and quality**: goals, xG, and shots on target for and against;
  first-half goals.
* **Tendency beyond strength**: residuals of goals, BTTS and over-2.5 against
  what the team's rating implied before each game. These capture game
  management and tempo, which strength alone misses.
* **Totals volatility**: how widely the team's match totals swing.
* **Matchups**: e.g. the home side's scored-2+ rate combined with the away
  side's conceded-2+ rate.
* **Head-to-head**: results, BTTS and over-2.5 record, goals per game.
* **Ratings**: Elo, and online Poisson attack/defence ratings on goals and on
  xG, plus the market probabilities those ratings imply.
* **Context**: league scoring environment, rest and fixture congestion,
  ClubElo, market value, FIFA points, weather.

Every prediction prints the evidence as raw counts (e.g. "scored in 7/8
home games · BTTS 2/8 away") and the features that moved each market.

## Model pipeline

1. **Goal-rate model zoo.** Each model outputs a score matrix:
   * Dixon-Coles (time-decayed; half-life tuned by CV) and a hierarchical
     Bayesian model (empirical-Bayes partial pooling). These are refitted
     monthly during cross-validation.
   * Poisson GLM, XGBoost, LightGBM and CatBoost (Poisson objectives), a
     random forest and an MLP, all on the past-match features.
2. **Ensemble.** A mixture of the score matrices, with weights fitted to
   minimise the combined 4-market log-loss.
3. **Per-market head.** Each market gets its own calibration (fitted on
   out-of-fold predictions only). Direct classifiers trained on that
   market's outcome are stacked in only for markets where they win out of
   sample.
4. **Reconciliation.** Iterative proportional fitting adjusts the score
   matrix as little as possible (minimum KL) so it matches every market at
   once. All final probabilities, scorelines and expected goals are read
   from this one matrix.
5. **Selection.** Nested chronological CV: level 1 trains on seasons before
   *s* and tests on *s*; the level-2 head is fitted only on earlier test
   seasons. The candidate with the best combined 4-market skill (mean
   log-loss skill over 1X2, O/U 2.5, BTTS and team totals) is saved as a
   versioned bundle.

## Review & optimisation results

The v1 code was lost, so the v1 method is reproduced inside the trainer
("v1-style": 1X2-only multinomial calibration with the matrix rescaled to
it) and compared with v2 on the same 5,506 held-out matches:

| Change | Finding | Kept? |
|---|---|---|
| Per-market calibration instead of 1X2-only | Calibration error: BTTS 2.5% → 1.3%, O2.5 2.0% → 1.5%, home over 0.5 1.8% → 1.1%, away over 0.5 2.0% → 1.3%; log-loss flat or better | ✔ |
| Selection on combined 4-market skill (was 1X2 only) | Picks models that are good at all four markets | ✔ |
| Ensemble weights fitted on the 4-market objective | Best candidate (0.0318 vs 0.0317 for the best single model) | ✔ |
| Coherent reconciliation (IPF) | Costs no accuracy and guarantees consistent markets | ✔ |
| Direct market classifiers | Alone they are weaker than the goal models; per market they only help on away over 1.5. Gated per market, out of sample | ✔ (gated) |
| Stacking every model per market | Overfits (0.0310 vs 0.0321) | ✘ |
| Online rating learning rate | 0.06 was far too high. Tuned on prequential likelihood: goals 0.01, xG blend 0.03 with full xG weight (−0.02 nats/match) | ✔ (auto-tuned each `train`) |
| Dixon-Coles half-life | Grid widened and CV-tuned (best ~1000 days on synthetic data) | ✔ |
| Monthly walk-forward refits for team models | Fair, up-to-date out-of-fold scores for DC and Bayes | ✔ |
| Longer form windows (EW half-life 14/20/30) | No consistent gain | ✘ |

Bookmaker benchmark on the same matches (synthetic closing odds that know
the true scoring rates): 1X2 log-loss 1.0114 for the model vs 1.0009 for
the book; O2.5 0.6826 vs 0.6770. A gap of this size is typical for
public-data models against closing lines.

**Honest caveat:** the numbers above come from the synthetic dataset,
because the data sites are unreachable from the build environment. Run
`footy update && footy train` on a networked machine to get real-data
figures. Football outcomes are very noisy, so skill scores of a few percent
are normal and nothing here guarantees profit.

## Debugging log (v1.0.0 → v2)

| Problem | Where | Fix |
|---|---|---|
| `.gitignore` rule `data/` also matched the `footypred/data/` package, so the v1.0.0 archive had no database, scraper or updater code and failed with `ModuleNotFoundError` | v1.0.0 | — |
| Same bug in the first v2 zip (`data/` and `models/` ignored, so `footypred/data` and `footypred/models` were missing) | v2.0.0 | Rules anchored to the project root (`/data/`); a test fails if any package file is untracked |
| 1X2 calibrator fitted and scored on the same predictions, so the leaderboard was in-sample | v1 selection | Nested chronological CV: the calibration layer is only scored on later seasons |
| Ensemble weights chosen from the same scores they were judged on | v1 selection | Same nested scheme |
| Predicting a past date gave rest days of −994, which the tree models extrapolated on (+6 pts home win) | v2 features | Rest days clamped at 0 or more, congestion counts only earlier games, and a "not a fair backtest" warning |
| Cross-league fixtures silently used the home league's scoring level | v2 predictor | Now stated as a warning |
| Team-totals picks rendered as `[object HTMLSpanElement]`; low contrast on violet in dark mode | v2 web app | Fixed |
| Feature drivers showed internal codes (`P(a_o15)`, `mv`) | v2 explanations | Plain-English labels |

## Charts

`footy predict ... --chart` produces a 3×3 dashboard:
* 1X2
* O/U 2.5 and BTTS
* team goals over 0.5/1.5/2.5
* each team's goal distribution vs a Poisson fit
* total goals vs a Normal approximation, with the 2.5 line marked
* correct-score heatmap
* model divergence per market (spread plus Jensen-Shannon divergence)
* past-match evidence
* out-of-sample reliability

`footy evaluate --chart` shows skill per candidate (raw / v1-style / final),
skill and calibration error per market, and reliability diagrams.

## Data sources (`footy update`)

Every source fails on its own without stopping the others. HTTP requests are
rate-limited per host, retried with backoff and cached on disk.

* football-data.co.uk: results, half-time scores, shots, corners, cards,
  closing 1X2 and O/U 2.5 odds (odds are used only as a benchmark)
* Understat: xG
* ClubElo
* Transfermarkt (opt-in): market values
* FIFA rankings
* Open-Meteo (opt-in): weather

## Layout

```
footypred/
├── cli.py                  footy bootstrap|update|train|predict|evaluate|teams|app|pick
├── config.py, logging_utils.py
├── data/      db.py (SQLite, column-merging upserts) · http.py · names.py
│              synthetic.py (minute-level game-state simulator) · pipeline.py
│              sources/ football_data · understat · clubelo · transfermarkt · fifa · weather
├── features/  engineering.py (replay, windows, market rates) · ratings.py · tuning.py
├── models/    scorematrix.py · goal_models.py · market_head.py (direct, stacking, IPF)
│              trainer.py (nested CV, selection) · metrics.py · registry.py · summary.py
├── predict/   predictor.py · explain.py · report.py · charts.py
└── ui/        web.py (local web app) · static/index.html · menu.py (terminal) · service.py
config/default.yaml         every tunable setting
tests/                      21 tests: market identities, reconciliation, leakage,
                            state pickling/replay, DC recovery, parsers, end-to-end,
                            web API, terminal menu, past dates, packaging
```
