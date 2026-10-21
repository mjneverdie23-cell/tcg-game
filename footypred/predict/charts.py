"""Charts (matplotlib, static PNG).

plot_prediction  — 3x3 dashboard for one fixture, built around the four
                   markets plus the models and the past-match evidence:
    1X2 · O/U 2.5 & BTTS · team goals O/U 0.5-2.5
    goal PMFs vs Poisson · total goals vs Normal (2.5 line) · score heatmap
    model divergence · past-match evidence · out-of-sample reliability
plot_evaluation  — model report: candidate skill (raw / v1-style / final),
                   per-market skill, reliability diagrams per market.

Colour roles: home = blue, away = red (polarity pair), draw / "no" /
"under" = neutral gray, "yes" / "over" = violet, sequential blue ramp
for the heatmap; reliability lines use later categorical slots so they
never read as a team. Every mark carries a direct label.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from scipy.stats import norm, poisson  # noqa: E402

from footypred.logging_utils import get_logger
from footypred.models.metrics import outcomes

log = get_logger("predict.charts")

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
HOME = "#2a78d6"
HOME_DARK = "#104281"
AWAY = "#e34948"
AWAY_DARK = "#8f1f1f"
NEUTRAL = "#b5b3ac"
YES = "#4a3aa7"
SERIES = ["#1baf7a", "#eda100", "#008300", "#e87ba4"]   # categorical slots 2,3,4,7
SEQ_RAMP = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf",
            "#184f95", "#0d366b"]

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titlesize": 10.5})


def _style(ax, title, grid_axis="y"):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=10.5, fontweight="bold", loc="left", pad=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(BASELINE)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def _pct_fmt(ax, axis="y", decimals=0):
    f = lambda v, _: f"{v:.{decimals}%}"
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)


def js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence (bits) between two distributions."""
    p = np.asarray(p, float).ravel(); q = np.asarray(q, float).ravel()
    p, q = p / p.sum(), q / q.sum()
    m = 0.5 * (p + q)
    kl = lambda a, b: float(np.sum(a[a > 0] * np.log2(a[a > 0] / b[a > 0])))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def _save(fig, out):
    """Save to a path (returns the Path) or a binary file-like (returns it)."""
    try:
        if hasattr(out, "write"):
            fig.savefig(out, format="png", dpi=120, facecolor=SURFACE)
            return out
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=120, facecolor=SURFACE)
        log.info("chart saved -> %s", out)
        return out
    finally:
        plt.close(fig)


# ===================================================================== panels
def _p_1x2(ax, pred):
    o = pred.markets["1x2"]
    labels = [f"{pred.home}\nwin", "Draw", f"{pred.away}\nwin"]
    vals = [o["home"], o["draw"], o["away"]]
    bars = ax.bar(labels, vals, width=0.55, color=[HOME, NEUTRAL, AWAY], zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{100 * v:.0f}%", ha="center",
                va="bottom", fontsize=8.5, color=INK)
    ax.set_ylim(0, max(vals) * 1.25)
    _pct_fmt(ax)
    _style(ax, f"1X2  ·  confidence {pred.confidence['1x2']}/100")


def _p_ou_btts(ax, pred):
    rows = [("Over 2.5", "Under 2.5", pred.markets["over_under_2.5"]["over"]),
            ("BTTS Yes", "BTTS No", pred.markets["btts"]["yes"])]
    for y, (yes_l, no_l, p) in zip((1, 0), rows):
        ax.barh(y, p, height=0.5, color=YES, zorder=3)
        ax.barh(y, 1 - p, left=p, height=0.5, color=NEUTRAL, zorder=3,
                edgecolor=SURFACE, linewidth=2)
        ax.text(p / 2, y, f"{yes_l}\n{100 * p:.0f}%", ha="center", va="center",
                fontsize=8.5, color="#ffffff")
        ax.text(p + (1 - p) / 2, y, f"{no_l}\n{100 * (1 - p):.0f}%", ha="center",
                va="center", fontsize=8.5, color=INK)
    ax.axvline(0.5, color=INK_2, linewidth=0.8, linestyle=":", zorder=4)
    ax.set_yticks([1, 0])
    ax.set_yticklabels([f"O/U 2.5\nconf {pred.confidence['over_under_2.5']}",
                        f"BTTS\nconf {pred.confidence['btts']}"], fontsize=8, color=INK_2)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, 1.6)
    _pct_fmt(ax, "x")
    _style(ax, "Over/Under 2.5  ·  Both teams to score", grid_axis=None)


