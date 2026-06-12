"""
RC Section Visualizer — Cross-Section Plotter
"""
import numpy as np
import plotly.graph_objects as go
from models.section import SectionGeometry
from models.rebar import RebarRecord
from models.materials import ConcreteProps
from utils.math_helpers import bar_area
from analysis.properties import calculate_transformed_centroid

def create_section_plot(
    geom: SectionGeometry,
    records: list[RebarRecord],
    show_dims: bool,
    show_centroid: bool,
    show_na: bool,
    show_cover_box: bool,
    dark_mode: bool,
    concrete: ConcreteProps,
    fy: float  # MPa
) -> go.Figure:
    """
    Build the Plotly figure representing the beam cross section.
    """
    bg_paper  = "#ffffff" if dark_mode else "#0f1117"
    bg_plot   = "#f7f7f7" if dark_mode else "#13151f"
    conc_fill = "#d0cdc8" if dark_mode else "#1e2235"
    conc_line = "#a0a0a0" if dark_mode else "#3a4060"
    text_col  = "#222222" if dark_mode else "#c8d0e8"
    dim_col   = "#555555" if dark_mode else "#7c8db5"
    rebar_colors = {
        "Bottom": "#f87171",
        "Top": "#34d399",
        "Side": "#60a5fa",
        "Custom": "#fbbf24"
    }

    section_x_min = -geom.b / 2.0
    section_x_max = geom.b / 2.0
    section_y_min = -geom.h / 2.0
    section_y_max = geom.h / 2.0
    if geom.section_type == "Circular":
        section_x_min = section_y_min = -geom.D / 2.0
        section_x_max = section_y_max = geom.D / 2.0
    elif geom.section_type == "T-Beam":
        section_x_min = -geom.b_f / 2.0
        section_x_max = geom.b_f / 2.0

    x_min = section_x_min
    x_max = section_x_max
    y_min = section_y_min
    y_max = section_y_max
    for record in records:
        radius = record.dia / 2.0
        x_min = min(x_min, record.x - radius)
        x_max = max(x_max, record.x + radius)
        y_min = min(y_min, record.y - radius)
        y_max = max(y_max, record.y + radius)

    fig = go.Figure()

    # ── Concrete Outline ──────────────────────────────────────────────────────
    if geom.section_type == "Rectangular":
        fig.add_shape(dict(
            type="rect", x0=-geom.b/2, y0=-geom.h/2, x1=geom.b/2, y1=geom.h/2,
            fillcolor=conc_fill,
            line=dict(color=conc_line, width=2), layer="below"
        ))
    elif geom.section_type == "Circular":
        theta = np.linspace(0, 2*np.pi, 200)
        fig.add_trace(go.Scatter(
            x=(geom.D/2)*np.cos(theta), y=(geom.D/2)*np.sin(theta),
            fill="toself", fillcolor=conc_fill,
            line=dict(color=conc_line, width=2),
            mode="lines", hoverinfo="skip", showlegend=False
        ))
    elif geom.section_type == "T-Beam":
        px = [-geom.b_f/2, geom.b_f/2, geom.b_f/2, geom.b_w/2, geom.b_w/2, -geom.b_w/2, -geom.b_w/2, -geom.b_f/2, -geom.b_f/2]
        py = [geom.h/2, geom.h/2, geom.h/2-geom.t_f, geom.h/2-geom.t_f, -geom.h/2, -geom.h/2, geom.h/2-geom.t_f, geom.h/2-geom.t_f, geom.h/2]
        fig.add_trace(go.Scatter(
            x=px, y=py, fill="toself", fillcolor=conc_fill,
            line=dict(color=conc_line, width=2),
            mode="lines", hoverinfo="skip", showlegend=False
        ))

    # ── Cover Box ─────────────────────────────────────────────────────────────
    if show_cover_box and geom.section_type == "Rectangular":
        fig.add_shape(dict(
            type="rect",
            x0=-geom.b/2+geom.cover, y0=-geom.h/2+geom.cover,
            x1=geom.b/2-geom.cover, y1=geom.h/2-geom.cover,
            fillcolor="rgba(0,0,0,0)",
            line=dict(color="#f59e0b", width=1, dash="dot"), layer="above"
        ))

    # ── Dimension Lines ───────────────────────────────────────────────────────
    if show_dims and geom.section_type in ("Rectangular", "T-Beam"):
        offset = max(geom.b, geom.h) * 0.06 + 24
        y_min = min(y_min, -geom.h / 2.0 - offset * 1.25)
        x_max = max(x_max, geom.b / 2.0 + offset * 1.15)
        fig.add_annotation(
            x=0, y=-geom.h/2-offset, text=f"<b>B = {geom.b:.0f} mm</b>",
            showarrow=False, font=dict(color=dim_col, size=11)
        )
        fig.add_shape(dict(
            type="line", x0=-geom.b/2, y0=-geom.h/2-offset*0.6,
            x1=geom.b/2, y1=-geom.h/2-offset*0.6,
            line=dict(color=dim_col, width=1)
        ))
        fig.add_annotation(
            x=geom.b/2+offset*0.9, y=0, text=f"<b>H = {geom.h:.0f} mm</b>",
            showarrow=False, font=dict(color=dim_col, size=11), textangle=-90
        )
        fig.add_shape(dict(
            type="line", x0=geom.b/2+offset*0.5, y0=-geom.h/2,
            x1=geom.b/2+offset*0.5, y1=geom.h/2,
            line=dict(color=dim_col, width=1)
        ))

    # ── Transformed Centroid ──────────────────────────────────────────────────
    if show_centroid:
        Es = 200000.0
        Ec = concrete.Ec_mpa
        n = Es / Ec
        cx, cy = calculate_transformed_centroid(geom, records, n)
        fig.add_trace(go.Scatter(
            x=[cx], y=[cy], mode="markers",
            marker=dict(symbol="cross-thin", size=18, color="#f59e0b", line=dict(width=2.5)),
            name="Transformed Centroid",
            hovertemplate=f"Centroid<br>X={cx:.1f} mm<br>Y={cy:.1f} mm<extra></extra>"
        ))

    # ── Neutral Axis ──────────────────────────────────────────────────────────
    if show_na and records:
        x_lim = geom.D/2.0 if geom.section_type == "Circular" else geom.b/2.0
        y_top = geom.D/2.0 if geom.section_type == "Circular" else geom.h/2.0
        
        from analysis.capacity import calculate_flexural_capacity
        from analysis.properties import get_steel_area, calculate_effective_depth
        from models.materials import SteelProps
        from constants import MPA_TO_KSC
        
        As_bot = get_steel_area(records, "Bottom")
        As_top = get_steel_area(records, "Top")
        d_val = calculate_effective_depth(records, "Bottom", geom.h)
        dp_val = calculate_effective_depth(records, "Top", geom.h)
        
        d = d_val if d_val else geom.h - geom.cover - geom.stirrup_dia - 25.0
        dp = dp_val if dp_val else geom.cover + geom.stirrup_dia + 25.0
        
        steel_temp = SteelProps(fy_ksc=fy * MPA_TO_KSC, fyt_ksc=2400.0)
        
        capacity = calculate_flexural_capacity(geom, As_bot, As_top, d, dp, concrete, steel_temp)
        c = capacity.c_na
        if c > 0:
            y_na = y_top - c
            fig.add_shape(dict(
                type="line", x0=-x_lim, y0=y_na, x1=x_lim, y1=y_na,
                line=dict(color="#a78bfa", width=2, dash="dashdot")
            ))
            fig.add_annotation(
                x=x_lim, y=y_na, text=" NA", showarrow=False,
                font=dict(color="#a78bfa", size=11), xanchor="left"
            )

    # ── Draw Rebars ───────────────────────────────────────────────────────────
    layer_traces = {}
    for r in records:
        x_, y_, dia = r.x, r.y, r.dia
        count = r.count
        layer = r.layer
        color = rebar_colors.get(layer, "#fbbf24")
        theta = np.linspace(0, 2*np.pi, 60)
        r_bar = dia / 2.0
        
        hover = (f"<b>{r.bar_size}</b><br>Ø{dia:.0f} mm | {layer}<br>"
                 f"X={x_:.1f}, Y={y_:.1f} mm<br>A={bar_area(dia):.1f} mm²  Count={count}")
        
        if layer not in layer_traces:
            layer_traces[layer] = {"color": color}
            
        fig.add_trace(go.Scatter(
            x=x_+r_bar*np.cos(theta), y=y_+r_bar*np.sin(theta),
            fill="toself", fillcolor=color,
            line=dict(color="#0f1117", width=0.8),
            mode="lines", showlegend=False, hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=[x_], y=[y_], mode="markers",
            marker=dict(size=dia*0.55, color=color, opacity=0),
            showlegend=False,
            hovertemplate=hover+"<extra></extra>",
            name=layer
        ))

    # Add legend items for layers
    for lyr, info in layer_traces.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=info["color"]), name=f"{lyr} Bars"
        ))

    # Layout sizing & coloring
    fit_pad = max(geom.b, geom.h) * 0.035 + 18
    fig.update_layout(
        paper_bgcolor=bg_paper, plot_bgcolor=bg_plot,
        xaxis=dict(
            range=[x_min - fit_pad, x_max + fit_pad], scaleanchor="y", scaleratio=1,
            showgrid=True, gridcolor="#1e2235" if not dark_mode else "#e0e0e0",
            gridwidth=1, zeroline=True, zerolinecolor="#2a3050",
            tickfont=dict(color=text_col, size=10),
            title=dict(text="X (mm)", font=dict(color=text_col, size=11))
        ),
        yaxis=dict(
            range=[y_min - fit_pad, y_max + fit_pad],
            showgrid=True, gridcolor="#1e2235" if not dark_mode else "#e0e0e0",
            gridwidth=1, zeroline=True, zerolinecolor="#2a3050",
            tickfont=dict(color=text_col, size=10),
            title=dict(text="Y (mm)", font=dict(color=text_col, size=11))
        ),
        legend=dict(
            bgcolor="rgba(26,29,46,0.88)" if not dark_mode else "rgba(247,247,247,0.88)",
            bordercolor="#2a3050", borderwidth=1,
            font=dict(color=text_col, size=10),
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=20, r=20, t=48, b=30),
        height=460,
        hoverlabel=dict(bgcolor="#1a1d2e", font=dict(color="#e8eaf0")),
    )

    return fig
