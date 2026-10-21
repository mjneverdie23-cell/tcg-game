"""Text summary of a training report (used by `footy train` / `footy evaluate`)."""

from __future__ import annotations

GROUP_LABEL = {"1x2": "1X2", "o25": "O/U 2.5", "btts": "BTTS", "team_totals": "Team totals"}


def render_training_report(rep: dict) -> str:
    L = []
    sel = rep["selected"]
    periods = (f"half-seasons {', '.join(rep['eval_periods'])}"
               if rep.get("fold_mode") == "half"
               else f"seasons {', '.join(map(str, rep['eval_seasons']))}")
    L.append(f"Evaluated out of sample on {rep['eval_matches']} matches ({periods}).")
    L.append("Skill = log-loss improvement over the base rate (higher is better).\n")
    L.append(f"{'candidate':<15}{'raw':>9}{'v1-style':>10}{'final':>9}   per-market final skill "
             f"(1X2 / O2.5 / BTTS / team totals)")
    rows = sorted(((c, k) for c, k in rep["candidates"].items() if "final" in k),
                  key=lambda x: -x[1]["final"]["combined_skill"])
    for c, k in rows:
        g = k["final"]["groups"]
        mark = " ◀ selected" if c == sel else ""
        L.append(f"{c:<15}{k['raw']['combined_skill']:9.4f}{k['baseline']['combined_skill']:10.4f}"
                 f"{k['final']['combined_skill']:9.4f}   {g['1x2']:.4f} / {g['o25']:.4f} / "
                 f"{g['btts']:.4f} / {g['team_totals']:.4f}{mark}")
    if "direct_gbm" in rep["candidates"]:
        d = rep["candidates"]["direct_gbm"]["raw"]
        L.append(f"{'direct only':<15}{d['combined_skill']:9.4f}")

    s = rep["candidates"][sel]
    L.append(f"\nSelected '{sel}' — v1-style vs final, per market:")
    L.append(f"  {'market':<18}{'log loss':>18}{'calibration err':>20}{'accuracy':>16}")
    for mk, lbl in (("1x2", "1X2"), ("o25", "Over 2.5"), ("btts", "BTTS"),
                    ("h_o05", "Home over 0.5"), ("h_o15", "Home over 1.5"),
                    ("h_o25", "Home over 2.5"), ("a_o05", "Away over 0.5"),
                    ("a_o15", "Away over 1.5"), ("a_o25", "Away over 2.5")):
        b, f = s["baseline"][mk], s["final"][mk]
        L.append(f"  {lbl:<18}{b['logloss']:8.4f} → {f['logloss']:.4f}"
                 f"{b['ece']:11.4f} → {f['ece']:.4f}{100 * b['accuracy']:9.1f}% → "
                 f"{100 * f['accuracy']:.1f}%")
    heads = rep.get("heads", {}).get(sel, {})
    if heads:
        stk = [k for k, v in heads.items() if v == "stk"]
        L.append(f"  direct market classifiers used in: {', '.join(stk) if stk else 'none (calibration alone won)'}")
    if rep.get("ensemble_weights"):
        w = ", ".join(f"{k} {v:.2f}" for k, v in sorted(rep["ensemble_weights"].items(),
                                                         key=lambda x: -x[1]) if v > 0)
        L.append(f"  ensemble weights: {w}")
    b = rep.get("bookmaker")
    if b:
        L.append(f"\nBookmaker closing-odds benchmark (same matches):"
                 f"\n  1X2 log loss  model {b['model_1x2_logloss']:.4f}  vs  book {b['1x2_logloss']:.4f}"
                 f"\n  O2.5 log loss model {b['model_o25_logloss']:.4f}  vs  book {b['o25_logloss']:.4f}")
    h = rep.get("halftime")
    if h and h.get("eval"):
        e = h["eval"]
        L.append(f"\nFirst half (out of sample, {h['eval_matches']} matches with half-time "
                 f"scores): {h['selected']} model, combined skill {e['combined_skill']:+.4f}")
        L.append(f"  {'market':<14}{'log loss':>10}{'skill':>9}{'accuracy':>10}{'calib. err':>12}")
        for k in ("1x2", "o05", "o15", "o25", "btts"):
            x = e[k]
            L.append(f"  {('HT ' + {'1x2': '1X2', 'o05': 'over 0.5', 'o15': 'over 1.5', 'o25': 'over 2.5', 'btts': 'BTTS'}[k]):<14}"
                     f"{x['logloss']:10.4f}{x['skill']:+9.4f}{100 * x['accuracy']:9.1f}%{100 * x['ece']:11.1f}%")
        others = {c: v["combined_skill"] for c, v in h.get("candidates", {}).items() if c != h["selected"]}
        if others:
            L.append("  other candidates: " + ", ".join(f"{c} {v:+.4f}" for c, v in others.items()))
    elif h:
        L.append(f"\nFirst half: trained on {h['matches']} matches with half-time scores "
                 "(too few seasons to evaluate out of sample)")
    L.append(f"\n{rep['n_matches']} matches · {rep['n_features']} features · "
             f"DC half-life {rep['dc_half_life_days']:.0f} days · trained in {rep['train_seconds']}s")
    return "\n".join(L)