def _p_team_totals(ax, pred):
    lines = ["0.5", "1.5", "2.5"]
    x = np.arange(len(lines))
    w = 0.36
    for off, side, team, color in ((-w / 2, "home", pred.home, HOME),
                                   (w / 2, "away", pred.away, AWAY)):
        vals = [pred.markets["team_totals"][side][f"over_{l}"] for l in lines]
        ax.bar(x + off, vals, width=w - 0.04, color=color, zorder=3, label=team)
        for xi, v in zip(x + off, vals):
            ax.text(xi, v + 0.012, f"{100 * v:.0f}%", ha="center", va="bottom",
                    fontsize=8, color=INK_2)
    ax.axhline(0.5, color=INK_2, linewidth=0.8, linestyle=":", zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Over {l}" for l in lines], fontsize=8.5, color=INK_2)
    ax.set_ylim(0, 1.1)
    _pct_fmt(ax)
    ax.legend(fontsize=7.5, frameon=False, labelcolor=INK_2, loc="upper right")
    _style(ax, f"Team goals over/under  ·  confidence {pred.confidence['team_totals']}/100")


def _p_goal_pmf(ax, pred, kmax=6):
    sm = pred.score_matrix
    ks = np.arange(kmax + 1)
    ph, pa = sm.grid.sum(axis=1)[:kmax + 1], sm.grid.sum(axis=0)[:kmax + 1]
    w = 0.38
    ax.bar(ks - w / 2, ph, width=w - 0.04, color=HOME, zorder=3, label=f"{pred.home} (model)")
    ax.bar(ks + w / 2, pa, width=w - 0.04, color=AWAY, zorder=3, label=f"{pred.away} (model)")
    ax.plot(ks - w / 2, poisson.pmf(ks, sm.lam_home), "o-", color=HOME_DARK, lw=1.6, ms=4,
            zorder=4, label=f"Poisson(λ={sm.lam_home:.2f})")
    ax.plot(ks + w / 2, poisson.pmf(ks, sm.lam_away), "o--", color=AWAY_DARK, lw=1.6, ms=4,
            zorder=4, label=f"Poisson(λ={sm.lam_away:.2f})")
    for xb in (0.5, 1.5, 2.5):
        ax.axvline(xb, color=BASELINE, lw=0.7, ls=":", zorder=2)
    ax.set_xticks(ks)
    ax.set_xlabel("goals scored  (dotted: 0.5 / 1.5 / 2.5 lines)", fontsize=8, color=MUTED)
    _pct_fmt(ax)
    ax.legend(fontsize=7, frameon=False, labelcolor=INK_2)
    _style(ax, "Team goal distributions vs Poisson")


def _p_total_normal(ax, pred, kmax=8):
    sm = pred.score_matrix
    G = sm.grid.shape[0]
    tot = np.add.outer(np.arange(G), np.arange(G))
    ks = np.arange(kmax + 1)
    pt = np.array([sm.grid[tot == k].sum() for k in ks])
    ax.bar(ks, pt, width=0.7, color=[NEUTRAL if k <= 2 else YES for k in ks], zorder=3)
    mu = sm.lam_home + sm.lam_away
    sd = math.sqrt(mu)
    xs = np.linspace(-0.5, kmax + 0.5, 300)
    ax.plot(xs, norm.pdf(xs, mu, sd), color=INK, lw=1.5, ls="--", zorder=4,
            label=f"Normal(μ={mu:.2f}, σ={sd:.2f})")
    ax.axvline(2.5, color=INK_2, lw=1.0, zorder=4)
    over = pred.markets["over_under_2.5"]["over"]
    ytop = max(pt.max(), norm.pdf(mu, mu, sd)) * 1.18
    ax.text(2.42, ytop * 0.93, f"Under {100 * (1 - over):.0f}%", ha="right", fontsize=8.5, color=INK_2)
    ax.text(2.58, ytop * 0.93, f"Over {100 * over:.0f}%", ha="left", fontsize=8.5, color=YES)
    ax.set_ylim(0, ytop)
    ax.set_xticks(ks)
    ax.set_xlabel("total goals in the match", fontsize=8, color=MUTED)
    _pct_fmt(ax)
    ax.legend(fontsize=7.5, frameon=False, labelcolor=INK_2, loc="center right")
    _style(ax, "Total goals vs Normal approximation")


def _p_heatmap(ax, pred, kmax=5):
    sub = pred.score_matrix.grid[:kmax + 1, :kmax + 1]
    cmap = LinearSegmentedColormap.from_list("seq", SEQ_RAMP)
    ax.imshow(sub.T, origin="lower", cmap=cmap, vmin=0, vmax=float(sub.max()) * 1.05,
              aspect="auto")
    best = np.unravel_index(np.argmax(sub), sub.shape)
    for i in range(kmax + 1):
        for j in range(kmax + 1):
            v = sub[i, j]
            if v < 0.005:
                continue
            ax.text(i, j, f"{100 * v:.1f}", ha="center", va="center", fontsize=7.2,
                    fontweight="bold" if (i, j) == best else "normal",
                    color="#ffffff" if v > 0.55 * sub.max() else INK_2)
    ax.set_xticks(range(kmax + 1)); ax.set_yticks(range(kmax + 1))
    ax.set_xlabel(f"{pred.home} goals", fontsize=8, color=MUTED)
    ax.set_ylabel(f"{pred.away} goals", fontsize=8, color=MUTED)
    _style(ax, "Correct score (%)", grid_axis=None)


def _p_divergence(ax, pred):
    rows = [("Home win", lambda m: m["1x2"]["home"]), ("Draw", lambda m: m["1x2"]["draw"]),
            ("Away win", lambda m: m["1x2"]["away"]),
            ("Over 2.5", lambda m: m["over_under_2.5"]["over"]),
            ("BTTS", lambda m: m["btts"]["yes"]),
            ("Home o1.5", lambda m: m["team_totals"]["home"]["over_1.5"]),
            ("Away o1.5", lambda m: m["team_totals"]["away"]["over_1.5"])]
    ys = np.arange(len(rows))[::-1]
    for y, (lbl, get) in zip(ys, rows):
        vals = [get(mm) for mm in pred.model_markets.values()]
        lo, hi = min(vals), max(vals)
        ax.plot([lo, hi], [y, y], color=BASELINE, lw=3, solid_capstyle="round", zorder=2)
        ax.scatter(vals, [y] * len(vals), s=22, color=MUTED, zorder=3, edgecolor=SURFACE,
                   linewidth=1)
        fv = get(pred.markets)
        ax.scatter([fv], [y], s=60, marker="D", color=INK, zorder=4, edgecolor=SURFACE,
                   linewidth=1.5)
        ax.text(1.01, y, f"{100 * fv:.0f}%  ±{50 * (hi - lo):.0f}", va="center", fontsize=7.5,
                color=INK_2, transform=ax.get_yaxis_transform())
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8, color=INK_2)
    ax.set_xlim(0, 1)
    _pct_fmt(ax, "x")
    jsd = sorted(((n, js_divergence(sm.grid, pred.score_matrix.grid))
                  for n, sm in pred.model_matrices.items()), key=lambda x: x[1])
    txt = "JS divergence vs final:  " + " · ".join(f"{n} {d:.3f}" for n, d in jsd[:4])
    txt += "\n" + " · ".join(f"{n} {d:.3f}" for n, d in jsd[4:])
    ax.text(0, -0.2, txt, transform=ax.transAxes, fontsize=6.8, color=MUTED, va="top")
    ax.scatter([], [], s=22, color=MUTED, label="individual models")
    ax.scatter([], [], s=50, marker="D", color=INK, label="final (reconciled)")
    ax.legend(fontsize=7, frameon=False, labelcolor=INK_2, loc="lower right")
    _style(ax, "Model divergence by market", grid_axis="x")


