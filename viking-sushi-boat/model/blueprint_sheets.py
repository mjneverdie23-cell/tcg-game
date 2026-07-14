"""Dimensioned blueprint sheets (PNG) + DXF cut files for the skeleton."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

import blueprint as bp

BG = "#f7f9fc"
INK = "#16386e"          # part lines
FILL = "#e4ecf7"
DIM = "#9c2b21"          # dimension lines
CL = "#5577aa"           # centrelines

DATE = "2026-07-14"
PROJECT = "VIKING SUSHI BOAT - FLAT BOTTOM + SKELETON  (v2)"


# ------------------------------------------------------------ draw helpers -
def draw_part(ax, p, lw=1.6):
    geoms = p.geoms if p.geom_type == "MultiPolygon" else [p]
    for g in geoms:
        xs, ys = np.asarray(g.exterior.coords).T
        ax.fill(xs, ys, fc=FILL, ec=INK, lw=lw, zorder=2)
        for h in g.interiors:
            hx, hy = np.asarray(h.coords).T
            ax.fill(hx, hy, fc="white", ec=INK, lw=lw * 0.85, zorder=3)


def hdim(ax, x0, x1, y, text=None, ts=9):
    for x in (x0, x1):
        ax.plot([x, x], [y - 3, y + 3], color=DIM, lw=0.8, zorder=4)
    ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle="<|-|>",
                                 mutation_scale=9, color=DIM, lw=0.9,
                                 zorder=4))
    ax.text((x0 + x1) / 2, y + 4, text or f"{abs(x1 - x0):.0f}",
            ha="center", va="bottom", fontsize=ts, color=DIM, zorder=5)


def vdim(ax, y0, y1, x, text=None, ts=9, side=1):
    for y in (y0, y1):
        ax.plot([x - 3, x + 3], [y, y], color=DIM, lw=0.8, zorder=4)
    ax.add_patch(FancyArrowPatch((x, y0), (x, y1), arrowstyle="<|-|>",
                                 mutation_scale=9, color=DIM, lw=0.9,
                                 zorder=4))
    ax.text(x + 5 * side, (y0 + y1) / 2, text or f"{abs(y1 - y0):.0f}",
            ha="left" if side > 0 else "right", va="center", fontsize=ts,
            color=DIM, rotation=90, zorder=5)


def leader(ax, xy, text, xytext, ts=8.5):
    ax.annotate(text, xy, xytext=xytext, fontsize=ts, color=INK,
                ha="center", zorder=5,
                arrowprops=dict(arrowstyle="->", lw=0.8, color=INK))


def cline(ax, p0, p1):
    ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color=CL, lw=0.7,
            ls=(0, (10, 3, 2, 3)), zorder=1)


def title_block(fig, sheet, title, scale):
    ax = fig.add_axes([0.60, 0.015, 0.385, 0.115])
    ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 10, 3, fc="white", ec=INK, lw=1.4))
    ax.plot([0, 10], [2, 2], color=INK, lw=0.8)
    ax.plot([6.4, 6.4], [0, 3], color=INK, lw=0.8)
    ax.text(0.15, 2.45, PROJECT, fontsize=9.5, fontweight="bold", color=INK)
    ax.text(0.15, 1.35, title, fontsize=9, color=INK)
    ax.text(0.15, 0.45, "MATERIAL: 12 mm birch plywood / hardwood  -  "
                        "UNITS: mm", fontsize=7.5, color=INK)
    ax.text(6.6, 1.45, f"SHEET {sheet}/4", fontsize=9, color=INK)
    ax.text(6.6, 0.45, f"SCALE {scale}   {DATE}", fontsize=7.5, color=INK)


def sheet_axes(fig):
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.93])
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


# ================================================== SHEET 1 - BOTTOM PLATE =
def sheet1(path):
    fig = plt.figure(figsize=(16.5, 10.5))
    fig.patch.set_facecolor(BG)
    ax = sheet_axes(fig)
    p = bp.bottom_part()
    draw_part(ax, p)
    cline(ax, (-310, 0), (310, 0))
    cline(ax, (0, -105), (0, 105))
    for x in bp.RIB_X:                       # rib stations
        cline(ax, (x, -bp.bottom_half_width(x) - 6),
              (x, bp.bottom_half_width(x) + 6))
        ax.text(x, bp.bottom_half_width(x) + 9, f"rib\n{x:+.0f}",
                ha="center", fontsize=7, color=CL)
    hdim(ax, -280, 280, -128, "560")
    vdim(ax, -90, 90, 300, "180 (max, at x=0)")
    hdim(ax, -160.2, -119.8, 52, "40.4")
    hdim(ax, -140, 0, -50, "140 c-c")
    hdim(ax, 0, 140, -50, "140 c-c")
    vdim(ax, -6.2, 6.2, 168, "12.4", side=1)
    leader(ax, (-140, 6), "3x through slot 40.4 x 12.4\nfor spine tabs, "
                          "dogbone R3.1", (-150, 116))
    leader(ax, (238, 40), "side edges: smooth arcs\n(coordinates per DXF)",
           (240, 108))
    leader(ax, (283, -4), "pointed bow", (300, -60))
    leader(ax, (-283, -4), "pointed stern", (-300, -60))
    # half-width table
    tx = -300
    rows = [("station x", "half-width")] + \
           [(f"{x:+.0f}", f"{bp.bottom_half_width(x):.0f}")
            for x in [0.0, 90.0, 180.0, 240.0]]
    for i, (a, b) in enumerate(rows):
        ax.text(tx, -150 - 13 * i, a, fontsize=8, color=INK)
        ax.text(tx + 80, -150 - 13 * i, b, fontsize=8, color=INK)
    ax.set_xlim(-360, 360)
    ax.set_ylim(-225, 150)
    fig.suptitle("P1  FLAT BOTTOM PLATE  -  plan view  (qty 1, t = 12)",
                 fontsize=13, color=INK, y=0.97)
    title_block(fig, 1, "P1 FLAT BOTTOM - PLAN", "1:4 @ A3")
    plt.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


# =================================================== SHEET 2 - KEEL SPINE ==
def sheet2(path):
    fig = plt.figure(figsize=(16.5, 10.5))
    fig.patch.set_facecolor(BG)
    ax = sheet_axes(fig)
    p = bp.spine_part()
    draw_part(ax, p)
    cline(ax, (-340, 0), (420, 0))
    for x in bp.RIB_X:
        cline(ax, (x, -12), (x, 75))
    # datum and key levels
    hdim(ax, -323.7, 404.2, -36, "728 overall")
    vdim(ax, 0, 304, 452, "304 overall", side=1)
    vdim(ax, 0, bp.SPINE_TOP, 222, "58", side=1)
    vdim(ax, bp.LAP_Z, bp.SPINE_TOP, 46, "28", side=1)
    hdim(ax, -6.2, 6.2, 78, "12.4")
    hdim(ax, 0, 90, 100, "90 c-c")
    hdim(ax, -90, 0, 100, "90 c-c")
    hdim(ax, 121, 159, -18, "38")
    leader(ax, (90, 44), "5x rib slot 12.4 wide,\ndepth 28 (to z=30),\n"
                         "dogbone R3.1", (60, 150))
    leader(ax, (140, 3), "3x bottom tab 38 x 12\n(flush with plate underside)",
           (120, -66))
    leader(ax, (351, 261), "eye cutout\n(per DXF)", (300, 320))
    leader(ax, (-296, 250), "tail volute: tapering spiral band,\n"
                            "centre (-296, 212), sweep 438 deg,\n"
                            "band 28 -> 8 wide", (-180, 300))
    leader(ax, (402, 231), "dragon head profile per DXF\n(Urnes style)",
           (368, 118))
    leader(ax, (-306, 100), "sternpost trailing edge", (-260, 40))
    ax.text(-330, -60, "datum z=0: underside of bottom plate  -  "
                       "plate top = 12", fontsize=8.5, color=DIM)
    ax.set_xlim(-390, 470)
    ax.set_ylim(-95, 345)
    fig.suptitle("P2  KEEL SPINE with dragon head & tail volute  -  profile"
                 "  (qty 1, t = 12)", fontsize=13, color=INK, y=0.97)
    title_block(fig, 2, "P2 KEEL SPINE - PROFILE", "1:4.5 @ A3")
    plt.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


# ========================================================= SHEET 3 - RIBS ==
def sheet3(path):
    fig = plt.figure(figsize=(16.5, 10.5))
    fig.patch.set_facecolor(BG)
    ax = sheet_axes(fig)
    ws = bp.rib_widths()
    ribs = [("R3  CENTRE RIB   (qty 1, station x = 0)", ws[0.0], 0),
            ("R2  MID RIB   (qty 2, stations x = +-90)", ws[90.0], -150),
            ("R1  END RIB   (qty 2, stations x = +-180)", ws[180.0], -300)]
    for label, wb, oy in ribs:
        p = bp.rib_part(wb)
        from shapely import affinity
        p = affinity.translate(p, 0, oy)
        draw_part(ax, p)
        b = p.bounds
        cline(ax, (0, oy + 4), (0, oy + 100))
        ax.text(b[0] - 8, oy + 88, label, fontsize=10, color=INK,
                fontweight="bold", ha="left")
        hdim(ax, b[0], b[2], oy - 6, f"{b[2] - b[0]:.0f}")
        hdim(ax, -wb, wb, oy - 24, f"foot {2 * wb:.0f}")
        vdim(ax, oy + 12, b[3], b[2] + 12, f"{b[3] - oy - 12:.0f}", side=1)
        if oy == 0:
            hdim(ax, -6.2, 6.2, oy + 52, "12.4")
            ax.plot([-6.2, -6.2], [oy + 30, oy + 49], color=DIM, lw=0.5)
            ax.plot([6.2, 6.2], [oy + 30, oy + 49], color=DIM, lw=0.5)
            vdim(ax, oy + 12, oy + 30, 40, "18", side=1)
            leader(ax, (16, oy + 13), "2x limber hole R5\nat y = +-16",
                   (110, oy + 44))
            leader(ax, (-4, oy + 26), "keel half-lap slot 12.4 x 18,\n"
                                      "dogbone R3.1", (-110, oy + 52))
    ax.text(-250, -370, "all ribs: t = 12  -  foot sits on plate top "
                        "(z = 12)  -  slot laps the spine at z = 30",
            fontsize=9, color=DIM)
    ax.set_xlim(-260, 260)
    ax.set_ylim(-420, 130)
    fig.suptitle("P3  RIB FAMILY  -  5 pieces, 3 unique  (t = 12)",
                 fontsize=13, color=INK, y=0.97)
    title_block(fig, 3, "P3 RIBS R1/R2/R3", "1:3 @ A3")
    plt.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


# ===================================================== SHEET 4 - ASSEMBLY ==
def sheet4(path):
    fig = plt.figure(figsize=(16.5, 10.5))
    fig.patch.set_facecolor(BG)
    # side elevation ------------------------------------------------------
    ax = fig.add_axes([0.04, 0.47, 0.92, 0.46]); ax.set_aspect("equal")
    ax.axis("off")
    draw_part(ax, bp.spine_part(), lw=1.1)
    ws = bp.rib_widths()
    from shapely import affinity
    for x in bp.RIB_X:                       # rib silhouettes edge-on
        ax.add_patch(plt.Rectangle((x - 6, 12), 12,
                                   58.8 + 0.32 * ws[x] - 4, fc="#c8d6ea",
                                   ec=INK, lw=0.9, zorder=3))
    ax.add_patch(plt.Rectangle((-280, 0), 560, 12, fc="#c8d6ea", ec=INK,
                               lw=1.0, zorder=1))
    ax.text(-330, 285, "SIDE ELEVATION (assembled)", fontsize=10,
            color=INK, fontweight="bold")
    hdim(ax, -180, 180, 105, "4 x 90 = 360")
    ax.set_xlim(-395, 465); ax.set_ylim(-30, 322)

    # top view ------------------------------------------------------------
    ax2 = fig.add_axes([0.04, 0.16, 0.55, 0.30]); ax2.set_aspect("equal")
    ax2.axis("off")
    draw_part(ax2, bp.bottom_part(), lw=1.1)
    ax2.add_patch(plt.Rectangle((-308, -6), 712, 12, fc="#c8d6ea", ec=INK,
                                lw=0.9, zorder=3, alpha=0.9))
    for x in bp.RIB_X:
        wbx = ws[x]
        ax2.add_patch(plt.Rectangle((x - 6, -wbx - 10), 12, 2 * wbx + 20,
                                    fc="#b8c9e2", ec=INK, lw=0.9, zorder=4))
    ax2.text(-300, 118, "TOP VIEW", fontsize=10, color=INK,
             fontweight="bold")
    ax2.set_xlim(-360, 430); ax2.set_ylim(-135, 140)

    # joint detail ---------------------------------------------------------
    ax3 = fig.add_axes([0.62, 0.16, 0.34, 0.30]); ax3.set_aspect("equal")
    ax3.axis("off")
    ax3.add_patch(plt.Rectangle((-60, 0), 120, 12, fc="#c8d6ea", ec=INK,
                                lw=1.2))
    spine_sec = plt.Polygon([(-6, 12), (6, 12), (6, 30), (6.2, 30),
                             (6.2, 58), (30, 58), (30, 70), (-30, 70),
                             (-30, 58), (-6.2, 58), (-6.2, 30), (-6, 30)],
                            closed=True, fc=FILL, ec=INK, lw=1.2)
    # simpler: draw spine slot region and rib slot engaging
    ax3.add_patch(plt.Rectangle((-6, 12), 12, 46, fc="#dbe7f5", ec=INK,
                                lw=1.2))
    ax3.add_patch(plt.Rectangle((-40, 12), 28, 34, fc="#eddfc8", ec=INK,
                                lw=1.2))
    ax3.add_patch(plt.Rectangle((12, 12), 28, 34, fc="#eddfc8", ec=INK,
                                lw=1.2))
    ax3.add_patch(plt.Rectangle((-40, 30), 80, 16, fc="none", ec=INK,
                                lw=0.0))
    vdim(ax3, 12, 30, 50, "18 rib slot", side=1)
    vdim(ax3, 30, 58, 66, "28 spine slot", side=1)
    hdim(ax3, -6.2, 6.2, 74, "12.4")
    ax3.text(-58, 84, "EGG-CRATE HALF-LAP (section at a rib)",
             fontsize=9.5, color=INK, fontweight="bold")
    ax3.text(-58, -26, "rib (ochre) laps the spine (blue) at z = 30;\n"
                       "both stand on the 12 mm bottom plate",
             fontsize=8, color=INK)
    ax3.set_xlim(-70, 110); ax3.set_ylim(-40, 100)

    # notes -----------------------------------------------------------------
    fig.text(0.04, 0.115, "NOTES:  1. stock 12.0 mm; all slots 12.4 "
                          "(+0.4 fit).   2. dogbone reliefs R3.1 for a "
                          "6 mm cutter are included in the DXF.",
             fontsize=9, color=DIM)
    fig.text(0.04, 0.085, "3. assembly: tabs of P2 into P1, then ribs "
                          "R1-R3 drop over the spine.   4. food-safe "
                          "oil finish.", fontsize=9, color=DIM)
    fig.suptitle("ASSEMBLY  -  elevation, plan and joint detail",
                 fontsize=13, color=INK, y=0.97)
    title_block(fig, 4, "ASSEMBLY + JOINTS", "1:5 / 1:1.5 @ A3")
    plt.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


# ================================================================== DXF ====
def export_dxfs(outdir):
    import ezdxf
    os.makedirs(outdir, exist_ok=True)
    ws = bp.rib_widths()
    parts = [("P1_bottom_plate", bp.bottom_part(), 1),
             ("P2_keel_spine", bp.spine_part(), 1),
             ("P3_rib_R3_centre", bp.rib_part(ws[0.0]), 1),
             ("P3_rib_R2_mid", bp.rib_part(ws[90.0]), 2),
             ("P3_rib_R1_end", bp.rib_part(ws[180.0]), 2)]
    files = []

    def add(msp, p, dx=0, dy=0):
        geoms = p.geoms if p.geom_type == "MultiPolygon" else [p]
        for g in geoms:
            msp.add_lwpolyline(np.asarray(g.exterior.coords) + [dx, dy],
                               close=True, dxfattribs={"layer": "CUT"})
            for h in g.interiors:
                msp.add_lwpolyline(np.asarray(h.coords) + [dx, dy],
                                   close=True, dxfattribs={"layer": "CUT"})

    for name, p, qty in parts:
        doc = ezdxf.new("R2010", setup=True)
        doc.header["$INSUNITS"] = 4
        doc.layers.add("CUT", color=2)
        doc.layers.add("LABEL", color=3)
        msp = doc.modelspace()
        b = p.bounds
        add(msp, p, -b[0], -b[1])
        msp.add_text(f"{name}  qty {qty}  t12", height=8, dxfattribs={
            "layer": "LABEL"}).set_placement((2, -14))
        fn = os.path.join(outdir, f"{name}.dxf")
        doc.saveas(fn)
        files.append(fn)

    # combined layout
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.layers.add("CUT", color=2)
    doc.layers.add("LABEL", color=3)
    msp = doc.modelspace()
    oy = 0.0
    for name, p, qty in parts:
        b = p.bounds
        add(msp, p, -b[0], oy - b[1])
        msp.add_text(f"{name} x{qty}", height=8, dxfattribs={
            "layer": "LABEL"}).set_placement((0, oy - 14))
        oy += (b[3] - b[1]) + 30
    fn = os.path.join(outdir, "all_parts_layout.dxf")
    doc.saveas(fn)
    files.append(fn)
    return files


if __name__ == "__main__":
    os.makedirs(bp.BP, exist_ok=True)
    sheet1(os.path.join(bp.BP, "sheet1_bottom.png"))
    sheet2(os.path.join(bp.BP, "sheet2_spine.png"))
    sheet3(os.path.join(bp.BP, "sheet3_ribs.png"))
    sheet4(os.path.join(bp.BP, "sheet4_assembly.png"))
    print("sheets done")
    for f in export_dxfs(bp.CNC):
        print(" ", f)
