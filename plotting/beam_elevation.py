import plotly.graph_objects as go

from constants import SECTIONS


def _bar_label(summary: dict, layer: str) -> str:
    value = summary.get(layer, "No bars")
    return value if value else "No bars"


def create_beam_elevation_plot(span_lengths: dict, design_results: dict, rebar_summaries: dict) -> go.Figure:
    fig = go.Figure()
    colors = {"PASS": "#22c55e", "FAIL": "#ef4444"}
    x0 = 0.0

    for sec_key, sec_label in SECTIONS.items():
        length = float(span_lengths.get(sec_key, 0.0))
        x1 = x0 + length
        result = design_results.get(sec_key)
        status = result.status if result else "PASS"
        color = colors.get(status, "#94a3b8")

        fig.add_shape(type="rect", x0=x0, y0=-0.22, x1=x1, y1=0.22, line=dict(color="#64748b", width=2), fillcolor="#172033")
        fig.add_shape(type="line", x0=x0, y0=-0.55, x1=x0, y1=0.55, line=dict(color="#cbd5e1", width=3))
        fig.add_annotation(x=(x0 + x1) / 2.0, y=0.68, text=f"<b>{sec_label}</b><br>{length:.0f} mm", showarrow=False, font=dict(color="#e5e7eb", size=11))
        if result:
            fig.add_annotation(x=(x0 + x1) / 2.0, y=-0.72, text=f"<b>{status}</b>  U={result.utilization:.2f}", showarrow=False, font=dict(color=color, size=12))

        summary = rebar_summaries.get(sec_key, {})
        fig.add_shape(type="line", x0=x0 + 0.08 * length, y0=0.34, x1=x1 - 0.08 * length, y1=0.34, line=dict(color="#34d399", width=5))
        fig.add_shape(type="line", x0=x0 + 0.05 * length, y0=-0.34, x1=x1 - 0.05 * length, y1=-0.34, line=dict(color="#f87171", width=5))
        fig.add_annotation(x=(x0 + x1) / 2.0, y=0.48, text=_bar_label(summary, "Top"), showarrow=False, font=dict(color="#bbf7d0", size=10))
        fig.add_annotation(x=(x0 + x1) / 2.0, y=-0.48, text=_bar_label(summary, "Bottom"), showarrow=False, font=dict(color="#fecaca", size=10))

        spacing = max(float(summary.get("StirrupSpacing", 150.0)), 50.0)
        marker_count = max(2, min(30, int(length / spacing) + 1))
        if marker_count > 1:
            dx = length / (marker_count - 1)
            for i in range(marker_count):
                xs = x0 + i * dx
                fig.add_shape(type="line", x0=xs, y0=-0.2, x1=xs, y1=0.2, line=dict(color="#60a5fa", width=1))
        fig.add_annotation(x=(x0 + x1) / 2.0, y=0.0, text=f"s = {spacing:.0f} mm", showarrow=False, font=dict(color="#bfdbfe", size=10))
        x0 = x1

    fig.add_shape(type="line", x0=x0, y0=-0.55, x1=x0, y1=0.55, line=dict(color="#cbd5e1", width=3))
    fig.update_xaxes(visible=False, range=[0, max(x0, 1.0)])
    fig.update_yaxes(visible=False, range=[-0.9, 0.9])
    fig.update_layout(
        paper_bgcolor="#0b0d14",
        plot_bgcolor="#0b0d14",
        margin=dict(l=20, r=20, t=20, b=20),
        height=330,
        showlegend=False,
    )
    return fig