def _p_evidence(ax, pred):
    """Last-5 form: each team overall and at the fixture's venue."""
    f = pred.form
    if not f:
        ax.axis("off")
        return
    c = f["counts"]
    cats = [("Scored 1+", "scored"), ("Scored 2+", "scored2"), ("Conceded 1+", "conceded"),
            ("Clean sheet", "clean_sheets"), ("BTTS", "btts"), ("Over 2.5", "o25")]
    series = [("home_home", f"{pred.home} at home", HOME, 1.0),
              ("home_last", f"{pred.home} last {f['window']}", HOME, 0.45),
              ("away_away", f"{pred.away} away", AWAY, 1.0),
              ("away_last", f"{pred.away} last {f['window']}", AWAY, 0.45)]
    ys = np.arange(len(cats))[::-1]
    h = 0.2
    offs = [1.5 * h, 0.5 * h, -0.5 * h, -1.5 * h]
    for off, (key, lbl, color, alpha) in zip(offs, series):
        x = c[key]
        if not x["n"]:
            continue
        vals = [x[k] / x["n"] for _, k in cats]
        ax.barh(ys + off, vals, height=h - 0.02, color=color, alpha=alpha, zorder=3,
                label=f"{lbl} ({x['n']})")
        for y, (_, k), v in zip(ys + off, cats, vals):
            ax.text(v + 0.012, y, f"{x[k]}/{x['n']}", va="center", fontsize=6.5, color=INK_2)
    ax.set_yticks(ys)
    ax.set_yticklabels([c_[0] for c_ in cats], fontsize=8, color=INK_2)
    ax.set_xlim(0, 1.18)
    _pct_fmt(ax, "x")
    ax.legend(fontsize=6.8, frameon=False, labelcolor=INK_2, loc="upper center",
              bbox_to_anchor=(0.5, -0.06), ncol=2)
    b = f.get("best_pick")
    title = f"Last-{f['window']} form"
    if b:
        title += f"  ·  best pick: {b['label']} ({100 * b['model_prob']:.0f}%)"
    _style(ax, title, grid_axis="x")


