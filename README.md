# footypred 2.4.1 — four-market football prediction

Offline football prediction built around four markets, driven by each
team's past match details:

| Market | Output |
|---|---|
| **1X2** | home / draw / away probabilities, fair odds, pick + strength |
| **Total goals Over/Under** | 2.5 (main line), plus 1.5 and 3.5 |
| **Team goals Over/Under 0.5 · 1.5 · 2.5** | per team, all three lines |
| **Both teams to score** | yes / no |

All of these come from one joint score distribution. The probabilities are
therefore always consistent with each other: BTTS can never exceed either
team's chance of scoring, Over 2.5 agrees with both team totals, and so on.

## Best pick from last-5 form

For every fixture the system looks at:
* each team's **last 5 matches**
* each team's **last 5 home games** and **last 5 away games**
* each team's **last 5 games against opponents rated like this opponent**
  (Elo at the time of each game, within ±80, widened to ±160)
* the **last 5 head-to-head meetings**

In each window it counts scored 1+/2+/3+, conceded 1+/2+/3+, clean sheets,
failed to score, BTTS, over 2.5 and W-D-L. It also writes plain-language
profiles for each team, e.g. "Arsenal at home: scores often (4/5), keeps
clean sheets (3/5)".

Every selection in the four markets (23 in total, including total goals
over/under 1.5, 2.5 and 3.5) is then scored by how often it landed in
those games. Games against similar opponents count most, then the venue
that matches the fixture (the home team's home games and the away team's
away games). The **best pick** is the selection that recent form supports
most, using the model probability as a sanity check:

```
score = 0.6 × form rate + 0.4 × model probability        (form_weight, configurable)
eligible only if  fair odds are inside the pick style's range,
                  form and model clear the style's minimums,
                  and it is ≥ 5 points above a typical game in that league
```

| Pick style | Fair odds | Min model | Min form |
|---|---|---|---|
| safe | 1.15 – 1.60 | 60% | 60% |
| **balanced** (default) | 1.25 – 2.20 | 45% | 55% |
| bold | 1.60 – 3.50 | 30% | 45% |

**Lopsided matches.** When one side is a big favourite, its "safe" lines
(favourite over 0.5, underdog under 2.5) are about 1.03–1.10: not worth a
bet. These are flagged as *too short*, and the pick moves up the ladder to
over 1.5 goals, the favourite to win, the favourite over 1.5, BTTS No, or
total over 2.5. The "vs similar opponents" window makes those bigger lines
judgeable. "Bayern's last 5 home games" were mostly against average sides;
"Bayern's last 5 vs teams rated like Heidenheim" shows what happens in a
mismatch. Example (synthetic data): **PSG vs Metz**. Metz under 2.5 is 96%
at 1.04 (too short), so the best pick is **Over 1.5 goals at 1.27**, with
2+ goals in 5/5 of PSG's games vs teams like Metz and 5/5 of Metz's games
vs teams like PSG.

For example: team A scores and keeps clean sheets at home, and team B
scores and concedes both home and away. The best pick is **A over 0.5
goals**. BTTS is flagged as a conflict, because A's clean sheets cut
against B's scoring. The report also shows the best selection in each
market, and warns when form and model disagree.

**Is it accurate?** `footy backtest-picks` replays the out-of-sample
seasons. For each match it uses only games played before it plus the
model's out-of-fold probabilities, and checks whether the best pick landed.
On the synthetic data (2,982 test matches; 484 of them lopsided, with a
favourite at 62%+):

| | avg fair odds | best picks landed | model said |
|---|---|---|---|
| safe | 1.25 | 80.3% | 80.4% |
| **balanced** | 1.36 | 72.4% | 73.9% |
| bold | 1.82 | 54.4% | 55.6% |
| lopsided, old v2.2 rule | **1.18** (mostly favourite over 0.5) | 85.5% | 84.9% |
| lopsided, balanced | **1.38** (over 1.5, favourite win, underdog under 1.5, BTTS No) | 75.6% | 73.5% |
| raw last-5 rates of 80–100% | — | 82% | form said 88% |

Total over/under 1.5 and 3.5 are read off the reconciled score matrix and
are well calibrated out of sample: calibration error 1.2% and 0.5%
(O/U 2.5: 1.5%).

