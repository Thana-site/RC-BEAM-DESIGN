"""
Beam Elevation — Full Structural Drawing
=========================================
Generates a publication-quality beam elevation drawing using Plotly shapes
and annotations.  Replaces the placeholder sketch that was here before.

Public API (unchanged):
    create_beam_elevation_plot(span_lengths, design_results, rebar_summaries)
        -> go.Figure

Internal helper for a standalone beam_config dict:
    draw_beam_elevation(beam_config) -> go.Figure
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from constants import SECTIONS
from models.section import SectionGeometry

# ─────────────────────────────────────────────────────────────────────────────
#  Colour palette  (dark-mode, matching the rest of the app)# ─────────────────────────────────────────────────────────────────────────────
_C = {
    "bg":          "#0F141E",
    "beam_fill":   "rgba(52, 62, 95, 0.90)",
    "beam_line":   "#3A4060",
    "col_fill":    "rgba(42, 50, 80, 0.95)",
    "col_line":    "#4A5580",
    "top_bar":     "#44DD88",        # green  – continuous top
    "bot_bar":     "#FF5555",        # red    – continuous bottom
    "sup_bar":     "#55CCFF",        # cyan   – support hogging bars
    "mid_bar":     "#FFAA33",        # amber  – midspan extra bottom
    "stirrup":     "#7090CC",        # steel-blue
    "dim":         "#8898BB",        # dimension lines / ticks
    "label":       "#C8D0E8",        # general text
    "span_lbl":    "#E0E8FF",        # span header text
    "pass":        "#44DD88",
    "fail":        "#FF4444",
    "na":          "#A78BFA",        # neutral axis purple (unused here but kept)
}


# ─────────────────────────────────────────────────────────────────────────────
#  Low-level shape helpers
# ─────────────────────────────────────────────────────────────────────────────

def _rect(fig: go.Figure,
          x0: float, x1: float, y0: float, y1: float,
          fill: str, line_color: str, lw: float = 1.5,
          layer: str = "below") -> None:
    fig.add_shape(
        type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
        fillcolor=fill,
        line=dict(color=line_color, width=lw),
        layer=layer,
    )


def _hline(fig: go.Figure,
           x0: float, x1: float, y: float,
           color: str, width: float = 2.5) -> None:
    fig.add_shape(type="line",
                  x0=x0, x1=x1, y0=y, y1=y,
                  line=dict(color=color, width=width))


def _vline(fig: go.Figure,
           x: float, y0: float, y1: float,
           color: str, width: float = 1.2) -> None:
    fig.add_shape(type="line",
                  x0=x, x1=x, y0=y0, y1=y1,
                  line=dict(color=color, width=width))


def _label(fig: go.Figure,
           x: float, y: float, text: str,
           color: str, size: int = 10,
           xanchor: str = "center", yanchor: str = "middle",
           bgcolor: str = "rgba(15,20,30,0.75)",
           bordercolor: str = "rgba(0,0,0,0)", borderwidth: int = 0,
           borderpad: int = 2) -> None:
    fig.add_annotation(
        x=x, y=y, text=text, showarrow=False,
        font=dict(size=size, color=color, family="Arial"),
        xanchor=xanchor, yanchor=yanchor,
        bgcolor=bgcolor,
        bordercolor=bordercolor,
        borderwidth=borderwidth,
        borderpad=borderpad,
    )


def _dim_line(fig: go.Figure,
              x0: float, x1: float, y: float,
              text: str,
              color: str = _C["dim"],
              fontsize: int = 10,
              above: bool = True,
              tick_half: float = 18.0) -> None:
    """Horizontal dimension line with end ticks and centred text."""
    _hline(fig, x0, x1, y, color, width=1.0)
    # end ticks
    for xc in (x0, x1):
        _vline(fig, xc, y - tick_half, y + tick_half, color, width=1.0)
    # text
    yshift = tick_half + 4 if above else -(tick_half + 4)
    yanchor = "bottom" if above else "top"
    _label(fig, (x0 + x1) / 2, y, text, color, fontsize,
           yanchor=yanchor, bgcolor="rgba(15,20,30,0.82)",
           xanchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Core drawing function  (beam_config dict)
# ─────────────────────────────────────────────────────────────────────────────

def draw_beam_elevation(cfg: dict) -> go.Figure:  # noqa: C901
    """
    Draw a full structural beam elevation from a *beam_config* dict.

    Keys expected in cfg
    --------------------
    beam           : {height, width, cover, bar_dia}
    spans          : [{label, length}, ...]
    columns        : {width, above, below}
    cantilever     : None | float (mm, right side only)
    continuous_bars: {top: {count, dia, label}, bottom: {count, dia, label}}
    support_bars   : [{support_index, count, dia, label, left_ext, right_ext}]
    midspan_bars   : [{span_index, count, dia, label, left_offset, right_offset}]
    stirrups       : [{span_index, zone, spacing, count}]
                     zone ∈ {"left", "mid", "right"}
    results        : [{span_index, status, U}]
    """

    # ── geometry ──────────────────────────────────────────────────────────────
    bh      = float(cfg["beam"]["height"])
    cover   = float(cfg["beam"].get("cover", 40))
    bar_d   = float(cfg["beam"].get("bar_dia", 25))
    col_w   = float(cfg["columns"]["width"])
    col_ab  = float(cfg["columns"]["above"])   # column stub above beam
    col_bl  = float(cfg["columns"]["below"])   # column stub below beam
    spans   = cfg["spans"]
    cant    = cfg.get("cantilever")            # None or mm

    Y_TOP   = 0.0
    Y_BOT   = bh
    Y_TBAR  = cover + bar_d / 2              # main top bar y
    Y_BBAR  = bh - cover - bar_d / 2        # main bottom bar y

    # vertical positions for extra rows
    Y_SUP_BAR = Y_TBAR + bar_d + 4          # support hogging bars (below top)
    Y_MID_BAR = Y_BBAR - bar_d - 4          # midspan extra bottom (above bot)

    # annotation rails
    Y_DIM_SPAN = Y_TOP - col_ab - 55        # span dimension line (above)
    Y_SPAN_LBL = Y_DIM_SPAN - 32           # span name label
    Y_DIM_ZONE = Y_BOT + col_bl + 36       # stirrup zone dim (below)
    Y_RESULT   = Y_BOT + col_bl + 88       # PASS/FAIL text

    # cumulative column-centreline x-coordinates
    col_x: list[float] = [0.0]
    for sp in spans:
        col_x.append(col_x[-1] + sp["length"])
    total_len = col_x[-1]
    x_cant_end = total_len + cant if cant else total_len

    stir_pad = cover + 10.0

    # ── figure ────────────────────────────────────────────────────────────────
    margin_l = col_w * 1.6
    margin_r = col_w * 1.6 + (cant if cant else 0)
    x_min    = -margin_l
    x_max    = total_len + margin_r
    y_min    = Y_SPAN_LBL - 24
    y_max    = Y_RESULT   + 38

    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor=_C["bg"],
        plot_bgcolor =_C["bg"],
        width=1500, height=520,
        margin=dict(l=20, r=20, t=52, b=20),
        title=dict(
            text="BEAM ELEVATION — REINFORCEMENT LAYOUT",
            font=dict(size=14, color=_C["span_lbl"], family="Arial"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(range=[x_min, x_max],
                   showgrid=False, zeroline=False,
                   showticklabels=False, visible=False),
        yaxis=dict(range=[y_max, y_min],          # inverted: y_top < y_bot
                   showgrid=False, zeroline=False,
                   showticklabels=False, visible=False,
                   scaleanchor=None),
        showlegend=False,
    )

    # ── 1  COLUMN STUBS ───────────────────────────────────────────────────────
    for cx in col_x:
        _rect(fig,
              cx - col_w / 2, cx + col_w / 2,
              Y_TOP - col_ab, Y_BOT + col_bl,
              _C["col_fill"], _C["col_line"], lw=2.0)

    # ── 2  BEAM BODY ──────────────────────────────────────────────────────────
    for i, sp in enumerate(spans):
        _rect(fig, col_x[i], col_x[i + 1], Y_TOP, Y_BOT,
              _C["beam_fill"], _C["beam_line"], lw=1.5)

    if cant:
        _rect(fig, col_x[-1], x_cant_end, Y_TOP, Y_BOT,
              _C["beam_fill"], _C["beam_line"], lw=1.5)

    # ── 3  STIRRUPS ───────────────────────────────────────────────────────────
    stir_tick_top = Y_TOP + stir_pad
    stir_tick_bot = Y_BOT - stir_pad

    zone_bounds: dict[tuple[int, str], tuple[float, float]] = {}  # for dim lines

    for st in cfg.get("stirrups", []):
        si      = st["span_index"]
        zone    = st["zone"]
        spacing = float(st["spacing"])
        count   = int(st["count"])

        xs_start = col_x[si]
        xs_end   = col_x[si + 1]
        zone_len = spacing * max(count - 1, 0)

        if zone == "left":
            zx0 = xs_start + stir_pad
            zx1 = zx0 + zone_len
        elif zone == "right":
            zx1 = xs_end - stir_pad
            zx0 = zx1 - zone_len
        else:  # mid
            mid = (xs_start + xs_end) / 2
            zx0 = mid - zone_len / 2
            zx1 = mid + zone_len / 2

        zone_bounds[(si, zone)] = (zx0, zx1)

        xs_pos = np.linspace(zx0, zx1, count) if count > 1 else np.array([zx0])
        for x in xs_pos:
            _vline(fig, x, stir_tick_top, stir_tick_bot,
                   _C["stirrup"], width=1.2)

        # mid-zone spacing label inside beam
        if zone == "mid":
            _label(fig, (zx0 + zx1) / 2, (Y_TOP + Y_BOT) / 2,
                   f"s = {int(spacing)} mm",
                   _C["stirrup"], size=9,
                   bgcolor="rgba(15,20,30,0.72)")

    # ── 4  CONTINUOUS TOP BARS ────────────────────────────────────────────────
    top_cfg = cfg["continuous_bars"]["top"]
    x0_bar  = col_x[0]
    x1_bar  = x_cant_end

    _hline(fig, x0_bar, x1_bar, Y_TBAR, _C["top_bar"], width=3.0)

    for i, sp in enumerate(spans):
        xm = (col_x[i] + col_x[i + 1]) / 2
        _label(fig, xm, Y_TBAR - bar_d - 6,
               top_cfg["label"], _C["top_bar"], size=9)

    # ── 5  CONTINUOUS BOTTOM BARS ─────────────────────────────────────────────
    bot_cfg = cfg["continuous_bars"]["bottom"]

    _hline(fig, x0_bar, x1_bar, Y_BBAR, _C["bot_bar"], width=3.0)

    for i, sp in enumerate(spans):
        xm = (col_x[i] + col_x[i + 1]) / 2
        _label(fig, xm, Y_BBAR + bar_d + 6,
               bot_cfg["label"], _C["bot_bar"], size=9)

    # ── 6  SUPPORT TOP (HOGGING) BARS ─────────────────────────────────────────
    for sb in cfg.get("support_bars", []):
        cx  = col_x[sb["support_index"]]
        x0s = cx - sb["left_ext"]
        x1s = cx + sb["right_ext"]

        _hline(fig, x0s, x1s, Y_SUP_BAR, _C["sup_bar"], width=2.5)
        # end-hook ticks
        for xc in (x0s, x1s):
            _vline(fig, xc, Y_SUP_BAR - 14, Y_SUP_BAR + 14,
                   _C["sup_bar"], width=1.5)

        _label(fig, cx, Y_SUP_BAR - bar_d - 8,
               sb["label"], _C["sup_bar"], size=9)

    # ── 7  MIDSPAN EXTRA BOTTOM BARS ──────────────────────────────────────────
    for mb in cfg.get("midspan_bars", []):
        si  = mb["span_index"]
        x0m = col_x[si]        + mb["left_offset"]
        x1m = col_x[si + 1]   - mb["right_offset"]

        _hline(fig, x0m, x1m, Y_MID_BAR, _C["mid_bar"], width=2.5)
        for xc in (x0m, x1m):
            _vline(fig, xc, Y_MID_BAR - 14, Y_MID_BAR + 14,
                   _C["mid_bar"], width=1.5)

        xm = (x0m + x1m) / 2
        _label(fig, xm, Y_MID_BAR + bar_d + 8,
               mb["label"], _C["mid_bar"], size=9)

    # ── 8  SPAN DIMENSION LINES (above beam) ──────────────────────────────────
    for i, sp in enumerate(spans):
        _dim_line(fig, col_x[i], col_x[i + 1], Y_DIM_SPAN,
                  f"{int(sp['length'])} mm",
                  color=_C["dim"], fontsize=10, above=True)

    if cant:
        _dim_line(fig, col_x[-1], x_cant_end, Y_DIM_SPAN,
                  f"{int(cant)} mm",
                  color=_C["dim"], fontsize=10, above=True)

    # ── 9  SPAN LABELS ────────────────────────────────────────────────────────
    for i, sp in enumerate(spans):
        xm = (col_x[i] + col_x[i + 1]) / 2
        _label(fig, xm, Y_SPAN_LBL, f"<b>{sp['label']}</b>",
               _C["span_lbl"], size=11,
               bgcolor="rgba(0,0,0,0)")

    # ── 10  STIRRUP ZONE DIMENSION LINES (below beam) ─────────────────────────
    for st in cfg.get("stirrups", []):
        si      = st["span_index"]
        zone    = st["zone"]
        spacing = float(st["spacing"])
        count   = int(st["count"])
        zx0, zx1 = zone_bounds.get((si, zone), (col_x[si], col_x[si + 1]))

        _dim_line(fig, zx0, zx1, Y_DIM_ZONE,
                  f"{count}@{int(spacing)}",
                  color=_C["stirrup"], fontsize=9, above=False, tick_half=12)

    # ── 11  PASS / FAIL STATUS ────────────────────────────────────────────────
    for res in cfg.get("results", []):
        si     = res["span_index"]
        status = res["status"]
        U      = float(res["U"])
        xm     = (col_x[si] + col_x[si + 1]) / 2
        color  = _C["pass"] if status == "PASS" else _C["fail"]

        _label(fig, xm, Y_RESULT,
               f"<b>{status}</b>   U = {U:.2f}",
               color, size=12,
               bgcolor="rgba(15,20,30,0.85)",
               bordercolor=color, borderwidth=1, borderpad=5)

    # ── 12  LEGEND (top-right corner) ─────────────────────────────────────────
    items = [
        (_C["top_bar"],  "Cont. top bars"),
        (_C["bot_bar"],  "Cont. bottom bars"),
        (_C["sup_bar"],  "Support top bars"),
        (_C["mid_bar"],  "Midspan extra bars"),
        (_C["stirrup"],  "Stirrups"),
    ]
    lx0   = x_max - margin_r * 0.85
    ly    = Y_SPAN_LBL - 4
    seg_w = 55.0
    dy    = 26.0

    for j, (color, label) in enumerate(items):
        y_j = ly + j * dy
        _hline(fig, lx0, lx0 + seg_w, y_j, color, width=2.5)
        _label(fig, lx0 + seg_w + 8, y_j,
               label, color, size=9,
               xanchor="left", bgcolor="rgba(0,0,0,0)")

    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  Adapter  –  keeps the existing call-site in beam_workflow.py working
#  Signature: create_beam_elevation_plot(span_lengths, design_results, rebar_summaries)
# ─────────────────────────────────────────────────────────────────────────────

_SECTION_LABELS = {
    "Ext": "Exterior Span",
    "Mid": "Mid Span",
    "Int": "Interior Span",
}

_DEFAULT_SPAN_MM = {
    "Ext": 3500.0,
    "Mid": 4000.0,
    "Int": 3500.0,
}


def _parse_bar_label(label: str) -> tuple[int, int]:
    """
    Parse e.g. '3-DB25' → (3, 25).  Returns (0, 0) on failure.
    Falls back gracefully for 'No bars' or compound strings like '2-DB25 + 1-DB20'.
    """
    if not label or label == "No bars":
        return 0, 0
    first = label.split("+")[0].strip()
    try:
        parts = first.split("-DB")
        n   = int(parts[0].strip())
        dia = int(parts[1].strip())
        return n, dia
    except (IndexError, ValueError):
        return 0, 0


def create_beam_elevation_plot(
    span_lengths: dict,
    design_results: dict,
    rebar_summaries: dict,
    geom: SectionGeometry | None = None,
) -> go.Figure:
    """
    Public adapter consumed by beam_workflow.py.

    Converts the app's native dicts into a beam_config and calls
    draw_beam_elevation().
    """
    sec_keys = list(SECTIONS.keys())

    # ── Spans ─────────────────────────────────────────────────────────────────
    spans: list[dict] = []
    for key in sec_keys:
        L = float(span_lengths.get(key, _DEFAULT_SPAN_MM.get(key, 3500.0)))
        spans.append({"label": _SECTION_LABELS.get(key, key), "length": L})

    # ── Continuous bars  (take first span's summary as representative) ─────────
    top_labels    = [rebar_summaries.get(k, {}).get("Top",    "No bars") for k in sec_keys]
    bot_labels    = [rebar_summaries.get(k, {}).get("Bottom", "No bars") for k in sec_keys]
    top_label_rep = next((l for l in top_labels if l and l != "No bars"), "No bars")
    bot_label_rep = next((l for l in bot_labels if l and l != "No bars"), "No bars")
    _, top_dia    = _parse_bar_label(top_label_rep)
    _, bot_dia    = _parse_bar_label(bot_label_rep)

    # ── Support top bars at internal columns ──────────────────────────────────
    # Use the top-bar label from the span to the right of each internal support
    support_bars: list[dict] = []
    for i in range(1, len(sec_keys)):          # internal supports only
        left_key  = sec_keys[i - 1]
        right_key = sec_keys[i]
        left_L    = float(span_lengths.get(left_key,  3500.0))
        right_L   = float(span_lengths.get(right_key, 3500.0))
        lbl       = rebar_summaries.get(right_key, {}).get("Top", "No bars")
        if lbl and lbl != "No bars":
            support_bars.append({
                "support_index": i,
                "count":      _parse_bar_label(lbl)[0],
                "dia":        _parse_bar_label(lbl)[1],
                "label":      lbl,
                "left_ext":   left_L  * 0.25,
                "right_ext":  right_L * 0.25,
            })

    # ── Stirrups (one zone per span, using the stored spacing) ────────────────
    stirrups: list[dict] = []
    for si, key in enumerate(sec_keys):
        spacing = float(rebar_summaries.get(key, {}).get("StirrupSpacing", 150.0))
        L       = float(span_lengths.get(key, 3500.0))
        # Split: left zone = 2h, right zone = 2h (600 mm each), mid = rest
        zone_len_lr = min(600.0, L * 0.25)

        # left zone
        count_l = max(2, int(zone_len_lr / spacing) + 1)
        stirrups.append({"span_index": si, "zone": "left",
                         "spacing": spacing, "count": count_l})
        # right zone
        stirrups.append({"span_index": si, "zone": "right",
                         "spacing": spacing, "count": count_l})
        # mid zone (wider spacing capped at 150)
        spacing_mid = min(spacing * 2, 150.0)
        mid_len     = max(L - 2 * zone_len_lr, 200.0)
        count_m     = max(2, int(mid_len / spacing_mid) + 1)
        stirrups.append({"span_index": si, "zone": "mid",
                         "spacing": spacing_mid, "count": count_m})

    # ── Results ───────────────────────────────────────────────────────────────
    results: list[dict] = []
    for si, key in enumerate(sec_keys):
        r = design_results.get(key)
        if r is not None:
            results.append({
                "span_index": si,
                "status":     r.status,
                "U":          float(r.utilization),
            })

    # ── Beam section geometry (fallback values; sidebar changes these) ─────────
    # Approximate bar_dia from the first meaningful bot label
    bar_dia = max(bot_dia, top_dia, 16)

    cfg: dict = {
        "beam": {
            "height":  geom.height if geom else 600,
            "width":   geom.width if geom else 400,
            "cover":   geom.cover if geom else 40,
            "bar_dia": bar_dia,
        },
        "columns": {
            "width": 400,
            "above": 280,
            "below": 280,
        },
        "cantilever":      None,
        "spans":           spans,
        "continuous_bars": {
            "top":    {"count": _parse_bar_label(top_label_rep)[0],
                       "dia":   top_dia,
                       "label": top_label_rep if top_label_rep != "No bars" else "—"},
            "bottom": {"count": _parse_bar_label(bot_label_rep)[0],
                       "dia":   bot_dia,
                       "label": bot_label_rep if bot_label_rep != "No bars" else "—"},
        },
        "support_bars": support_bars,
        "midspan_bars": [],          # could be added when app exposes extra bottom bars
        "stirrups":     stirrups,
        "results":      results,
    }

    return draw_beam_elevation(cfg)
