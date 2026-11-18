# footypred 3.0 — four-market football prediction

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

## Use it from your browser (no terminal needed)

1. Install Python 3 from <https://www.python.org/downloads/>. On Windows,
   tick **"Add python.exe to PATH"** during setup.
2. Unzip footypred, then double-click the launcher:
   * Windows: **`start_footypred.bat`**
   * macOS: **`start_footypred.command`** (if macOS blocks it the first
     time, right-click → Open)
   * Linux: `./start_footypred.command`

   The first start installs the packages, which takes a few minutes. After
   that, the app opens at <http://127.0.0.1:8765/>. Keep the small window
   open while you use it; closing it stops the app. Double-clicking again
   while it's running just opens the page.
3. The **Data** tab walks you through the first start:
   - **Add your matches:**
     - paste your free football-data.org API key and click **Download my
       leagues**
     - or add CSV/Excel files you already have
     - or try the **demo data**
   - **Train the model**, then predict.

Everything you need afterwards is in the page:

| Tab | What you do there |
|---|---|
| **Schedule** | Today's matches, three days back and five days ahead, grouped by competition. Times are in your time zone; live games show ● LIVE, finished ones the score. Filter by team or league, show live games only, or sort **by time**. **★ Picks** puts the best pick and follow-ups under every upcoming match. Click a match to see its **league table** (both teams highlighted) and a **Full prediction** button. At the bottom, **Polymarket Optimal Combos** ranks parlays of the day's picks. |
| **Predict** | Pick league, teams, date and competition. You get the four markets, the best pick, past-match evidence and the analysis dashboard. |
| **From image** | Drop a screenshot of fixtures, then predict them all. |
| **Backtest** | Pick a date range with the slider. The system trains on matches before the start and predicts each day after it. You get hit rates, profit, charts and a CSV. |
| **Model report** | Out-of-sample evaluation of the current model. |
| **Data** | Your match file, plus everything below. |