Two things follow. **The model's probability is the honest number** (picks
land as often as it says), while **raw last-5 streaks overstate**: a 5/5
streak is not 100%. That is why the headline figure is the model's and form
is shown as evidence. The 5-point "above typical" rule stops trivially safe
lines winning every time. Without it, "<team> under 2.5 goals" won most
fixtures. Re-run the backtest on real data after `footy update`, because
form may carry more signal there than in the synthetic world.

Options: `--style safe|balanced|bold`, `--markets 1x2,totals,btts,team_totals`,
`--min-odds`, `--max-odds`, `--form-weight` (1.0 lets form decide alone),
`--min-lift`. The web app has a pick-style menu, market checkboxes and a
min-odds box (blank means the style decides).

## Predict from a screenshot (one image, many matches)

```bash
footy image coupon.png                 # read every fixture, predict all, summary table
footy image a.png b.jpg --full         # + full report per fixture
footy image coupon.png --chart-dir out # + dashboard PNG per fixture
```

In the web app, open **From image**. Drop, paste (Ctrl/⌘+V) or choose a
screenshot. The detected fixtures appear in an editable list: fix a team,
untick a row or add one. **Predict** gives a summary table with each
fixture's best pick, and **Open** shows the full analysis.

* **Default reader: offline OCR** (RapidOCR, models bundled with the pip
  package: no network, no API key). It handles one-line fixtures
  ("Arsenal vs Chelsea", "Real Madrid - Barcelona 20:00"), two-column
  layouts with odds in between, and stacked betting-app cards (including
  team names wrapped onto two lines). It also reads date headers ("Sat 25
  Oct", "26/10", "Tomorrow") and kick-off times, and avoids reading odds
  such as "2.05" as dates or times. Team names are matched against the
  database with aliases (Man City, Barca, Inter, Wolves, Nott'm Forest …)
  and tolerate OCR slips. Tested on browser-rendered and drawn screenshots:
  16/16 fixtures, with correct dates and times.
* **Optional Claude vision reader** for screenshots OCR can't handle
  (crests instead of names, unusual layouts). Install it with
  `pip install anthropic`, sign in with an API key, then use
  `--engine claude` or the Reader dropdown. **This sends the image to
  Anthropic.** It uses `claude-opus-5-5` (set `image.claude_model` in the
  config) with structured JSON output. "Auto" only falls back to it when OCR
  finds nothing and the package is installed.
* Teams that aren't in the database are listed as "not in database"; they
  are never guessed.

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

## Your match file (football-data.org → one CSV on your PC)

The whole system can run from a single CSV on your computer. It holds
every finished match from 2022/23 to today for the Premier League, Ligue 1,
Bundesliga, La Liga, Eredivisie, Serie A, Champions League, Süper Lig and
Eliteserien.

1. Get a free API key at <https://www.football-data.org/client/register>,
   then set it as an environment variable. It is never written to the file
   or the config.
   ```bash
   export FOOTBALL_DATA_API_KEY=your-key          # Windows: setx FOOTBALL_DATA_API_KEY your-key
   ```
2. Build the file once. The free plan allows 10 requests a minute, so a full
   download takes a few minutes.
   ```bash
   footy data download --to 2026-10-20           # → data/matches.csv
   ```
3. Keep it current. This adds the matches played since the last run to the
   end of the same file; it never rebuilds the file.
   ```bash
   footy data update
   ```
   Each competition is re-checked from 3 days before its last stored match,
   which catches late results. If the source corrects a stored score, the
   file is rewritten with the fix, and the old file is kept as `matches.csv.bak`.
4. Train on it with `footy train`.

Everything reads the file directly from your disk: `footy predict`,
`footy app`, `footy backtest` and the rest. When the file changes, it is
imported again automatically, and nothing is uploaded. You can point
`local_data.csv` in `config/default.yaml` at any path, for example a
shared folder. The web app's **Data** tab shows the file, its date range
and per-competition counts, with **Reload from file** and
**Update from football-data.org** buttons.

| code | competition | football-data.org | fallback |
|---|---|---|---|
| E0 · F1 · D1 · SP1 · N1 · I1 | the five big leagues + Eredivisie | PL · FL1 · BL1 · PD · DED · SA | football-data.co.uk |
| CL | Champions League | CL | – |
| T1 | Süper Lig | looked up by area + name | football-data.co.uk `T1` |
| NOR | Eliteserien (calendar-year seasons) | looked up by area + name | football-data.co.uk `new/NOR` |

* **Plan limits:** if a competition or season isn't in your football-data.org
  plan (the API answers 403), domestic leagues are filled from
  football-data.co.uk instead. Süper Lig and Eliteserien are likely to need
  this on the free plan, and so may older seasons. The fallback also adds
  shots, corners, cards and closing odds. The output shows where every
  competition-season came from.
* **Goals are 90-minute scores.** For a cup tie decided in extra time or on
  penalties, the file keeps the 90-minute result plus `duration`,
  `home_aet` and `away_aet`. A final is marked `neutral=1`.
* **Team names** are cleaned to the short names used everywhere else
  ("FC Bayern München" → "Bayern Munich"), so a club has one name in its
  league and in the Champions League. `footy data check` lists names that
  may be the same club. To merge two names, add a `from,to` line to
  `data/aliases.csv`.
* **Champions League:** CL games never move a team out of its domestic
  league in the pickers. A fixture between teams from different leagues is
  treated as a CL match, and the **Competition** select (or
  `--competition`) overrides that.
* Other commands: `footy data info` shows matches per competition and
  season, and `footy data import [--file other.csv]` imports right away.

### Merging other CSV files (e.g. Süper Lig and Eliteserien)

If you downloaded CSVs yourself, `footy data merge` adds the matches from
them that aren't in your file yet. A typical case is Süper Lig and
Eliteserien from football-data.co.uk when the API doesn't cover them:

| competition | download from football-data.co.uk |
|---|---|
| Süper Lig | one file per season: `mmz4281/2223/T1.csv`, `2324/T1.csv`, `2425/T1.csv`, `2526/T1.csv`, `2627/T1.csv` |
| Eliteserien | one file with every season: `new/NOR.csv` |

```bash
footy data merge Downloads/T1_2526.csv Downloads/NOR.csv --dry-run   # see what would be added
footy data merge Downloads/T1_2526.csv Downloads/NOR.csv             # add them
footy data merge Downloads/footy-extra/                              # every CSV in a folder
```

* **Formats detected:**
  - a football-data.co.uk league file (with a `Div` column, e.g. T1)
  - a football-data.co.uk country file (`Country`/`Season`, e.g. NOR)
  - another footypred match file
  - any CSV with date, home, away and home/away goal columns; add
    `--competition T1` if it has no competition column
  - files saved from Excel with `;` separators and decimal commas
* **"Not in it yet":** a match counts as already present when the
  competition and both teams match and the date is within a day. One day
  of slack covers the API's UTC dates against a source's local dates.
  New matches are appended to the end of the file; nothing else changes.
* **Seasons** before `first_season` (2022/23) are skipped unless you pass
  `--all-seasons`. Unplayed fixtures are skipped too. `--to` sets the
  latest date to include.
* **Team names** are cleaned the same way as the API's names
  ("Buyuksehyr" → "Basaksehir"). Names that differ only in accents,
  punctuation or one typo are matched to the spelling already in your file
  ('Goztep' → 'Goztepe'). The report lists every new team name with its
  closest existing name, so you can spot a missed duplicate. Add it to
  `aliases.csv` and merge again.
* `--fill-missing` also fills empty odds, shots, cards and half-time scores
  on matches already in your file. This rewrites the file and keeps the
  previous version as `matches.csv.bak`.
* After merging, `footy data update` keeps those competitions current as
  well.

In the web app, the **Data** tab has the same tool under **Add matches from
other CSV files**. Paste file or folder paths from your PC (quotes are
fine), click **Preview**, then **Merge into my file**. The files are read
straight from disk, not uploaded.

Columns: `match_id, source, competition, competition_name, season, date,
kickoff, kickoff_tz, matchday, stage, status, home, away, home_raw, away_raw,
fthg, ftag, hthg, htag, duration, home_aet, away_aet, neutral, hs, as_, hst,
ast, hc, ac, hy, ay, hr, ar, odds_h, odds_d, odds_a, odds_o25, odds_u25,
fd_id, updated_at`. Your own CSV works too, as long as it has at least
`competition, season, date, home, away, fthg, ftag`.

## Backtest over a date range

```bash
footy backtest --from 2025-08-01 --to 2026-05-31
footy backtest --from 2026-01-01 --competitions E0,CL --retrain-every 30 --quick
```

The backtest rebuilds the system as it stood on the start date. Ratings
are tuned and models trained only on matches **before** `--from`. It then
steps through the range one day at a time. Each day's matches are predicted
from what was known that morning, scored against the real results, and
only then fed in, which is exactly what the live system does when new
results arrive. With `--retrain-every N`, the models are also retrained
every N days. `--quick` trains only Poisson, Dixon-Coles and LightGBM,
which is several times faster. With less than four seasons of history, the
cross-validation uses half-seasons, so a start date about a year after your
first match works.

Reported results:
* per market: log loss, skill, accuracy and calibration error, compared
  with the bookmaker's closing odds when the file has them
* how often the safe, balanced and bold best picks landed, against what
  the model claimed
* flat-stake profit at bookmaker odds for those picks and for value bets
  (model edge over 5%), where odds exist

`--competitions` limits which matches are scored. Every match still feeds
the ratings. Output: a per-match CSV (every market, every pick style, hits)
and a chart in `data/backtests/`.

In the web app, the **Backtest** tab has a date-range slider (drag either
end), presets for the last 30, 90, 180 and 365 days, competition
checkboxes and a retrain option. It runs in the background with a progress
bar and shows stat tiles, market and pick tables, the chart and a
match-by-match table, with a full CSV download.

A test checks that this is genuinely out of sample: changing every result
on a day leaves that day's predictions unchanged.

## Quick start

```bash
pip install -r requirements.txt && pip install -e .
footy bootstrap                 # offline synthetic dataset (no network needed)
#   or: footy data download     # your match file from football-data.org (see above)
#   or: footy update            # scrape real data (see Data sources)
footy train                     # tune, cross-validate, select, save (~6 min)
footy predict "Arsenal" "Chelsea"
footy predict "Man City" "Liverpool" --chart          # + 9-panel dashboard PNG
footy predict "Brazil" "Argentina" --neutral --date 2026-11-15
footy predict "Barca" "Real Madrid" --json
footy evaluate --chart          # out-of-sample report + reliability diagrams
footy teams --league E0
footy image screenshot.png      # read fixtures from an image and predict them all
footy backtest-picks            # how often best picks landed out of sample
footy backtest --from 2026-01-01 --to 2026-05-31   # walk-forward over a date range
footy data update               # add yesterday's matches to your match file
footy data merge T1.csv NOR.csv # add matches from other CSVs that aren't in your file
```

For automatic refreshes, schedule `footy data update && footy train` with
cron (or Task Scheduler on Windows).
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
* last-5 form (each team at the venue and overall), titled with the best pick
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
├── cli.py                  footy bootstrap|update|data|train|predict|evaluate|teams|app|
│                           pick|image|backtest|backtest-picks
├── config.py, logging_utils.py
├── data/      db.py (SQLite, column-merging upserts) · http.py · names.py
│              localfile.py (your match CSV: download, update, merge, import)
│              synthetic.py (minute-level game-state simulator, incl. a Champions League)
│              pipeline.py
│              sources/ football_data_org · football_data · understat · clubelo ·
│                       transfermarkt · fifa · weather
├── features/  engineering.py (replay, windows, market rates) · ratings.py · tuning.py
├── models/    scorematrix.py · goal_models.py · market_head.py (direct, stacking, IPF)
│              trainer.py (nested CV, selection) · metrics.py · registry.py · summary.py
├── predict/   predictor.py · picks.py (last-5 form check, best pick, backtest)
│              walkforward.py (date-range backtest) · explain.py · report.py · charts.py ·
│              batch.py
├── vision/    ocr.py (RapidOCR) · fixtures.py (layout parser) · claude_reader.py · reader.py
└── ui/        web.py (local web app) · static/index.html · menu.py (terminal) · service.py
config/default.yaml         every tunable setting
tests/                      47 tests: market identities, reconciliation, leakage,
                            state pickling/replay, DC recovery, parsers, end-to-end,
                            web API, terminal menu, past dates, packaging, form
                            windows & best pick (incl. the A/B example), backtest,
                            image layouts, OCR on a real browser screenshot,
                            Claude reader (mocked), image upload endpoint,
                            lopsided-match ladder, pick styles, older bundles,
                            football-data.org download/update (mock API), CSV
                            merge (co.uk / Excel formats, names, ±1 day), file
                            import & aliases, walk-forward backtest (no look-ahead),
                            data and backtest endpoints
```