def _reliability(ax, items, title, bins=8):
    ax.plot([0, 1], [0, 1], color=BASELINE, lw=1, zorder=2)
    for (lbl, p, y, color, ls) in items:
        edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
        idx = np.clip(np.digitize(p, edges[1:-1]), 0, len(edges) - 2)
        mp = np.array([p[idx == b].mean() for b in range(len(edges) - 1) if (idx == b).any()])
        my = np.array([y[idx == b].mean() for b in range(len(edges) - 1) if (idx == b).any()])
        faded = lbl.endswith(" raw")
        ax.plot(mp, my, ls, color=color, lw=1.4 if faded else 1.8, ms=4.5, zorder=3,
                label=lbl, alpha=0.45 if faded else 1.0)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    _pct_fmt(ax); _pct_fmt(ax, "x")
    ax.set_xlabel("predicted", fontsize=8, color=MUTED)
    ax.set_ylabel("observed", fontsize=8, color=MUTED)
    ax.legend(fontsize=7, frameon=False, labelcolor=INK_2, loc="upper left")
    _style(ax, title, grid_axis="both")


def _p_reliability(ax, pred):
    ep = pred.eval_preds
    if not ep:
        ax.axis("off")
        return
    out = outcomes(ep["y_h"], ep["y_a"])
    f = ep["final"]
    items = [("Home win", f["1x2"][:, 0], (out["1x2"] == 0).astype(float), SERIES[0], "o-"),
             ("Over 2.5", f["o25"], out["o25"], SERIES[1], "o-"),
             ("BTTS", f["btts"], out["btts"], SERIES[2], "o-"),
             ("Home o1.5", f["h_o15"], out["h_o15"], SERIES[3], "o-")]
    _reliability(ax, items, f"Out-of-sample reliability ({len(ep['y_h'])} matches)")


def plot_prediction(pred, out_path):
    if pred.score_matrix is None:
        raise ValueError("prediction carries no score matrix")
    fig, axes = plt.subplots(3, 3, figsize=(18, 15))
    fig.patch.set_facecolor(SURFACE)
    _p_1x2(axes[0, 0], pred); _p_ou_btts(axes[0, 1], pred); _p_team_totals(axes[0, 2], pred)
    _p_goal_pmf(axes[1, 0], pred); _p_total_normal(axes[1, 1], pred); _p_heatmap(axes[1, 2], pred)
    _p_divergence(axes[2, 0], pred); _p_evidence(axes[2, 1], pred); _p_reliability(axes[2, 2], pred)
    eg = pred.expected_goals
    fig.suptitle(f"{pred.home}  vs  {pred.away}   —   {pred.date}", color=INK, fontsize=15,
                 fontweight="bold", x=0.02, ha="left", y=0.99)
    fig.text(0.02, 0.962, f"model: {pred.model} ({pred.version})   ·   xG {eg['home']:.2f} – "
             f"{eg['away']:.2f}   ·   overall confidence {pred.confidence['overall']}/100",
             color=INK_2, fontsize=10)
    fig.tight_layout(rect=(0.01, 0.01, 0.99, 0.95), h_pad=3.0, w_pad=2.5)
    return _save(fig, out_path)