The bar under the tabs switches between **Balanced** (the model as before)
and **High stake**. High stake mode only picks at odds of 1.70 and up, and
its slider sets how much American owners and betting sponsors move a match.
See [High stake mode](#high-stake-mode-odds-170-owner--sponsor-factor). Those
clubs get a red ⚠ alert in Schedule, Predict and From image.

The **Data** tab has these sections:
- **Your match file:** the file and its leagues, **Update from
  football-data.org** (adds the latest matches), **Reload from file**, and
  rebuild from scratch.
- **Model:** **Train model** (quick: 3 models, a few minutes; full: all 8),
  with a live log. A note tells you when retraining is worth it, e.g.
  after adding leagues.
- **Süper Lig + Eliteserien:** builds both leagues from football-data.co.uk
  files (or downloads them) and adds them to your file.
- **Add matches from other CSV files:** merge any CSV or Excel file on
  your PC; only matches not in your file yet are added.
- **Team names:** finds names that look like the same club; one click
  merges them.
- **Settings:** API key, where your match file lives, first season. Saved
  on your PC in `config/local.yaml`, which is never committed.

Long jobs (download, update, training, backtests) run in the background
with a progress bar. If you reload the page, it picks the running job up
again. `python -m footypred` also opens the app. The terminal commands
below still exist, for scripting and scheduled tasks.

## Schedule

The schedule comes from football-data.org. One call fetches every match of
your API competitions in the window, played or not, with kick-off time,
live status, score and crest. It is refreshed when you open the Schedule
tab (if it's older than 30 minutes), when you click ↻, every 5 minutes
while a match is live, and with every **Update**.

Süper Lig and Eliteserien aren't in the API's free plan. Their upcoming
matches come from football-data.co.uk's weekly fixture lists (`fixtures.csv`
and `new_league_fixtures.csv`), including pre-match odds, and their recent
results come from your match file. Without an API key, every league is
covered that way, except the Champions League. The window is saved as
`fixtures.csv` next to your match file. It is kept apart from the match
file, which only ever holds finished results.

Teams with no matches in your data (e.g. a Champions League club from a
league you don't follow) are shown greyed out; they can't be predicted.

**League table under a match.** Click a match and its league's current
table opens below it: position, team, played, won, drawn, lost, goal
difference and points, with both teams highlighted. A line above the table
gives their places, e.g. "Chelsea: 3rd · 24 pts (12 played)". The table is
built from your results, including finished games the schedule has
fetched but your match file doesn't have yet, so it works offline and for
every league you follow. Points are 3 / 1 / 0, then the league's tie-break:

- goal difference, then goals scored: most leagues
- head-to-head first: La Liga, Serie A and Süper Lig

Points deductions aren't in the results, so add them in
`config/local.yaml` (`standings.deductions: {E0: {2026: {Everton: 10}}}`).
A Champions League match shows the league-phase table (from 2024-25).
Other cup matches show each team's domestic table. **Full prediction**
opens the match in the Predict tab.

## High stake mode (odds 1.70+, owner & sponsor factor)

The bar at the top of the page switches between two modes:

* **Balanced:** the standard picks.
* **High stake:** the same page, but every pick pays 1.70 or more. Match
  result, handicap and BTTS + over 2.5 come first.

The mode applies to Schedule, Predict, From image and Backtest, and the
browser remembers it. Model report and Data don't use it, so the bar hides
on those tabs.

In high stake mode:
- **Pick styles** become Safe (43%+ chance), Balanced (31%+) and Bold
  (17%+). Safe and Balanced pay 1.70+ and Bold pays 2.20+. Min odds can't be
  set below 1.70.
- **Two new markets** join the picks:
  - Handicap +0.5 / +1.5 for either side (+0.5 = win or draw, +1.5 = doesn't
    lose by two or more).
  - BTTS + over 2.5 (both teams score and there are 3+ goals).
- **Order:** match result, handicap and the combo are picked first. Total
  goals, BTTS and team goals still appear when their odds are 1.70 or more.
- **Extra cards:** a *High stake adjustment* card shows the 1X2 before and
  after the factor, with each team's upset record. A *Handicap & BTTS +
  over 2.5* card shows the new markets.

### The owner & sponsor factor (the slider)

Two kinds of club are flagged:
- clubs with an American owner (majority, joint or largest investor)
- clubs with a betting-company sponsor, on or off the shirt

They get a red ⚠ alert in either mode:
- **Predict:** the owner and sponsor names, under the headline.
- **Schedule and From image:** a short line, e.g. "Chelsea: American
  owner + betting sponsor". Hover over it for the names.

In high stake mode, the slider (0–100%) sets how much those flags move a
match:

1. Each team's last 40 matches are compared with what pre-match Elo
   ratings expected:
   - how often it failed to win as the favourite
   - how often it avoided defeat as the underdog

   Small samples are pulled towards "as expected".
2. The match's **upset ratio** combines the favourite's record with the
   underdog's. 1.00 means as many upsets as expected; the ratio is kept
   between 0.5 and 2.
3. The favourite's chance of not winning is multiplied by
   `1 + slider × flag weight × (upset ratio − 1)`. Each flag adds 0.5 to
   the weight, up to 1. A flag is an American owner or a betting sponsor,
   on either club.
4. Every scoreline is reweighted to match, so the handicaps, totals and
   BTTS move with it.

Example: both clubs are flagged, the slider is at 100% and the upset ratio
is 1.25. A favourite with a 46% chance of not winning goes to 57.5%.

If the teams have had *fewer* upsets than expected (ratio below 1), the
favourite gets stronger instead. At 0%, or when neither club is flagged,
nothing changes.

The analyses of your match file found no evidence that these clubs have
more upsets than their ratings expect. The factor is your own assumption,
so the slider starts at 0%.

**Test it with a backtest.** Set the mode and slider, then run a backtest
(Backtest tab, or `footy backtest --mode high --factor 33`). Each match
gets the factor as it would have on the day: upset records use earlier
matches only. The result compares the model with and without the factor
on the same matches (accuracy, log loss, Brier score). It also shows how
often the favourite failed to win against what each version expected.
Picks are the high stake ones.

### The club list: `config/club_flags.csv`

Each club is one row with these columns:

`team,league,american_owner,owner_stake,owner_since,betting_sponsor,sponsor_deal,sponsor_season,note`

- `owner_stake`: only `majority`, `joint` or `largest investor` count.
  Anything else (`minority`, `pending`) is listed but doesn't count.
- `betting_sponsor`: any name counts. Leave it empty if there is none.
- `sponsor_season`: if a deal is from an earlier season, the alert shows
  that season, e.g. "(shirt, 2025-26)".
- `team`: the name has to match your data exactly, ignoring case and
  accents, or through a known alias. Names are never fuzzy-matched, so a
  typo can't put an alert on the wrong club.
- Rows whose team starts with `#` are skipped.

The list was researched in November 2026, and owners and sponsors change.
To change it, edit the file in a spreadsheet app or text editor and
restart the app.

A new download of the app replaces this file, so keep a copy of your
edits. You can also point `high_stake.flags_file` in `config/local.yaml`
at your own copy.

## First half (1X2, over/under, BTTS)

Every prediction also covers the first 45 minutes:
- the half-time result (home / draw / away)
- first-half goals over/under 0.5, 1.5 and 2.5
- first-half BTTS
- each team scoring before the break
- expected goals and the most likely half-time scores

It appears as a **First half** card in Predict and as a column in From
image. You also get a section in `footy predict` and columns in the
walk-forward backtest CSV, and the Backtest tab and Model report show how
it scored.

It's a separate model, trained when you click **Train** (about 10 seconds
extra), on the same pre-match features and the same out-of-sample folds.
Three candidates compete, each tested only on seasons it wasn't fitted on:

* **scaled:** the full-time model's expected goals turned into first-half
  rates (`log λ_HT = a + b·log λ_FT + c·log λ_FT(opponent)`), fitted on
  half-time scores, with a low-score adjustment because first halves
  often end 0-0. It stays consistent with the full-time prediction: fewer
  goals, less BTTS.
* Dixon-Coles and Poisson regression fitted directly on half-time scores.
* a 50/50 blend of the best two.

The best one is kept. In testing, the scaled model won and every
first-half market beat its base rate, with calibration errors of about
0.5–2%. First halves are harder to call than full matches (skill about
+0.01 against about +0.035 for full time), so expect smaller edges.

Matches without a half-time score are left out of this model only.
football-data.co.uk's Eliteserien file has none; first-half predictions
for Eliteserien come from the full-time model's expected goals. Switch it
off with `training.halftime: false`.

**First-half picks** are opt-in. Tick **1st half** under "Best pick from"
(or pass `--markets ...,first_half`) and these join the best pick,
follow-ups and leans:
- HT result
- HT over/under 0.5 and 1.5
- HT BTTS yes/no

Their form evidence is counted on half-time scores, e.g. "2 of last 5
home games had 1+ goals before half-time". The Over / Under boxes apply to
them too.

## Follow-up picks

Every prediction (Predict, From image, Schedule, and `footy predict`)
lists, after the best pick:

* **Follow-up picks:** up to four more selections, taken from different
  markets first (match result, total goals, BTTS, each team's goals), then
  the next most likely. They pass the same rule as the best pick (see
  below).
* **Leans:** when fewer selections pass (or none does, so there's no clear
  pick), the list is topped up with the closest misses. Each is marked
  *lean* with what it missed: "chance below this style's threshold" or
  "odds below this style's minimum". None is offered below a 40% chance
  (25% in high stake mode).
* **By style:** the best pick under each of Safe, Balanced and Bold, so you
  can see the safer and the bolder option side by side.

## Best pick: probability decides, last-5 form is evidence

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
over/under 1.5, 2.5 and 3.5) gets a form rate: how often it landed in
those games. Games against similar opponents count most, then the venue
that matches the fixture. The form rate is **evidence**: it is shown with
every pick but decides nothing.

**What counts as a pick (3.0): probability, nothing else.**

```
valid  =  model probability >= the style's threshold
          OR  EV = probability x market odds - 1  >  min_edge (default 0)
              (where the selection has a market price, e.g. on Polymarket)
```

There's no upper odds limit: a long price never drops a pick. A
selection the model rates 40% that Polymarket pays 3.50 on (EV +40%) is a
pick even in a style that asks for 45%. The form rate and the league's
typical rate no longer gate anything. Valid picks are **ranked by model
probability**; high stake mode puts the match result, handicaps and the
combo first.

| Pick style | Chance needed | Shortest price taken |
|---|---|---|
| safe | 60% | 1.15 |
| **balanced** (default) | 45% | 1.25 |
| bold | 30% | 1.60 |
| high stake safe / balanced / bold | 43% / 31% / 17% | 1.70 / 1.70 / 2.20 |

The shortest price is a payout floor, not a quality rule. It keeps
near-certainties (e.g. 1.05 lines) out. With a market price, it applies to
that price. Because picks are ranked by probability, the best pick is
usually the likeliest selection just above the floor. Raise **Min odds**
(or choose Bold) for bigger lines.

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

Two things follow, and they are why 3.0 lets probability decide. **The
model's probability is the honest number** (picks land as often as it
says), while **raw last-5 streaks overstate**: a 5/5 streak is not 100%.
(The table above was measured with the 2.x rules: form-weighted ranking
and a 5-point "above a typical game" bar. Run `footy backtest-picks` again
to see the 3.0 picks.)

