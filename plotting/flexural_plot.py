"""Flexural strain and stress-block visualization."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.capacity import CapacityResult
from constants import MPA_TO_KSC
from models.materials import ConcreteProps, SteelProps
from models.rebar import RebarRecord
from models.section import SectionGeometry
from plotting.label_placement import DiagramLabel, LabelPlacer, SubplotLayout
from utils.math_helpers import bar_area

N_TO_KGF = 1.0 / 9.80665


def _depth_from_compression_face(record: RebarRecord, h: float, pos_moment: bool) -> float:
    return (h / 2.0 - record.y) if pos_moment else (h / 2.0 + record.y)


def _grouped_layers(records: list[RebarRecord], h: float, pos_moment: bool) -> list[dict]:
    groups: dict[float, dict] = {}
    for record in records:
        depth = _depth_from_compression_face(record, h, pos_moment)
        key = round(depth, 1)
        group = groups.setdefault(
            key,
            {
                "depth": depth,
                "bar_count": 0,
                "area": 0.0,
                "descriptions": [],
            },
        )
        group["bar_count"] += record.count
        group["area"] += bar_area(record.dia) * record.count
        group["descriptions"].append(f"{record.count}-{record.bar_size} {record.layer}")
    return [groups[key] for key in sorted(groups)]


def _signed_strain_at(depth: float, c_na: float, eps_cu: float) -> float:
    return eps_cu * (c_na - depth) / c_na if c_na > 0.0 else 0.0


def _steel_response(
    depth: float,
    area: float,
    c_na: float,
    a: float,
    eps_cu: float,
    steel: SteelProps | None,
    concrete: ConcreteProps,
) -> tuple[float, float, float]:
    if steel is None:
        strain = _signed_strain_at(depth, c_na, eps_cu)
        return strain, 0.0, 0.0
    strain = _signed_strain_at(depth, c_na, eps_cu)
    stress_mpa = max(-steel.fy, min(steel.Es_mpa * strain, steel.fy))
    displaced_concrete = 0.85 * concrete.fc_prime if (strain > 0.0 and depth <= a) else 0.0
    force_n = area * (stress_mpa - displaced_concrete if strain > 0.0 else stress_mpa)
    return strain, stress_mpa, force_n


def build_layer_results_table(
    geom: SectionGeometry,
    records: list[RebarRecord],
    capacity: CapacityResult,
    pos_moment: bool,
    concrete: ConcreteProps,
    steel: SteelProps | None,
) -> pd.DataFrame:
    """Return per-layer strain, stress, and force values for the results table."""
    h = geom.h
    eps_cu = 0.003
    c_na = capacity.c_na
    a = capacity.a
    layer_groups = _grouped_layers(records, h, pos_moment)

    rows: list[dict] = []
    for idx, group in enumerate(layer_groups, start=1):
        depth = group["depth"]
        strain, stress_mpa, force_n = _steel_response(
            depth, group["area"], c_na, a, eps_cu, steel, concrete
        )
        rows.append(
            {
                "Layer": f"L{idx}",
                "Depth (mm)": round(depth, 1),
                "Bars": group["bar_count"],
                "Strain": f"{strain:.5f}",
                "Stress (MPa)": f"{stress_mpa:.0f}",
                "Force (kgf)": f"{force_n * N_TO_KGF:.0f}",
            }
        )
    return pd.DataFrame(rows)


def create_flexural_plot(
    geom: SectionGeometry,
    records: list[RebarRecord],
    capacity: CapacityResult,
    pos_moment: bool,
    concrete: ConcreteProps,
    d: float,
    dp: float,
    comp_lbl: str,
    tens_lbl: str,
    steel: SteelProps | None = None,
) -> go.Figure:
    """Build strain compatibility and stress-block panels for one analysis point."""
    h = geom.h
    a = capacity.a
    c_na = capacity.c_na
    eps_cu = 0.003
    n_to_tonf = 1.0 / 9806.65

    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.48, 0.52],
        subplot_titles=["Strain Diagram", "Stress Block / Steel Forces"],
        horizontal_spacing=0.06,
    )

    c_col = "#60a5fa"
    t_col = "#f87171"
    na_col = "#a78bfa"
    blk_col = "#4ade80"

    layer_groups = _grouped_layers(records, h, pos_moment)
    layer_strains: list[float] = []
    labels: list[DiagramLabel] = []
    eps_range = max(abs(eps_cu), abs(capacity.eps_s), 0.001) * 1.45

    def layer_id(index: int) -> str:
        return f"L{index}"

    def strain_side_anchor(strain: float) -> str:
        return "left" if strain >= 0.0 else "right"

    def strain_side_shift(strain: float) -> int:
        return 8 if strain >= 0.0 else -8

    if c_na > 0.0:
        eps_d = _signed_strain_at(d, c_na, eps_cu)
        eps_dp = _signed_strain_at(dp, c_na, eps_cu)
        preview_layer_strains = [_signed_strain_at(group["depth"], c_na, eps_cu) for group in layer_groups]
        eps_range = max(
            [abs(eps_cu), abs(capacity.eps_s), abs(eps_d), abs(eps_dp), 0.001]
            + [abs(item) for item in preview_layer_strains]
        ) * 1.45
        c_zone = max(0.0, min(c_na, h))

        if c_zone > 0.0:
            fig.add_shape(
                dict(
                    type="rect",
                    x0=-eps_range,
                    y0=0.0,
                    x1=eps_range,
                    y1=c_zone,
                    fillcolor="rgba(96,165,250,0.11)",
                    line=dict(width=0),
                    layer="below",
                ),
                row=1,
                col=1,
            )
            labels.append(
                DiagramLabel(
                    text="Compression zone",
                    anchor_x=-eps_range * 0.92,
                    anchor_y=c_zone * 0.5,
                    priority=10,
                    color=c_col,
                    col=1,
                    xanchor="left",
                    preferred_xshift=0,
                    preferred_yshift=0,
                )
            )
        if c_zone < h:
            fig.add_shape(
                dict(
                    type="rect",
                    x0=-eps_range,
                    y0=c_zone,
                    x1=eps_range,
                    y1=h,
                    fillcolor="rgba(248,113,113,0.09)",
                    line=dict(width=0),
                    layer="below",
                ),
                row=1,
                col=1,
            )
            labels.append(
                DiagramLabel(
                    text="Tension zone",
                    anchor_x=-eps_range * 0.92,
                    anchor_y=c_zone + (h - c_zone) * 0.5,
                    priority=10,
                    color=t_col,
                    col=1,
                    xanchor="left",
                    preferred_xshift=0,
                    preferred_yshift=0,
                )
            )

        fig.add_trace(
            go.Scatter(
                x=[eps_cu, 0.0, eps_d],
                y=[0.0, c_na, d],
                mode="lines+markers",
                line=dict(color="#e8eaf0", width=2),
                marker=dict(size=6, color="#e8eaf0"),
                showlegend=False,
                hovertemplate="strain=%{x:.5f}<br>depth=%{y:.1f} mm<extra></extra>",
            ),
            row=1,
            col=1,
        )
        fig.add_shape(
            dict(type="line", x0=0, y0=0, x1=0, y1=h, line=dict(color="#2a3050", width=1)),
            row=1,
            col=1,
        )
        neutral_width = max(abs(eps_cu), abs(eps_d), abs(eps_dp), 0.001) * 0.28
        fig.add_shape(
            dict(
                type="line",
                x0=-neutral_width,
                y0=c_na,
                x1=neutral_width,
                y1=c_na,
                line=dict(color=na_col, width=1, dash="dot"),
            ),
            row=1,
            col=1,
        )

        if a > 0.0:
            fig.add_shape(
                dict(
                    type="line",
                    x0=-eps_range,
                    y0=min(a, h),
                    x1=eps_range,
                    y1=min(a, h),
                    line=dict(color=blk_col, width=1, dash="dash"),
                ),
                row=1,
                col=1,
            )
            labels.append(
                DiagramLabel(
                    text="a",
                    anchor_x=eps_range * 0.82,
                    anchor_y=min(a, h),
                    priority=100,
                    color=blk_col,
                    col=1,
                    xanchor="left",
                    preferred_xshift=0,
                    preferred_yshift=-10,
                )
            )

        labels.extend(
            [
                DiagramLabel(
                    text="&epsilon;c",
                    anchor_x=eps_cu,
                    anchor_y=0.0,
                    priority=100,
                    color=c_col,
                    col=1,
                    xanchor="left",
                    preferred_xshift=8,
                    preferred_yshift=-10,
                ),
                DiagramLabel(
                    text="NA",
                    anchor_x=0.0,
                    anchor_y=c_na,
                    priority=100,
                    color=na_col,
                    col=1,
                    xanchor="left",
                    preferred_xshift=10,
                    preferred_yshift=-10,
                ),
                DiagramLabel(
                    text="&epsilon;t",
                    anchor_x=eps_d,
                    anchor_y=d,
                    priority=90,
                    color=t_col,
                    col=1,
                    xanchor=strain_side_anchor(eps_d),
                    preferred_xshift=strain_side_shift(eps_d),
                    preferred_yshift=10,
                ),
            ]
        )
        if dp > 0.0:
            labels.append(
                DiagramLabel(
                    text="&epsilon;sc",
                    anchor_x=eps_dp,
                    anchor_y=dp,
                    priority=80,
                    color=c_col,
                    col=1,
                    xanchor=strain_side_anchor(eps_dp),
                    preferred_xshift=strain_side_shift(eps_dp),
                    preferred_yshift=-10,
                )
            )

        for idx, group in enumerate(layer_groups, start=1):
            depth = group["depth"]
            strain = _signed_strain_at(depth, c_na, eps_cu)
            layer_strains.append(strain)
            color = c_col if strain >= 0.0 else t_col
            fig.add_trace(
                go.Scatter(
                    x=[strain],
                    y=[depth],
                    mode="markers",
                    marker=dict(size=7, color=color, symbol="diamond"),
                    showlegend=False,
                    hovertemplate=(
                        f"{layer_id(idx)} ({group['bar_count']} bars)<br>"
                        f"{'<br>'.join(group['descriptions'])}<br>"
                        "strain=%{x:.5f}<br>depth=%{y:.1f} mm<extra></extra>"
                    ),
                ),
                row=1,
                col=1,
            )
            labels.append(
                DiagramLabel(
                    text=f"&epsilon;s,{layer_id(idx)}",
                    anchor_x=strain,
                    anchor_y=depth,
                    priority=70,
                    color=color,
                    col=1,
                    xanchor=strain_side_anchor(strain),
                    preferred_xshift=strain_side_shift(strain),
                    preferred_yshift=12 if idx % 2 else -12,
                )
            )

    stress_c_mpa = 0.85 * concrete.fc_prime
    stress_c_ksc = stress_c_mpa * MPA_TO_KSC
    if a > 0.0:
        fig.add_trace(
            go.Scatter(
                x=[0, stress_c_ksc, stress_c_ksc, 0, 0],
                y=[0, 0, min(a, h), min(a, h), 0],
                fill="toself",
                fillcolor="rgba(74,222,128,0.22)",
                line=dict(color=blk_col, width=2),
                name=f"0.85f'c = {stress_c_ksc:.0f} ksc",
                hovertemplate=f"0.85f'c={stress_c_ksc:.0f} ksc<br>a={a:.1f} mm<extra></extra>",
            ),
            row=1,
            col=2,
        )
        labels.append(
            DiagramLabel(
                text="Cc",
                anchor_x=stress_c_ksc * 0.5,
                anchor_y=min(a, h) / 2.0,
                priority=30,
                color=blk_col,
                col=2,
                size=10,
                xanchor="center",
                preferred_xshift=0,
                preferred_yshift=0,
            )
        )

    if len(layer_groups) > 0 and dp > 0.0 and capacity.Cs != 0.0:
        labels.append(
            DiagramLabel(
                text="Cs",
                anchor_x=0.0,
                anchor_y=dp,
                priority=20,
                color=c_col,
                col=2,
                xanchor="left",
                preferred_xshift=8,
                preferred_yshift=12,
            )
        )
    if len(layer_groups) > 0 and d > 0.0 and capacity.T != 0.0:
        labels.append(
            DiagramLabel(
                text="Ts",
                anchor_x=0.0,
                anchor_y=d,
                priority=20,
                color=t_col,
                col=2,
                xanchor="left",
                preferred_xshift=8,
                preferred_yshift=12,
            )
        )

    if steel is not None and c_na > 0.0:
        for idx, group in enumerate(layer_groups, start=1):
            depth = group["depth"]
            area = group["area"]
            strain, stress_mpa, force_n = _steel_response(
                depth, area, c_na, a, eps_cu, steel, concrete
            )
            stress_ksc = stress_mpa * MPA_TO_KSC
            force_tf = force_n * n_to_tonf
            color = c_col if strain >= 0.0 else t_col
            fig.add_shape(
                dict(type="line", x0=0, y0=depth, x1=stress_ksc, y1=depth, line=dict(color=color, width=2)),
                row=1,
                col=2,
            )
            fig.add_trace(
                go.Scatter(
                    x=[stress_ksc],
                    y=[depth],
                    customdata=[[strain, force_tf, stress_mpa, force_n * N_TO_KGF]],
                    mode="markers",
                    marker=dict(size=7, color=color, symbol="diamond"),
                    showlegend=False,
                    hovertemplate=(
                        f"{layer_id(idx)} ({group['bar_count']} bars)<br>"
                        f"{'<br>'.join(group['descriptions'])}<br>"
                        "strain=%{customdata[0]:.5f}<br>"
                        "stress=%{customdata[2]:.0f} MPa<br>"
                        "force=%{customdata[3]:.0f} kgf<br>"
                        "fs=%{x:.0f} ksc<br>"
                        "Fs=%{customdata[1]:.2f} tonf<extra></extra>"
                    ),
                ),
                row=1,
                col=2,
            )
            stress_anchor = "left" if stress_ksc >= 0.0 else "right"
            stress_shift = 8 if stress_ksc >= 0.0 else -8
            labels.append(
                DiagramLabel(
                    text=f"{'fsc' if strain >= 0.0 else 'fs'},{layer_id(idx)}",
                    anchor_x=stress_ksc,
                    anchor_y=depth,
                    priority=50,
                    color=color,
                    col=2,
                    xanchor=stress_anchor,
                    preferred_xshift=stress_shift,
                    preferred_yshift=10 if idx % 2 else -10,
                )
            )

    ax_opts = dict(showgrid=True, gridcolor="#1e2235", gridwidth=1, tickfont=dict(color="#c8d0e8", size=9), zeroline=False)
    y_range = [h * 1.12, -h * 0.12]
    eps_range = max([abs(eps_cu), abs(capacity.eps_s), 0.001] + [abs(item) for item in layer_strains]) * 1.45
    steel_limit = steel.fy * MPA_TO_KSC * 1.15 if steel is not None else 0.0
    stress_limit = max(stress_c_ksc * 1.8, steel_limit * 1.15, 1.0)

    strain_layout = SubplotLayout(
        x_range=(-eps_range, eps_range),
        y_range=(y_range[0], y_range[1]),
        width_px=300.0,
        height_px=400.0,
    )
    stress_layout = SubplotLayout(
        x_range=(-stress_limit, stress_limit),
        y_range=(y_range[0], y_range[1]),
        width_px=320.0,
        height_px=400.0,
        margin_left_px=20.0,
    )
    strain_placer = LabelPlacer(strain_layout)
    stress_placer = LabelPlacer(stress_layout)
    strain_labels = [label for label in labels if label.col == 1]
    stress_labels = [label for label in labels if label.col == 2]
    strain_placer.place_all(strain_labels)
    stress_placer.place_all(stress_labels)
    strain_placer.apply_to_figure(fig, strain_labels)
    stress_placer.apply_to_figure(fig, stress_labels)
    for col_idx in [1, 2]:
        fig.update_yaxes(
            autorange=False,
            range=y_range,
            title_text="Depth (mm)" if col_idx == 1 else "",
            title_font=dict(color="#7c8db5", size=8),
            **ax_opts,
            row=1,
            col=col_idx,
        )

    fig.update_xaxes(range=[-eps_range, eps_range], title_text="strain", title_font=dict(color="#7c8db5", size=8), **ax_opts, row=1, col=1)
    fig.update_xaxes(range=[-stress_limit, stress_limit], title_text="stress (ksc)", title_font=dict(color="#7c8db5", size=8), **ax_opts, row=1, col=2)

    fig.update_layout(
        paper_bgcolor="#0f1117",
        plot_bgcolor="#13151f",
        height=500,
        margin=dict(l=8, r=12, t=46, b=12),
        legend=dict(
            bgcolor="rgba(26,29,46,0.9)",
            bordercolor="#2a3050",
            borderwidth=1,
            font=dict(color="#c8d0e8", size=9),
            orientation="h",
            y=-0.08,
            x=0.5,
            xanchor="center",
        ),
        hoverlabel=dict(bgcolor="#1a1d2e", font=dict(color="#e8eaf0")),
    )
    return fig