# ================================================================ evaluation
def plot_evaluation(result, out_path):
    rep, ep = result.report, result.eval_preds
    fig, axes = plt.subplots(2, 3, figsize=(18, 10.5))
    fig.patch.set_facecolor(SURFACE)

    # 1) combined skill per candidate: raw / v1-style / final
    ax = axes[0, 0]
    cands = sorted([c for c, k in rep["candidates"].items() if "final" in k],
                   key=lambda c: rep["candidates"][c]["final"]["combined_skill"])
    ys = np.arange(len(cands))
    h = 0.27
    for off, kind, color, lbl in ((h, "raw", NEUTRAL, "raw"), (0, "baseline", "#86b6ef", "v1-style"),
                                  (-h, "final", HOME, "final (4-market)")):
        vals = [rep["candidates"][c][kind]["combined_skill"] for c in cands]
        ax.barh(ys + off, vals, height=h - 0.03, color=color, zorder=3, label=lbl)
    for y, c in zip(ys, cands):
        v = rep["candidates"][c]["final"]["combined_skill"]
        ax.text(max(v, 0) + 0.0005, y - h, f"{v:.4f}", va="center", fontsize=7, color=INK_2)
    ax.set_yticks(ys)
    ax.set_yticklabels([c + (" ◀" if c == rep["selected"] else "") for c in cands],
                       fontsize=8, color=INK_2)
    ax.axvline(0, color=BASELINE, lw=0.8)
    ax.legend(fontsize=7.5, frameon=False, labelcolor=INK_2, loc="upper center", ncol=3,
              bbox_to_anchor=(0.5, -0.07))
    _style(ax, "Combined 4-market skill by candidate", grid_axis="x")

    # 2) per-market skill of the selected candidate, v1-style vs final
    ax = axes[0, 1]
    s = rep["candidates"][rep["selected"]]
    mk = [("1x2", "1X2"), ("o25", "O2.5"), ("btts", "BTTS"), ("h_o05", "H o0.5"),
          ("h_o15", "H o1.5"), ("h_o25", "H o2.5"), ("a_o05", "A o0.5"), ("a_o15", "A o1.5"),
          ("a_o25", "A o2.5")]
    x = np.arange(len(mk))
    w = 0.38
    for off, kind, color, lbl in ((-w / 2, "baseline", "#86b6ef", "v1-style"),
                                  (w / 2, "final", HOME, "final")):
        vals = [s[kind][k]["skill"] for k, _ in mk]
        ax.bar(x + off, vals, width=w - 0.04, color=color, zorder=3, label=lbl)
    ax.set_xticks(x)
    ax.set_xticklabels([m[1] for m in mk], fontsize=7.5, color=INK_2)
    ax.axhline(0, color=BASELINE, lw=0.8)
    ax.legend(fontsize=7.5, frameon=False, labelcolor=INK_2)
    _style(ax, f"Skill per market — {rep['selected']}")

    # 3) calibration error per market
    ax = axes[0, 2]
    for off, kind, color, lbl in ((-w / 2, "baseline", "#86b6ef", "v1-style"),
                                  (w / 2, "final", HOME, "final")):
        vals = [s[kind][k]["ece"] for k, _ in mk]
        ax.bar(x + off, vals, width=w - 0.04, color=color, zorder=3, label=lbl)
    ax.set_xticks(x)
    ax.set_xticklabels([m[1] for m in mk], fontsize=7.5, color=INK_2)
    ax.legend(fontsize=7.5, frameon=False, labelcolor=INK_2)
    _pct_fmt(ax, decimals=1)
    _style(ax, "Calibration error per market (lower is better)")

    # 4-6) reliability, raw vs final
    out = outcomes(ep["y_h"], ep["y_a"])
    f, r = ep["final"], ep["raw"]
    _reliability(axes[1, 0], [
        ("Home win", f["1x2"][:, 0], (out["1x2"] == 0).astype(float), HOME, "o-"),
        ("Draw", f["1x2"][:, 1], (out["1x2"] == 1).astype(float), MUTED, "o-"),
        ("Away win", f["1x2"][:, 2], (out["1x2"] == 2).astype(float), AWAY, "o-")],
        "Reliability — 1X2 (final)")
    _reliability(axes[1, 1], [
        ("Over 2.5 raw", r["o25"], out["o25"], SERIES[1], "o--"),
        ("Over 2.5 final", f["o25"], out["o25"], SERIES[1], "o-"),
        ("BTTS raw", r["btts"], out["btts"], SERIES[2], "s--"),
        ("BTTS final", f["btts"], out["btts"], SERIES[2], "s-")],
        "Reliability — O/U 2.5 and BTTS (raw vs final)")
    _reliability(axes[1, 2], [
        ("Home o1.5", f["h_o15"], out["h_o15"], HOME, "o-"),
        ("Away o1.5", f["a_o15"], out["a_o15"], AWAY, "o-"),
        ("Home o2.5", f["h_o25"], out["h_o25"], HOME, "s--"),
        ("Away o0.5", f["a_o05"], out["a_o05"], AWAY, "s--")],
        "Reliability — team goals (final)")

    fig.suptitle(f"Model evaluation — out of sample, {rep['eval_matches']} matches",
                 color=INK, fontsize=14, fontweight="bold", x=0.02, ha="left", y=0.99)
    fig.tight_layout(rect=(0.01, 0.01, 0.99, 0.95), h_pad=3.0, w_pad=2.5)
    return _save(fig, out_path)