Options: `--style safe|balanced|bold`, `--markets 1x2,totals,btts,team_totals`,
`--min-prob` (the chance a pick needs), `--min-odds` (the shortest price),
`--min-edge` (EV a priced selection needs; default 0), `--no-under`,
`--no-over`. `--max-odds`, `--form-weight`, `--min-lift` and `--min-form`
are gone; old settings with them still load and the values are ignored.
The web app has a pick-style menu, market checkboxes, **Goal lines: Over
/ Under** tick boxes and a min-odds box (blank means the style decides).

## Polymarket prices and Optimal Combos

The app reads Polymarket's public prices (Gamma API, read-only, no account
or key). Each match on Polymarket is an event with Yes/No markets ("Will
Arsenal FC win?", "... end in a draw?") and sometimes totals, spreads and
BTTS. A share pays $1, so its price is a probability and the odds are
1 / price:

| Pick | Bought as | Price |
|---|---|---|
| team to win / draw | Yes | best ask |
| team +0.5 (win or draw) | No on the other team winning | 1 − best bid |
| over / under 2.5, BTTS | Over / Under, Yes / No | ask / 1 − bid |
| team +1.5 | the other side of the opponent's −1.5 | ask / 1 − bid |

Where a market has no order-book quote, the midpoint is used and marked
≈. Team goals, first-half lines and BTTS + over 2.5 aren't priced there.

**In predictions.** Predict, the Schedule's ★ Picks and From image show
each priced selection's Polymarket odds and EV = model probability × odds
− 1. A priced selection with positive EV counts as a pick (see above).
Prices are re-read at most every two minutes. When Polymarket can't be
reached, predictions carry on without them and say so.

**Polymarket Optimal Combos** (the bottom of the Schedule tab, for the
day you're looking at):

- **Legs:** a combo takes at most **one pick per match** and has **two
  legs or more**. A leg is a pick that is valid under your current style
  and mode and that Polymarket prices. Untick **+EV legs only** to also
  use valid picks with negative EV.
- **The maths:** matches are treated as independent.

  ```
  chance  = product of the legs' model probabilities
  odds    = product of the legs' Polymarket odds
  EV      = chance x odds - 1        (per 1 staked, before fees)
  ```
- **Ranking:** by EV or by probability, over *every* combo. A busy day has
  millions to trillions of them, so they aren't listed one by one. The
  objective is a product over legs, so its log is a sum. The best k
  combos with exactly l legs are then built match by match, keeping only
  the best k partial combos per leg count. That's exact: a combo whose
  partial part isn't among the best k can't be in the top k, because each
  better part could take the same remaining legs. It takes milliseconds,
  and the total count is exact too.
- **Options:** the top 50 or 100 is shown, with a **Legs** filter (2, 3,
  4, 5, 6+ or any).

Things to know before staking:
* EV compounds: if each leg's edge is a model error, the combo multiplies
  the error. Ranked by EV, long combos of small edges rise to the top.
  Their chance is small, so look at the chance column too, or rank by
  probability.
* The prices are what you could pay now (best ask), before any fees
  (`polymarket.fee`). A parlay pays the product of the odds only if you
  can actually get those prices together, e.g. by rolling winnings from
  one leg into the next, or if the platform offers that parlay.
* Polymarket isn't available everywhere. If it can't be reached from your
  network, the combos say so.

Settings: `polymarket` in `config/local.yaml`: `enabled`, `fee`,
`cache_seconds`, and `sports` to name the Polymarket sport code of a
league if the default doesn't find it. `gamma-api.polymarket.com/sports`
lists the codes.

The Over / Under boxes apply to total goals (1.5 / 2.5 / 3.5) and team
goals (0.5 / 1.5 / 2.5). With **Under** unticked, no under is picked
anywhere: not as the best pick, a follow-up, a lean or a per-style pick.
That holds in Predict, From image and the Schedule's ★ Picks. Match result
and BTTS (including BTTS No) aren't goal lines; untick those markets to
leave them out. The probabilities for every market are still shown. Your
choice is remembered in the browser. In the config it's
`picks.directions: [over]`.

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

### Süper Lig and Eliteserien: `scripts/extra_leagues.py`

For these two leagues, a script turns the raw football-data.co.uk downloads
into two clean files and can add them to your match file:

```bash
python scripts/extra_leagues.py                     # reads footballdata/super lig + footballdata/eliteserien
python scripts/extra_leagues.py --merge             # ... and adds the new matches to your match file
python scripts/extra_leagues.py --download --merge  # fetch the latest files first, then merge
python scripts/extra_leagues.py --super-lig "D:/footballdata/super lig" \
    --eliteserien D:/footballdata/eliteserien/NOR.xlsx --merge
footy train                                         # afterwards
```

* **Inputs:** Süper Lig is one file per season (`2022.csv` … `2026.csv`,
  any names). Eliteserien is football-data.co.uk's all-seasons country file
  (`NOR.csv` or `NOR.xlsx`).
* **Output:**
  - `data/extra/super_lig.csv`: every Süper Lig season combined
  - `data/extra/eliteserien.csv`: Eliteserien from 2022 on (your
    `first_season`)
  - both in the same columns as your match file
* **Cleaning:**
  - unplayed fixtures are dropped
  - awarded results are dropped: a 3-0 with no half-time score and no
    shots means no game was played (Hatayspor and Gaziantep after the 2023
    earthquake, and the walk-offs in Istanbulspor–Trabzonspor 2023 and
    Galatasaray–Adana Demirspor 2025)
  - team names get the same spelling as the API rows
  - odds fall back from Pinnacle to the market average to Bet365, row by
    row
  - football-data.co.uk's new xG columns are kept
  - Eliteserien files include the two-legged promotion/relegation play-off
    each year, which is why one second-tier club appears in each season
* **`--download`** fetches `mmz4281/{season}/T1.csv` and `new/NOR.csv`
  into the input folders. Run it with `--merge` whenever you want to catch
  up; matches already in your file are never added twice.

Excel files (`.xlsx`) work anywhere a CSV does, including `footy data merge`
(needs `openpyxl`, now in the requirements). Match files from older
versions get the two new xG columns automatically the first time something
is added to them, and the previous file is kept as `.bak`.

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
* in high stake mode (`--mode high --factor 33`, or the mode bar on the
  page): the owner & sponsor factor applied as of each match, the model
  with and without it on the same matches, and high stake picks (1.70+)

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

## Quick start (terminal)

The browser covers all of this (see the top); these commands are for
scripts and scheduled tasks.

```bash
pip install -r requirements.txt && pip install -e .
footy app                       # the web app (same as double-clicking start_footypred)
footy bootstrap                 # offline synthetic dataset (no network needed)
#   or: footy data download     # your match file from football-data.org (see above)
#   or: footy update            # scrape real data (see Data sources)
footy train                     # tune, cross-validate, select, save (~6 min; --quick: ~2)
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
* **Owner and sponsor** (3.0): two categorical features per team, one-hot
  encoded (each category is its own 0/1 column), from
  `config/club_flags.csv`:
  - owner: American majority / American joint / American largest
    investor / other / unknown
  - sponsor: betting company / none / unknown

  Owners are dated: an American takeover counts from `owner_since`, so
  Everton is "other" until December 2024. A club missing from the file is
  "other" / "none" when its league was researched, else "unknown": missing
  data stays a category of its own. Owner *names* aren't encoded: nearly
  every name is one club, so they would only be a second team identifier
  that a model overfits. The training report shows what the model made of
  these features: their share of the gradient-boosting gain and the
  Poisson GLM's coefficients. Turn them off with
  `features.club_flags: false`.

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
├── __main__.py             `python -m footypred` = the web app
├── cli.py                  footy bootstrap|update|data|train|predict|evaluate|teams|app|
│                           pick|image|backtest|backtest-picks
├── config.py, logging_utils.py
├── data/      db.py (SQLite, column-merging upserts) · http.py · names.py
│              localfile.py (your match CSV: download, update, merge, import)
│              extra_leagues.py (Süper Lig + Eliteserien from football-data.co.uk)
│              schedule.py (fixtures window for the Schedule tab)
│              synthetic.py (minute-level game-state simulator, incl. a Champions League)
│              standings.py (league tables for the Schedule's match panel)
│              pipeline.py
│              sources/ football_data_org · football_data · understat · clubelo ·
│                       transfermarkt · fifa · weather · polymarket (prices, Gamma API)
├── features/  engineering.py (replay, windows, market rates) · ratings.py · tuning.py
│              clubs.py (owner & sponsor categories, one-hot, dated)
├── models/    scorematrix.py · goal_models.py · market_head.py (direct, stacking, IPF)
│              trainer.py (nested CV, selection) · halftime.py (first-half model) ·
│              pipeline.py (train + save) ·
│              metrics.py · registry.py · summary.py
├── predict/   predictor.py · picks.py (last-5 form check, best pick, backtest)
│              highstake.py (high stake mode: club flags, upset records, the factor)
│              combos.py (Polymarket Optimal Combos: exact top-k, exact count)
│              walkforward.py (date-range backtest) · explain.py · report.py · charts.py ·
│              batch.py
├── vision/    ocr.py (RapidOCR) · fixtures.py (layout parser) · claude_reader.py · reader.py
└── ui/        web.py (local web app) · static/index.html · menu.py (terminal) ·
               service.py (predictions, data & training jobs, settings)
config/default.yaml         every tunable setting (your own: config/local.yaml, from Settings)
config/club_flags.csv       clubs with an American owner / betting sponsor (high stake mode)
start_footypred.bat         double-click launchers (Windows / macOS + Linux): install on first
start_footypred.command     run, then open the web app
scripts/extra_leagues.py    Süper Lig + Eliteserien files from football-data.co.uk
tests/                      92 tests: market identities, reconciliation, leakage,
                            state pickling/replay, DC recovery, parsers, end-to-end,
                            web API, terminal menu, past dates, packaging, form
                            windows & best pick (incl. the A/B example), backtest,
                            image layouts, OCR on a real browser screenshot,
                            Claude reader (mocked), image upload endpoint,
                            lopsided-match ladder, pick styles, older bundles,
                            football-data.org download/update (mock API), CSV
                            merge (co.uk / Excel formats, names, ±1 day), extra
                            leagues build + script (awarded results, odds fallback,
                            ISO dates, schema upgrade), setup from the browser
                            (no model/data, settings, download, train, demo, names),
                            schedule (API window, co.uk fixtures, results, time
                            zones), follow-up picks & leans, batch picks,
                            over/under tick boxes, first half (out-of-sample,
                            consistency with full time, opt-in picks, old models), file
                            import & aliases, walk-forward backtest (no look-ahead),
                            data and backtest endpoints, high stake mode (club list,
                            upset records, the factor, 1.70+ picks, handicaps,
                            BTTS + over 2.5, alerts on the schedule, backtests), 3.0: probability-
                            driven picks (+EV route, no odds cap), Polymarket parsing (mock API),
                            exact combo ranking vs brute force, league tables, owner & sponsor
                            features (dated, one-hot, unknown)
```
