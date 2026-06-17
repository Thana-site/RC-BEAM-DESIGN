import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis.capacity import CapacityResult
from analysis.design import CalculationStep, calculate_design_result
from constants import MPA_TO_KSC, SECTIONS
from models.materials import ConcreteProps, SteelProps
from models.rebar import rebar_df_to_records
from models.section import SectionGeometry
from plotting.beam_elevation import create_beam_elevation_plot
from plotting.flexural_plot import create_flexural_plot
from plotting.section_plot import create_section_plot
from ui.section_tab import (
    _render_rebar_editors,
    _render_rebar_summary,
    _render_section_properties,
    _render_validation_warnings,
)
from utils.math_helpers import bar_area
from utils import update_session_state_properties


DEFAULT_FORCES = {
    "Ext": {"Mu": 18.0, "Vu": 9.0, "L": 3500.0, "s": 150.0},
    "Mid": {"Mu": 24.0, "Vu": 11.0, "L": 4000.0, "s": 150.0},
    "Int": {"Mu": 22.0, "Vu": 13.0, "L": 3500.0, "s": 125.0},
}

COMPARISON_ORDER = ("Ext", "Mid", "Int")
SECTION_SHORT_LABELS = {
    "Ext": "EXT - Exterior Column",
    "Mid": "MID - Middle Column",
    "Int": "INT - Interior Column",
}


def render_beam_design_workflow(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    display_opts: dict,
) -> tuple[dict, dict, dict]:
    st.markdown('<div class="section-tag">RC Beam Design Platform</div>', unsafe_allow_html=True)
    st.caption("Every reported result below carries its formula, numerical substitution, unit, reference, and explanation.")

    design_results = {}
    rebar_summaries = {}
    span_lengths = {}

    st.markdown('<div class="section-tag">Section Comparison Dashboard</div>', unsafe_allow_html=True)
    st.caption("EXT, MID, and INT are shown together so section behavior, strain compatibility, stress block forces, and design capacity can be compared directly.")
    section_columns = st.columns(3, gap="small")
    for column, sec_key in zip(section_columns, COMPARISON_ORDER):
        with column:
            result, summary, span_length = _render_span_panel(sec_key, geom, concrete, steel, display_opts)
            design_results[sec_key] = result
            rebar_summaries[sec_key] = summary
            span_lengths[sec_key] = span_length

    st.divider()
    st.markdown('<div class="section-tag">Beam Detailing Elevation</div>', unsafe_allow_html=True)
    # Pass geom so the elevation uses real beam height, width, and cover
    fig = create_beam_elevation_plot(span_lengths, design_results, rebar_summaries, geom=geom)
    st.plotly_chart(fig, use_container_width=True, key="beam_elevation")

    return design_results, rebar_summaries, span_lengths


def render_traceability_center(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    design_results: dict,
    rebar_summaries: dict,
    span_lengths: dict,
) -> None:
    audit_mode = st.toggle(
        "Audit Mode",
        value=st.session_state.get("audit_mode", False),
        help="Show all intermediate calculations, assumptions, references, and pass/fail criteria.",
        key="audit_mode",
    )
    _render_traceability_center(
        geom,
        concrete,
        steel,
        design_results,
        rebar_summaries,
        span_lengths,
        audit_mode,
    )


def render_calculation_details(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    design_results: dict,
) -> None:
    st.markdown('<div class="section-tag">Engineering Calculations</div>', unsafe_allow_html=True)
    st.caption("Step-by-step calculation sheet for the currently selected interaction-diagram point.")
    if not design_results:
        st.info("Run the Beam Design tab first to generate section results.")
        return

    sec_key = st.selectbox(
        "Section",
        list(COMPARISON_ORDER),
        format_func=lambda key: SECTION_SHORT_LABELS.get(key, SECTIONS[key]),
        key="calculation_details_section",
    )
    result = design_results[sec_key]
    records = _get_section_records(sec_key)
    pos_moment, _, _, d, dp, comp_lbl, tens_lbl = _section_flexural_inputs(sec_key, geom)
    selected_c = float(st.session_state.get(f"pm_selected_c_{sec_key}", result.capacity.c_na))
    response = _section_response_at_c(geom, concrete, steel, records, selected_c, pos_moment)
    capacity = response["capacity"]
    layer_rows = response["layers"]
    a = capacity.a
    cc_force_n, cc_depth = _concrete_block_force(geom, concrete, a)
    orientation = 1.0 if pos_moment else -1.0

    st.markdown(
        f'<div class="info-box"><b>{SECTION_SHORT_LABELS.get(sec_key, SECTIONS[sec_key])}</b><br>'
        f'Selected interaction point: M = {response["M_tfm"]:.2f} tonf-m, '
        f'P = {response["P_tf"]:.2f} tonf, c = {selected_c:.2f} mm<br>'
        f'Compression face: {comp_lbl}; tension face: {tens_lbl}</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-tag">1. Input Parameters</div>', unsafe_allow_html=True)
    input_rows = [
        {"Parameter": "b", "Description": "Section width", "Value": f"{geom.b:.2f}", "Unit": "mm"},
        {"Parameter": "h", "Description": "Section depth", "Value": f"{geom.h:.2f}", "Unit": "mm"},
        {"Parameter": "fc'", "Description": "Concrete compressive strength", "Value": f"{concrete.fc_prime:.2f}", "Unit": "MPa"},
        {"Parameter": "fy", "Description": "Steel yield strength", "Value": f"{steel.fy:.2f}", "Unit": "MPa"},
        {"Parameter": "Es", "Description": "Steel modulus", "Value": f"{steel.Es_mpa:.0f}", "Unit": "MPa"},
        {"Parameter": "eps_cu", "Description": "Extreme concrete compression strain", "Value": "0.00300", "Unit": "-"},
        {"Parameter": "beta1", "Description": "Whitney stress block factor", "Value": f"{concrete.beta1:.3f}", "Unit": "-"},
        {"Parameter": "c", "Description": "Neutral axis depth", "Value": f"{capacity.c_na:.2f}", "Unit": "mm"},
        {"Parameter": "a", "Description": "beta1 x c", "Value": f"{capacity.a:.2f}", "Unit": "mm"},
        {"Parameter": "d", "Description": "Tension steel effective depth", "Value": f"{d:.2f}", "Unit": "mm"},
        {"Parameter": "d'", "Description": "Compression steel effective depth", "Value": f"{dp:.2f}", "Unit": "mm"},
    ]
    st.dataframe(pd.DataFrame(input_rows), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-tag">2. Strain Compatibility</div>', unsafe_allow_html=True)
    strain_rows = []
    for row in layer_rows:
        strain_rows.append(
            {
                "Layer": row["Layer"],
                "Bars": row["Bars"],
                "Formula": "eps_s = eps_cu x (c - d_i) / c",
                "Substitution": f"eps_{row['Layer']} = 0.003 x ({capacity.c_na:.2f} - {row['depth']:.2f}) / {capacity.c_na:.2f}",
                "Result": f"{row['strain']:.5f}",
                "Unit": "-",
            }
        )
    st.dataframe(pd.DataFrame(strain_rows), use_container_width=True, hide_index=True, height=min(360, 80 + 36 * max(len(strain_rows), 1)))

    st.markdown('<div class="section-tag">3. Steel Stress Calculation</div>', unsafe_allow_html=True)
    stress_rows = []
    for row in layer_rows:
        fs_raw = steel.Es_mpa * row["strain"]
        stress_rows.append(
            {
                "Layer": row["Layer"],
                "Bars": row["Bars"],
                "Formula": "fs = Es x eps_s;  |fs| <= fy",
                "Substitution": f"fs = {steel.Es_mpa:.0f} x {row['strain']:.5f} = {fs_raw:.1f} MPa",
                "Limit": f"fy = +/-{steel.fy:.1f} MPa",
                "Final fs": f"{row['stress_mpa']:.1f}",
                "Unit": "MPa",
                "Status": row["Yield Status"],
            }
        )
    st.dataframe(pd.DataFrame(stress_rows), use_container_width=True, hide_index=True, height=min(360, 80 + 36 * max(len(stress_rows), 1)))

    st.markdown('<div class="section-tag">4. Steel Force Calculation</div>', unsafe_allow_html=True)
    force_rows = []
    for row in layer_rows:
        area = row["area_mm2"]
        displaced = 0.85 * concrete.fc_prime if (row["strain"] > 0.0 and row["depth"] <= a) else 0.0
        net_stress = row["stress_mpa"] - displaced if displaced else row["stress_mpa"]
        force_rows.append(
            {
                "Layer": row["Layer"],
                "Bars": row["Bars"],
                "As": f"{area:.1f}",
                "Formula": "Fs = As x fs_net",
                "Substitution": f"Fs = {area:.1f} x ({row['stress_mpa']:.1f} - {displaced:.1f})",
                "Result": f"{row['force_n']:.0f}",
                "Force": f"{row['force_n'] / 9806.65:.2f}",
                "Unit": "N / tonf",
                "Note": "Concrete displaced" if displaced else "Steel only",
            }
        )
    st.dataframe(pd.DataFrame(force_rows), use_container_width=True, hide_index=True, height=min(380, 80 + 36 * max(len(force_rows), 1)))

    st.markdown('<div class="section-tag">5. Concrete Compression Block</div>', unsafe_allow_html=True)
    stress_block = 0.85 * concrete.fc_prime
    concrete_rows = [
        {
            "Step": "Stress block depth",
            "Formula": "a = beta1 x c",
            "Substitution": f"a = {concrete.beta1:.3f} x {capacity.c_na:.2f}",
            "Result": f"{a:.2f}",
            "Unit": "mm",
        },
        {
            "Step": "Stress block intensity",
            "Formula": "0.85 fc'",
            "Substitution": f"0.85 x {concrete.fc_prime:.2f}",
            "Result": f"{stress_block:.2f}",
            "Unit": "MPa",
        },
        {
            "Step": "Concrete compression force",
            "Formula": "Cc = 0.85 fc' x b x a",
            "Substitution": f"Cc = 0.85 x {concrete.fc_prime:.2f} x {geom.b:.2f} x {min(a, geom.h):.2f}",
            "Result": f"{cc_force_n:.0f} N = {cc_force_n / 9806.65:.2f} tonf",
            "Unit": "N / tonf",
        },
        {
            "Step": "Concrete force location",
            "Formula": "yc = a / 2",
            "Substitution": f"yc = {min(a, geom.h):.2f} / 2",
            "Result": f"{cc_depth:.2f}",
            "Unit": "mm from compression face",
        },
    ]
    st.dataframe(pd.DataFrame(concrete_rows), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-tag">6. Force Equilibrium</div>', unsafe_allow_html=True)
    compression_steel_n = sum(row["force_n"] for row in layer_rows if row["force_n"] > 0.0)
    tension_steel_n = abs(sum(row["force_n"] for row in layer_rows if row["force_n"] < 0.0))
    sigma_c_n = cc_force_n + compression_steel_n
    pn_n = cc_force_n + sum(row["force_n"] for row in layer_rows)
    equilibrium_rows = [
        {"Item": "Concrete compression", "Symbol": "Cc", "Value": f"{cc_force_n / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Compression steel", "Symbol": "Cs", "Value": f"{compression_steel_n / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Tension steel", "Symbol": "Ts", "Value": f"{tension_steel_n / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Total compression", "Symbol": "Sigma C = Cc + Cs", "Value": f"{sigma_c_n / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Total tension", "Symbol": "Sigma T = Ts", "Value": f"{tension_steel_n / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Nominal axial force", "Symbol": "Pn = Sigma C - Sigma T", "Value": f"{pn_n / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Force balance check", "Symbol": "Cc + Sum Fs", "Value": f"{response['P_tf']:.2f}", "Unit": "tonf"},
    ]
    st.dataframe(pd.DataFrame(equilibrium_rows), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-tag">7. Moment Calculation</div>', unsafe_allow_html=True)
    moment_rows = [
        {
            "Component": "Concrete Cc",
            "Formula": "M = F x (h/2 - y)",
            "Substitution": f"{cc_force_n / 9806.65:.2f} x ({geom.h / 2.0:.2f} - {cc_depth:.2f})",
            "Lever Arm (mm)": f"{geom.h / 2.0 - cc_depth:.2f}",
            "Moment": f"{orientation * cc_force_n * (geom.h / 2.0 - cc_depth) / 9806650.0:.2f}",
            "Unit": "tonf-m",
        }
    ]
    for row in layer_rows:
        lever = geom.h / 2.0 - row["depth"]
        moment_tfm = orientation * row["force_n"] * lever / 9806650.0
        moment_rows.append(
            {
                "Component": row["Layer"],
                "Bars": row["Bars"],
                "Formula": "M = Fs x (h/2 - d_i)",
                "Substitution": f"{row['force_n'] / 9806.65:.2f} x ({geom.h / 2.0:.2f} - {row['depth']:.2f})",
                "Lever Arm (mm)": f"{lever:.2f}",
                "Moment": f"{moment_tfm:.2f}",
                "Unit": "tonf-m",
            }
        )
    st.dataframe(pd.DataFrame(moment_rows), use_container_width=True, hide_index=True, height=min(420, 100 + 36 * max(len(moment_rows), 1)))
    st.markdown(
        f"""
        <div class="info-box">
          <b>Moment summary</b><br>
          Mn = Sum(F x z) = {response["M_tfm"]:.2f} tonf-m<br>
          |Mn| = {capacity.Mn / 9806650.0:.2f} tonf-m<br>
          phi = {capacity.phi:.3f}<br>
          phi Mn = {capacity.phi_Mn / 9806650.0:.2f} tonf-m
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_span_panel(
    sec_key: str,
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    display_opts: dict,
):
    sec_label = SECTION_SHORT_LABELS.get(sec_key, SECTIONS[sec_key])
    st.markdown(f"#### {sec_label}")
    with st.container(border=True):
        st.markdown('<div class="section-tag">Section Geometry</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="info-box"><b>b</b> = {geom.b:.0f} mm<br><b>h</b> = {geom.h:.0f} mm<br>'
            f'<b>cover</b> = {geom.cover:.0f} mm<br><b>stirrup dia</b> = {geom.stirrup_dia:.0f} mm</div>',
            unsafe_allow_html=True,
        )

    records = _get_section_records(sec_key)
    with st.expander("Edit reinforcement layout", expanded=False):
        edited_df = _render_rebar_editors(sec_key, geom)
        records = rebar_df_to_records(edited_df)
        update_session_state_properties(geom)
        _render_validation_warnings(geom, records)
        _render_single_page_rebar_tools(sec_key, geom)

    with st.container(border=True):
        st.markdown('<div class="section-tag">Section Drawing</div>', unsafe_allow_html=True)
        fig = create_section_plot(
            geom,
            records,
            show_dims=display_opts["show_dims"],
            show_centroid=display_opts["show_centroid"],
            show_na=display_opts["show_na"],
            show_cover_box=display_opts["show_cover_box"],
            dark_mode=display_opts["dark_mode"],
            concrete=concrete,
            fy=steel.fy,
        )
        fig.update_layout(height=_responsive_section_height(geom, compact=True), margin=dict(l=8, r=8, t=48, b=24))
        st.plotly_chart(fig, use_container_width=True, key=f"single_section_{sec_key}")

    with st.expander("Material and design forces", expanded=False):
        st.markdown('<div class="section-tag">Forces</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="info-box"><b>f&apos;c</b> = {concrete.fc_ksc:.0f} ksc ({concrete.fc_prime:.1f} MPa)<br>'
            f'<b>fy</b> = {steel.fy_ksc:.0f} ksc ({steel.fy:.0f} MPa)</div>',
            unsafe_allow_html=True,
        )
        defaults = DEFAULT_FORCES[sec_key]
        c1, c2 = st.columns(2)
        mu_default = -defaults["Mu"] if sec_key == "Int" else defaults["Mu"]
        mu = c1.number_input("Mu (tonf-m)", value=mu_default, step=1.0, key=f"Mu_{sec_key}")
        vu = c2.number_input("Vu (tonf)", value=defaults["Vu"], step=1.0, key=f"Vu_{sec_key}")
        c3, c4 = st.columns(2)
        span_length = c3.number_input("Span L (mm)", min_value=1000.0, value=defaults["L"], step=250.0, key=f"L_{sec_key}")
        stirrup_spacing = c4.number_input("Stirrup s (mm)", min_value=50.0, value=defaults["s"], step=25.0, key=f"s_{sec_key}")

    pos_moment, provided_as, compression_as, d, dp, _, _ = _section_flexural_inputs(sec_key, geom)

    result = calculate_design_result(
        geom,
        concrete,
        steel,
        provided_as,
        compression_as,
        d,
        dp,
        mu,
        vu,
        stirrup_spacing,
    )

    selected_point = _render_interaction_point_selector(geom, concrete, steel, sec_key, result, compact=True, key_prefix="design")
    with st.container(border=True):
        _render_strain_stress_block(geom, concrete, steel, sec_key, result, selected_point, compact=True, key_prefix="design")

    with st.container(border=True):
        st.markdown('<div class="section-tag">Reinforcement Summary</div>', unsafe_allow_html=True)
        _render_compact_reinforcement_summary(sec_key, stirrup_spacing, geom.stirrup_dia)

    with st.container(border=True):
        st.markdown('<div class="section-tag">Key Design Results</div>', unsafe_allow_html=True)
        _render_design_dashboard(result)

    with st.expander("Section properties and full bar table", expanded=False):
        _render_section_properties(geom, records, concrete, steel, sec_key)
        _render_rebar_summary(geom, records)

    return result, _summarize_rebar(sec_key, stirrup_spacing, geom.stirrup_dia), span_length


def _responsive_section_height(geom: SectionGeometry, compact: bool = False) -> int:
    aspect = geom.h / max(geom.b, 1.0)
    if compact:
        return int(max(320, min(430, 280 + aspect * 70)))
    return int(max(340, min(560, 260 + aspect * 110)))


def _section_flexural_inputs(sec_key: str, geom: SectionGeometry) -> tuple[bool, float, float, float, float, str, str]:
    pos_moment = sec_key != "Int"
    if pos_moment:
        provided_as = st.session_state[f"As_bot_{sec_key}"]
        compression_as = st.session_state[f"As_top_{sec_key}"]
        d = st.session_state.get(f"d_bot_{sec_key}") or geom.h - geom.cover - geom.stirrup_dia - 25.0
        dp = st.session_state.get(f"d_top_{sec_key}") or geom.cover + geom.stirrup_dia + 25.0
        comp_lbl = "Top compression zone"
        tens_lbl = "Bottom tension zone"
    else:
        provided_as = st.session_state[f"As_top_{sec_key}"]
        compression_as = st.session_state[f"As_bot_{sec_key}"]
        d_top = st.session_state.get(f"d_top_{sec_key}") or geom.cover + geom.stirrup_dia + 25.0
        d_bot = st.session_state.get(f"d_bot_{sec_key}") or geom.h - geom.cover - geom.stirrup_dia - 25.0
        d = geom.h - d_top
        dp = geom.h - d_bot
        comp_lbl = "Bottom compression zone"
        tens_lbl = "Top tension zone"
    return pos_moment, provided_as, compression_as, d, dp, comp_lbl, tens_lbl


def _render_design_dashboard(result) -> None:
    color = "#22c55e" if result.status == "PASS" else "#ef4444"
    st.markdown(
        f"""
        <div class="metric-card" style="border-left:4px solid {color}">
          <div class="metric-label">Design Status</div>
          <div class="metric-value" style="color:{color}">{result.status}
            <span class="metric-unit">U = {result.utilization:.2f}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    m1, m2 = st.columns(2)
    _metric(m1, "Required As", result.required_As, "mm2", "#fbbf24")
    _metric(m2, "Provided As", result.provided_As, "mm2", "#e5e7eb")
    m3, m4 = st.columns(2)
    _metric(m3, "Phi Mn / Mu", result.phi_Mn_tfm / abs(result.Mu_tfm) if result.Mu_tfm else 0.0, "", "#60a5fa")
    _metric(m4, "Phi Vn / Vu", result.phi_Vn_tf / abs(result.Vu_tf) if result.Vu_tf else 0.0, "", "#60a5fa")
    st.caption(f"Phi Mn = {result.phi_Mn_tfm:.2f} tonf-m | Phi Vn = {result.phi_Vn_tf:.2f} tonf")


def _metric(col, label: str, value: float, unit: str, color: str) -> None:
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
              <div class="metric-label">{label}</div>
              <div class="metric-value" style="color:{color}">{value:.2f}<span class="metric-unit">{unit}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_compact_reinforcement_summary(sec_key: str, stirrup_spacing: float, stirrup_dia: float) -> None:
    summary = _summarize_rebar(sec_key, stirrup_spacing, stirrup_dia)
    st.dataframe(
        pd.DataFrame(
            [
                {"Item": "Top reinforcement", "Value": summary["Top"]},
                {"Item": "Bottom reinforcement", "Value": summary["Bottom"]},
                {"Item": "Stirrups", "Value": f"2 legs, dia {summary['StirrupDia']:.0f} @ {summary['StirrupSpacing']:.0f} mm"},
            ]
        ),
        use_container_width=True,
        hide_index=True,
        height=145,
    )


def _render_single_page_rebar_tools(sec_key: str, geom: SectionGeometry) -> None:
    from analysis.rebar_generator import generate_rebar_coordinates, get_row_preview_y
    from constants import STANDARD_BARS

    df_bot_key = f"rebar_bot_{sec_key}"
    df_top_key = f"rebar_top_{sec_key}"

    st.markdown('<div class="section-tag" style="margin-top:8px">Add Rebar Row</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    rl_layer = c1.selectbox("Layer", ["Bottom", "Top", "Side"], key=f"sp_rl_layer_{sec_key}")
    rl_bar = c2.selectbox("Bar", list(STANDARD_BARS.keys()), index=list(STANDARD_BARS.keys()).index("DB25"), key=f"sp_rl_bar_{sec_key}")
    rl_n = c3.number_input("N bars" + ("/side" if rl_layer == "Side" else ""), 1, 30, 3, step=1, key=f"sp_rl_n_{sec_key}")

    c4, c5 = st.columns(2)
    if rl_layer in ("Bottom", "Top"):
        rl_rownum = c4.number_input("Row #", 1, 6, 1, step=1, key=f"sp_rl_rownum_{sec_key}")
    else:
        rl_rownum = 1
        c4.caption("Both side faces")
    rl_smode = c5.radio("Spacing", ["Auto", "Fixed"], key=f"sp_rl_smode_{sec_key}", horizontal=True)

    rl_fixed_s = 100.0
    if rl_smode == "Fixed":
        rl_fixed_s = st.number_input("c/c spacing (mm)", 10, 2000, 100, step=5, key=f"sp_rl_fixeds_{sec_key}")

    dia = float(STANDARD_BARS[rl_bar])
    if rl_layer in ("Bottom", "Top"):
        y_prev = get_row_preview_y(geom, rl_layer, dia, rl_rownum)
        st.caption(f"Preview: {rl_n} x {rl_bar} at Y = {y_prev} mm")
    else:
        st.caption(f"Preview: {rl_n} x {rl_bar} per side, {rl_n * 2} bars total")

    if st.button("Add row", key=f"sp_rl_add_{sec_key}", use_container_width=True):
        new_coords = generate_rebar_coordinates(geom, rl_layer, rl_bar, dia, rl_n, rl_rownum, rl_smode, float(rl_fixed_s))
        new_df = pd.DataFrame([r.to_dict() for r in new_coords])
        target_key = df_top_key if rl_layer == "Top" else df_bot_key
        st.session_state[target_key] = pd.concat([st.session_state[target_key], new_df], ignore_index=True)
        st.rerun()

    st.markdown('<div class="section-tag" style="margin-top:8px">Copy Section Rebar</div>', unsafe_allow_html=True)
    other_secs = [s for s in SECTIONS if s != sec_key]
    copy_cols = st.columns(len(other_secs))
    for col, src in zip(copy_cols, other_secs):
        if col.button(f"Copy {src}", key=f"sp_copy_{src}_{sec_key}", use_container_width=True):
            st.session_state[df_bot_key] = st.session_state[f"rebar_bot_{src}"].copy()
            st.session_state[df_top_key] = st.session_state[f"rebar_top_{src}"].copy()
            st.rerun()


def _summarize_rebar(sec_key: str, stirrup_spacing: float, stirrup_dia: float) -> dict:
    df_all = pd.concat(
        [st.session_state[f"rebar_bot_{sec_key}"], st.session_state[f"rebar_top_{sec_key}"]],
        ignore_index=True,
    )
    records = rebar_df_to_records(df_all)
    summary = {"Top": "", "Bottom": "", "StirrupSpacing": stirrup_spacing, "StirrupDia": stirrup_dia}
    for layer in ("Top", "Bottom"):
        layer_records = [r for r in records if r.layer == layer]
        if not layer_records:
            summary[layer] = "No bars"
            continue
        grouped = {}
        for r in layer_records:
            grouped[r.bar_size] = grouped.get(r.bar_size, 0) + r.count
        summary[layer] = " + ".join(f"{count}-{bar}" for bar, count in grouped.items())
    return summary


def _render_traceability_center(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    design_results: dict,
    rebar_summaries: dict,
    span_lengths: dict,
    audit_mode: bool,
) -> None:
    st.markdown('<div class="section-tag">Formula | Calculation | Notation | References</div>', unsafe_allow_html=True)
    formula_tab, calculation_tab, notation_tab, reference_tab, report_tab = st.tabs(
        ["Formula Panel", "Calculation Audit", "Notation Panel", "References", "Report"]
    )

    with formula_tab:
        _render_formula_panel(design_results)

    with calculation_tab:
        _render_calculation_audit(geom, concrete, steel, design_results, audit_mode)

    with notation_tab:
        _render_interactive_notation(design_results)

    with reference_tab:
        _render_reference_panel(design_results)

    with report_tab:
        _render_report_panel(geom, concrete, steel, design_results, rebar_summaries, span_lengths)


def _render_formula_panel(design_results: dict) -> None:
    st.markdown('<div class="section-tag">Formula Library</div>', unsafe_allow_html=True)
    formulas = _unique_steps(design_results)
    formula_rows = [
        {
            "Variable": step.variable_name,
            "Symbol": step.symbol,
            "Equation": step.formula,
            "Unit": step.unit,
            "Applicability": _formula_applicability(step.variable_name),
            "Assumptions": _formula_assumptions(step.variable_name),
            "Code reference": step.reference,
        }
        for step in formulas
    ]
    st.dataframe(pd.DataFrame(formula_rows), use_container_width=True, hide_index=True, height=360)

    selected = st.selectbox(
        "Formula detail",
        [step.variable_name for step in formulas],
        format_func=lambda name: _step_by_name(formulas, name).symbol + " - " + name,
        key="formula_detail_select",
    )
    step = _step_by_name(formulas, selected)
    st.markdown(
        f"""
        <div class="info-box">
          <b>{step.symbol}</b><br>
          Formula: <code>{step.formula}</code><br>
          Unit: {step.unit}<br>
          Applicability: {_formula_applicability(step.variable_name)}<br>
          Assumptions: {_formula_assumptions(step.variable_name)}<br>
          Reference: {step.reference}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_calculation_audit(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    design_results: dict,
    audit_mode: bool,
) -> None:
    st.markdown('<div class="section-tag">Calculation Transparency</div>', unsafe_allow_html=True)
    sec_key = st.selectbox(
        "Section",
        list(SECTIONS.keys()),
        format_func=lambda key: SECTIONS[key],
        key="audit_section_select",
    )
    result = design_results[sec_key]
    summary_rows = [
        {"Result": "As_required", "Value": f"{result.required_As:.2f}", "Unit": "mm2", "Status": "TRACEABLE"},
        {"Result": "As_provided", "Value": f"{result.provided_As:.2f}", "Unit": "mm2", "Status": "TRACEABLE"},
        {"Result": "phiMn", "Value": f"{result.phi_Mn_tfm:.2f}", "Unit": "tonf-m", "Status": "TRACEABLE"},
        {"Result": "phiVn", "Value": f"{result.phi_Vn_tf:.2f}", "Unit": "tonf", "Status": "TRACEABLE"},
        {"Result": "U", "Value": f"{result.utilization:.3f}", "Unit": "-", "Status": result.status},
    ]
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    selected_point = _render_interaction_point_selector(geom, concrete, steel, sec_key, result)
    _render_strain_stress_block(geom, concrete, steel, sec_key, result, selected_point)

    shown_steps = result.calculation_steps if audit_mode else [
        step for step in result.calculation_steps
        if step.variable_name in {
            "required_tensile_reinforcement",
            "provided_tensile_reinforcement",
            "design_moment_strength",
            "design_shear_strength",
            "governing_utilization",
        }
    ]

    for step in shown_steps:
        _render_calculation_step(step)

    st.markdown('<div class="section-tag">Equation Dependency Tree</div>', unsafe_allow_html=True)
    st.code(_dependency_tree(), language="text")

    if audit_mode:
        st.markdown('<div class="section-tag">Design Assumptions</div>', unsafe_allow_html=True)
        for assumption in result.assumptions:
            st.markdown(f"- {assumption}")


def _render_strain_stress_block(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    sec_key: str,
    result,
    selected_point: dict | None = None,
    compact: bool = False,
    key_prefix: str = "trace",
) -> None:
    st.markdown('<div class="section-tag">Section / Strain / Stress</div>', unsafe_allow_html=True)
    records = _get_section_records(sec_key)
    pos_moment, _, _, d, dp, comp_lbl, tens_lbl = _section_flexural_inputs(sec_key, geom)
    active_capacity = selected_point["capacity"] if selected_point else result.capacity
    active_layers = selected_point["layers"] if selected_point else _steel_layer_response(
        records,
        geom,
        concrete,
        steel,
        active_capacity.c_na,
        active_capacity.a,
        pos_moment,
    )

    fig = create_flexural_plot(
        geom,
        records,
        active_capacity,
        pos_moment,
        concrete,
        d,
        dp,
        comp_lbl,
        tens_lbl,
        steel,
    )
    fig.update_layout(height=_responsive_trace_height(geom, compact=compact))
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_flexural_{sec_key}")

    c1, c2, c3, c4 = st.columns(4)
    # FIX 1: Use Unicode εt instead of raw 'eps_t' for the strain label
    _trace_metric(c1, "εt", f"{active_capacity.eps_s:.5f}", "", "#f87171")
    _trace_metric(c2, "c", f"{active_capacity.c_na:.1f}", "mm", "#a78bfa")
    _trace_metric(c3, "a", f"{active_capacity.a:.1f}", "mm", "#60a5fa")
    # FIX 2 & 5: lowercase label, ksc unit (Thai engineering standard)
    _trace_metric(c4, "0.85f'c", f"{0.85 * concrete.fc_prime * MPA_TO_KSC:.0f}", "ksc", "#4ade80")

    steel_rows = [
        {
            "Layer": row["Layer"],
            "Bars": row["Bars"],
            "Depth (mm)": row["Depth (mm)"],
            "Strain": row["Strain"],
            "Stress (ksc)": row["Stress (ksc)"],
            "Force (tonf)": row["Force (tonf)"],
            "Yield Status": row["Yield Status"],
        }
        for row in active_layers
    ]
    steel_df = pd.DataFrame(
        steel_rows,
        columns=["Layer", "Bars", "Depth (mm)", "Strain", "Stress (ksc)", "Force (tonf)", "Yield Status"],
    )

    if compact:
        st.markdown('<div class="section-tag">Layer Results</div>', unsafe_allow_html=True)
        st.dataframe(
            steel_df,
            use_container_width=True,
            hide_index=True,
            height=150,
        )
    else:
        table_left, table_right = st.columns(2, gap="large")
        with table_left:
            st.markdown('<div class="section-tag">Strain by Reinforcement Layer</div>', unsafe_allow_html=True)
            st.dataframe(
                steel_df[["Layer", "Bars", "Depth (mm)", "Strain", "Yield Status"]],
                use_container_width=True,
                hide_index=True,
                height=220,
            )
        with table_right:
            st.markdown('<div class="section-tag">Stress Block and Steel Forces</div>', unsafe_allow_html=True)
            st.dataframe(
                steel_df,
                use_container_width=True,
                hide_index=True,
                height=220,
            )

    net_force_tf = (active_capacity.Cc + sum(row["force_n"] for row in active_layers)) / 9806.65
    concrete_rows = [
        {"Item": "Neutral axis", "Symbol": "c", "Value": f"{active_capacity.c_na:.2f}", "Unit": "mm"},
        {"Item": "Compression block depth", "Symbol": "a = beta1 c", "Value": f"{active_capacity.a:.2f}", "Unit": "mm"},
        {"Item": "Concrete compression stress", "Symbol": "0.85f'c", "Value": f"{0.85 * concrete.fc_prime * MPA_TO_KSC:.0f}", "Unit": "ksc"},
        {"Item": "Concrete compression force", "Symbol": "Cc", "Value": f"{active_capacity.Cc / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Compression steel force", "Symbol": "Cs", "Value": f"{active_capacity.Cs / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Tension steel force", "Symbol": "Ts", "Value": f"{active_capacity.T / 9806.65:.2f}", "Unit": "tonf"},
        {"Item": "Net force", "Symbol": "Cc + Cs - Ts", "Value": f"{net_force_tf:.2f}", "Unit": "tonf"},
        {"Item": "Nominal moment", "Symbol": "Mn", "Value": f"{active_capacity.Mn / 9806650.0:.2f}", "Unit": "tonf-m"},
        {"Item": "Strength reduction factor", "Symbol": "phi", "Value": f"{active_capacity.phi:.3f}", "Unit": "-"},
    ]
    st.markdown('<div class="section-tag">Force Summary</div>', unsafe_allow_html=True)
    if compact:
        st.dataframe(pd.DataFrame(concrete_rows), use_container_width=True, hide_index=True, height=235)
    else:
        st.dataframe(pd.DataFrame(concrete_rows), use_container_width=True, hide_index=True)


def _responsive_trace_height(geom: SectionGeometry, compact: bool = False) -> int:
    aspect = geom.h / max(geom.b, 1.0)
    if compact:
        return int(max(360, min(470, 330 + aspect * 70)))
    return int(max(460, min(640, 380 + aspect * 90)))


def _render_interaction_point_selector(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    sec_key: str,
    result,
    compact: bool = False,
    key_prefix: str = "trace",
) -> dict | None:
    records = _get_section_records(sec_key)
    pos_moment, _, _, _, _, _, _ = _section_flexural_inputs(sec_key, geom)
    points = _sample_interaction_points(geom, concrete, steel, records, pos_moment, result.capacity.c_na)
    if not points:
        return None

    selected_key = f"pm_selected_c_{sec_key}"
    if selected_key not in st.session_state:
        st.session_state[selected_key] = result.capacity.c_na

    selected_c = float(st.session_state[selected_key])
    selected_point = min(points, key=lambda point: abs(point["c"] - selected_c))
    fig = _create_interaction_plot(points, selected_point, result, sec_key)
    if compact:
        fig.update_layout(
            height=240,
            margin=dict(l=8, r=8, t=34, b=30),
            title=dict(text="Select P-M point", font=dict(color="#c8d0e8", size=11)),
            legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center", font=dict(color="#c8d0e8", size=8)),
        )

    st.markdown('<div class="section-tag">P-M Interaction Analysis Point</div>', unsafe_allow_html=True)
    event = _plotly_chart_with_optional_selection(fig, key=f"{key_prefix}_pm_interaction_{sec_key}")
    clicked_c = _selected_c_from_plotly_event(event)
    if clicked_c is not None:
        st.session_state[selected_key] = clicked_c
        selected_point = min(points, key=lambda point: abs(point["c"] - clicked_c))

    if compact:
        m1, m2 = st.columns(2)
        _trace_metric(m1, "M", f"{selected_point['M_tfm']:.2f}", "tonf-m", "#60a5fa")
        _trace_metric(m2, "P", f"{selected_point['P_tf']:.2f}", "tonf", "#fbbf24")
        m3, m4 = st.columns(2)
        _trace_metric(m3, "c", f"{selected_point['c']:.1f}", "mm", "#a78bfa")
        _trace_metric(m4, "phi", f"{selected_point['capacity'].phi:.3f}", "", "#4ade80")
    else:
        m1, m2, m3, m4 = st.columns(4)
        _trace_metric(m1, "Selected M", f"{selected_point['M_tfm']:.2f}", "tonf-m", "#60a5fa")
        _trace_metric(m2, "Selected P", f"{selected_point['P_tf']:.2f}", "tonf", "#fbbf24")
        _trace_metric(m3, "Selected c", f"{selected_point['c']:.1f}", "mm", "#a78bfa")
        _trace_metric(m4, "Selected phi", f"{selected_point['capacity'].phi:.3f}", "", "#4ade80")
    return selected_point


def _plotly_chart_with_optional_selection(fig: go.Figure, key: str):
    try:
        return st.plotly_chart(
            fig,
            use_container_width=True,
            key=key,
            on_select="rerun",
            selection_mode="points",
        )
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key)
        return None


def _selected_c_from_plotly_event(event) -> float | None:
    if not event:
        return None
    selection = getattr(event, "selection", None)
    if selection is None and isinstance(event, dict):
        selection = event.get("selection")
    points = getattr(selection, "points", None) if selection is not None else None
    if points is None and isinstance(selection, dict):
        points = selection.get("points")
    if not points:
        return None
    point = points[0]
    customdata = getattr(point, "customdata", None)
    if customdata is None and isinstance(point, dict):
        customdata = point.get("customdata")
    if isinstance(customdata, (list, tuple)):
        customdata = customdata[0] if customdata else None
    try:
        return float(customdata)
    except (TypeError, ValueError):
        return None


def _sample_interaction_points(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    records,
    pos_moment: bool,
    design_c: float,
) -> list[dict]:
    min_c = max(5.0, geom.h * 0.025)
    max_c = max(geom.h * 3.0, design_c * 1.25, min_c * 2.0)
    c_values = [min_c + (max_c - min_c) * i / 79.0 for i in range(80)]
    if design_c > 0:
        c_values.append(design_c)
    unique_c = sorted({round(c, 6) for c in c_values})
    return [_section_response_at_c(geom, concrete, steel, records, c, pos_moment) for c in unique_c]


def _create_interaction_plot(points: list[dict], selected_point: dict, result, sec_key: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[point["M_tfm"] for point in points],
            y=[point["P_tf"] for point in points],
            customdata=[point["c"] for point in points],
            mode="lines+markers",
            line=dict(color="#60a5fa", width=2),
            marker=dict(size=6, color="#60a5fa"),
            name="Interaction curve",
            hovertemplate="M=%{x:.2f} tonf-m<br>P=%{y:.2f} tonf<br>c=%{customdata:.1f} mm<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[selected_point["M_tfm"]],
            y=[selected_point["P_tf"]],
            customdata=[selected_point["c"]],
            mode="markers",
            marker=dict(size=13, color="#fbbf24", line=dict(color="#0f1117", width=2)),
            name="Selected point",
            hovertemplate="Selected<br>M=%{x:.2f} tonf-m<br>P=%{y:.2f} tonf<br>c=%{customdata:.1f} mm<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[result.Mu_tfm],
            y=[0.0],
            mode="markers",
            marker=dict(size=11, color="#f87171", symbol="x"),
            name="Demand",
            hovertemplate=f"{SECTIONS[sec_key]} demand<br>M=%{{x:.2f}} tonf-m<br>P=%{{y:.2f}} tonf<extra></extra>",
        )
    )
    fig.update_layout(
        height=330,
        margin=dict(l=12, r=12, t=36, b=36),
        paper_bgcolor="#0f1117",
        plot_bgcolor="#13151f",
        title=dict(text="Select a point to update the section, strain diagram, stress block, and force table", font=dict(color="#c8d0e8", size=13)),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(color="#c8d0e8", size=10)),
        hoverlabel=dict(bgcolor="#1a1d2e", font=dict(color="#e8eaf0")),
    )
    fig.update_xaxes(title_text="M (tonf-m)", gridcolor="#1e2235", tickfont=dict(color="#c8d0e8"))
    fig.update_yaxes(title_text="P (tonf, compression +)", gridcolor="#1e2235", tickfont=dict(color="#c8d0e8"))
    return fig


def _section_response_at_c(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    records,
    c_na: float,
    pos_moment: bool,
) -> dict:
    a = concrete.beta1 * c_na
    cc_force, cc_depth = _concrete_block_force(geom, concrete, a)
    layer_rows = _steel_layer_response(records, geom, concrete, steel, c_na, a, pos_moment)
    steel_force = sum(row["force_n"] for row in layer_rows)
    p_n = cc_force + steel_force
    m_nmm = cc_force * (geom.h / 2.0 - cc_depth)
    for row in layer_rows:
        m_nmm += row["force_n"] * (geom.h / 2.0 - row["depth"])
    if not pos_moment:
        m_nmm *= -1.0

    d, dp = _effective_depths_from_rows(layer_rows, geom)
    eps_t = min((row["strain"] for row in layer_rows), default=0.0)
    eps_cp = 0.003 * (c_na - dp) / c_na if c_na > 0 else 0.0
    phi = _phi_from_tensile_strain(abs(eps_t))
    tension_force = abs(sum(row["force_n"] for row in layer_rows if row["force_n"] < 0.0))
    comp_steel_force = sum(row["force_n"] for row in layer_rows if row["force_n"] > 0.0)
    capacity = CapacityResult(
        c_na=c_na,
        a=a,
        eps_s=eps_t,
        eps_cp=eps_cp,
        phi=phi,
        T=tension_force,
        Cc=cc_force,
        Cs=comp_steel_force,
        Mn=abs(m_nmm),
        phi_Mn=phi * abs(m_nmm),
    )
    return {
        "c": c_na,
        "P_tf": p_n / 9806.65,
        "M_tfm": m_nmm / 9806650.0,
        "capacity": capacity,
        "layers": layer_rows,
        "d": d,
        "dp": dp,
    }


def _concrete_block_force(geom: SectionGeometry, concrete: ConcreteProps, a: float) -> tuple[float, float]:
    a_clamped = max(0.0, min(a, geom.h))
    force = 0.85 * concrete.fc_prime * geom.b * a_clamped
    return force, a_clamped / 2.0


def _effective_depths_from_rows(layer_rows: list[dict], geom: SectionGeometry) -> tuple[float, float]:
    tension_rows = [row for row in layer_rows if row["force_n"] < 0.0]
    compression_rows = [row for row in layer_rows if row["force_n"] >= 0.0]
    d = max((row["depth"] for row in tension_rows), default=geom.h - geom.cover)
    dp = min((row["depth"] for row in compression_rows), default=geom.cover)
    return d, dp


def _phi_from_tensile_strain(eps_t: float) -> float:
    if eps_t >= 0.005:
        return 0.90
    if eps_t <= 0.002:
        return 0.65
    return 0.65 + (eps_t - 0.002) * (250.0 / 3.0)


def _trace_metric(col, label: str, value: str, unit: str, color: str) -> None:
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
              <div class="metric-label">{label}</div>
              <div class="metric-value" style="color:{color}">{value}<span class="metric-unit">{unit}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _get_section_records(sec_key: str):
    df_all = pd.concat(
        [st.session_state[f"rebar_bot_{sec_key}"], st.session_state[f"rebar_top_{sec_key}"]],
        ignore_index=True,
    )
    return rebar_df_to_records(df_all)


def _steel_layer_response(
    records,
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    c_na: float,
    a: float,
    pos_moment: bool,
) -> list[dict]:
    rows = []
    eps_cu = 0.003
    if c_na <= 0:
        return rows

    grouped = {}
    for record in records:
        depth = (geom.h / 2.0 - record.y) if pos_moment else (geom.h / 2.0 + record.y)
        key = round(depth, 1)
        group = grouped.setdefault(
            key,
            {
                "depth": depth,
                "area": 0.0,
                "bars": 0,
                "descriptions": [],
            },
        )
        area = bar_area(record.dia) * record.count
        group["area"] += area
        group["bars"] += record.count
        group["descriptions"].append(f"{record.count}-{record.bar_size} {record.layer}")

    for idx, group in enumerate((grouped[key] for key in sorted(grouped)), start=1):
        depth = group["depth"]
        strain = eps_cu * (c_na - depth) / c_na
        stress = max(-steel.fy, min(steel.Es_mpa * strain, steel.fy))
        area = group["area"]
        displaced_concrete = 0.85 * concrete.fc_prime if (strain > 0 and depth <= a) else 0.0
        force_n = area * (stress - displaced_concrete if strain > 0 else stress)
        zone = "Compression" if strain >= 0 else "Tension"
        yielded = abs(stress) >= steel.fy * 0.999
        rows.append(
            {
                "Layer": f"L{idx}",
                "Bars": group["bars"],
                "Description": " + ".join(group["descriptions"]),
                "Depth (mm)": f"{depth:.1f}",
                "Strain": f"{strain:.5f}",
                "Stress (MPa)": f"{stress:.1f}",
                "Stress (ksc)": f"{stress * MPA_TO_KSC:.0f}",
                "Force (tonf)": f"{force_n / 9806.65:.2f}",
                "Zone": zone,
                "Yield Status": "Yielded" if yielded else "Elastic",
                "depth": depth,
                "strain": strain,
                "stress_mpa": stress,
                "force_n": force_n,
                "area_mm2": area,
                "records": group["descriptions"],
            }
        )
    return rows


def _render_calculation_step(step: CalculationStep) -> None:
    with st.expander(f"{step.symbol} - {step.variable_name}", expanded=False):
        st.markdown(f"**Variable name:** `{step.variable_name}`")
        st.markdown(f"**Symbol:** `{step.symbol}`")
        st.markdown(f"**Formula:** `{step.formula}`")
        st.markdown(f"**Substitution:** `{step.substitution}`")
        st.markdown(f"**Result:** `{step.result} {step.unit}`")
        st.markdown(f"**Reference:** {step.reference}")
        st.markdown(f"**Explanation:** {step.explanation}")
        if step.dependencies:
            st.markdown("**Depends on:** " + ", ".join(f"`{dep}`" for dep in step.dependencies))


def _render_interactive_notation(design_results: dict) -> None:
    st.markdown('<div class="section-tag">Notation Library</div>', unsafe_allow_html=True)
    notation = _notation_library()
    st.dataframe(pd.DataFrame(notation), use_container_width=True, hide_index=True, height=320)

    variable_names = [row["Symbol"] for row in notation]
    selected = st.selectbox("Variable navigator", variable_names, key="notation_variable_select")
    row = next(item for item in notation if item["Symbol"] == selected)
    sources = _find_formula_sources(design_results, selected)
    related = _find_related_equations(design_results, selected)
    used_in = _find_used_in(design_results, selected)

    st.markdown(
        f"""
        <div class="info-box">
          <b>{selected}</b><br>
          Definition: {row["Description"]}<br>
          Unit: {row["Unit"]}<br>
          Formula sources: {sources}<br>
          Related equations: {related}<br>
          Code references: {row["Reference"]}<br>
          Where used: {used_in}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_reference_panel(design_results: dict) -> None:
    st.markdown('<div class="section-tag">Code Reference System</div>', unsafe_allow_html=True)
    rows = []
    for sec_key, result in design_results.items():
        for check in result.code_checks:
            rows.append(
                {
                    "Section": SECTIONS[sec_key],
                    "Design check": check.name,
                    "Code provision": check.reference,
                    "Description": check.description,
                    "Criteria": check.criterion,
                    "Status": check.status,
                    "Explanation": check.explanation,
                }
            )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=360)

    st.markdown('<div class="section-tag">Reference Notes</div>', unsafe_allow_html=True)
    st.markdown(
        """
        - Flexural stress block and moment strength are traced to ACI 318-19 Chapter 22.
        - Strength reduction factors are traced to ACI 318-19 Chapter 21.
        - The shear panel states the compact model used by the app; minimum shear reinforcement and development length should be reviewed before approval.
        - The report is intended as an engineering review package, not a substitute for professional judgment or authority review.
        """
    )


def _render_report_panel(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    design_results: dict,
    rebar_summaries: dict,
    span_lengths: dict,
) -> None:
    st.markdown('<div class="section-tag">Calculation Report</div>', unsafe_allow_html=True)
    report = _build_report_text(geom, concrete, steel, design_results, rebar_summaries, span_lengths)
    st.download_button(
        "Download calculation package",
        data=report,
        file_name="rc_beam_calculation_package.md",
        mime="text/markdown",
        use_container_width=True,
    )
    with st.expander("Report preview", expanded=True):
        st.markdown(report)


def _unique_steps(design_results: dict) -> list[CalculationStep]:
    unique = {}
    for result in design_results.values():
        for step in result.calculation_steps:
            unique.setdefault(step.variable_name, step)
    return list(unique.values())


def _step_by_name(steps: list[CalculationStep], name: str) -> CalculationStep:
    return next(step for step in steps if step.variable_name == name)


def _formula_applicability(variable_name: str) -> str:
    if "shear" in variable_name or variable_name in {"concrete_shear_strength", "stirrup_shear_strength"}:
        return "Rectangular, nonprestressed beam shear check with two-leg stirrups."
    if "moment" in variable_name or variable_name in {"stress_block_factor", "neutral_axis_depth", "stress_block_depth"}:
        return "Rectangular reinforced concrete flexural strength check."
    if "utilization" in variable_name:
        return "Design check demand-to-capacity comparison."
    return "Active beam section and reinforcement schedule."


def _formula_assumptions(variable_name: str) -> str:
    if "shear" in variable_name:
        return "Normalweight concrete, lambda = 1.0; stirrup legs = 2."
    if variable_name == "required_tensile_reinforcement":
        return "Solved iteratively using the same flexural capacity model."
    if variable_name == "provided_tensile_reinforcement":
        return "Bar areas are taken from the current reinforcement table."
    return "ACI stress-block behavior, eps_cu = 0.003, Es = 200000 MPa."


def _notation_library() -> list[dict]:
    return [
        {"Symbol": "fc_prime", "Description": "Specified concrete compressive strength", "Unit": "MPa", "Reference": "ACI 318-19 Sec. 19.2"},
        {"Symbol": "fy", "Description": "Yield strength of longitudinal reinforcement", "Unit": "MPa", "Reference": "ACI 318-19 Sec. 20.2"},
        {"Symbol": "fyt", "Description": "Yield strength of shear reinforcement", "Unit": "MPa", "Reference": "ACI 318-19 Sec. 20.2"},
        {"Symbol": "b", "Description": "Beam width", "Unit": "mm", "Reference": "Project geometry input"},
        {"Symbol": "h", "Description": "Overall beam depth", "Unit": "mm", "Reference": "Project geometry input"},
        {"Symbol": "d", "Description": "Effective depth to tension reinforcement", "Unit": "mm", "Reference": "ACI 318-19 notation"},
        {"Symbol": "dp", "Description": "Depth to compression reinforcement", "Unit": "mm", "Reference": "ACI 318-19 notation"},
        {"Symbol": "As", "Description": "Area of tensile reinforcement", "Unit": "mm2", "Reference": "Bar schedule"},
        {"Symbol": "Asp", "Description": "Area of compression reinforcement", "Unit": "mm2", "Reference": "Bar schedule"},
        {"Symbol": "Mu", "Description": "Factored moment demand", "Unit": "tonf-m", "Reference": "User design load input"},
        {"Symbol": "Vu", "Description": "Factored shear demand", "Unit": "tonf", "Reference": "User design load input"},
        {"Symbol": "beta1", "Description": "Equivalent stress-block factor", "Unit": "-", "Reference": "ACI 318-19 Sec. 22.2.2.4"},
        {"Symbol": "c", "Description": "Neutral axis depth from compression face", "Unit": "mm", "Reference": "ACI 318-19 Sec. 22.3"},
        {"Symbol": "a", "Description": "Equivalent rectangular stress-block depth", "Unit": "mm", "Reference": "ACI 318-19 Sec. 22.2.2.4"},
        {"Symbol": "T", "Description": "Tension steel force", "Unit": "N", "Reference": "ACI 318-19 Sec. 22.3"},
        {"Symbol": "Cc", "Description": "Concrete compression force", "Unit": "N", "Reference": "ACI 318-19 Sec. 22.2"},
        {"Symbol": "Cs", "Description": "Compression steel force", "Unit": "N", "Reference": "ACI 318-19 Sec. 22.3"},
        {"Symbol": "Mn", "Description": "Nominal moment strength", "Unit": "tonf-m", "Reference": "ACI 318-19 Sec. 22.3"},
        {"Symbol": "phi", "Description": "Strength reduction factor", "Unit": "-", "Reference": "ACI 318-19 Table 21.2.2"},
        {"Symbol": "phiMn", "Description": "Design moment strength", "Unit": "tonf-m", "Reference": "ACI 318-19 Sec. 21.2"},
        {"Symbol": "Vc", "Description": "Concrete contribution to shear strength", "Unit": "tonf", "Reference": "ACI 318-19 Table 22.5.5.1"},
        {"Symbol": "Vs", "Description": "Shear reinforcement contribution", "Unit": "tonf", "Reference": "ACI 318-19 Sec. 22.5.10.5"},
        {"Symbol": "phiVn", "Description": "Design shear strength", "Unit": "tonf", "Reference": "ACI 318-19 Sec. 21.2 and Sec. 22.5"},
        {"Symbol": "U", "Description": "Governing utilization ratio", "Unit": "-", "Reference": "ACI 318-19 Sec. 9.5"},
    ]


def _find_formula_sources(design_results: dict, symbol: str) -> str:
    matches = []
    for result in design_results.values():
        for step in result.calculation_steps:
            if step.symbol == symbol or symbol in step.dependencies:
                matches.append(step.symbol)
    return ", ".join(sorted(set(matches))) if matches else "No direct formula source in current result set."


def _find_related_equations(design_results: dict, symbol: str) -> str:
    matches = []
    for result in design_results.values():
        for step in result.calculation_steps:
            if step.symbol == symbol or symbol in step.dependencies:
                matches.append(step.formula)
    return " | ".join(sorted(set(matches))) if matches else "No related equation found."


def _find_used_in(design_results: dict, symbol: str) -> str:
    used = []
    for sec_key, result in design_results.items():
        for step in result.calculation_steps:
            if step.symbol == symbol or symbol in step.dependencies:
                used.append(f"{SECTIONS[sec_key]}: {step.symbol}")
    return ", ".join(sorted(set(used))) if used else "Not used by current displayed calculations."


def _dependency_tree() -> str:
    return """phiMn
|-- Mn
|   |-- Cc
|   |   |-- fc_prime
|   |   |-- b
|   |   `-- a
|   |       |-- beta1
|   |       `-- c
|   |           |-- As
|   |           |-- Asp
|   |           |-- fy
|   |           |-- fc_prime
|   |           |-- d
|   |           `-- dp
|   |-- Cs
|   |   |-- Asp
|   |   |-- fsc
|   |   `-- fc_prime
|   |-- d
|   |-- a
|   `-- dp
`-- phi
    `-- eps_t

phiVn
|-- phi_v
`-- Vn
    |-- Vc
    |   |-- fc_prime
    |   |-- b
    |   `-- d
    `-- Vs
        |-- Av
        |-- fyt
        |-- d
        `-- s"""


def _build_report_text(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    design_results: dict,
    rebar_summaries: dict,
    span_lengths: dict,
) -> str:
    lines = [
        "# RC Beam Calculation Package",
        "",
        "## 1. Input Summary",
        f"- Code basis: ACI 318-19 with project detailing inputs.",
        f"- Units: ksc, MPa, mm, tonf, tonf-m; internal strength calculations use N and mm.",
        f"- Section: rectangular beam, b = {geom.b:.0f} mm, h = {geom.h:.0f} mm.",
        f"- Cover = {geom.cover:.0f} mm; stirrup diameter = {geom.stirrup_dia:.0f} mm.",
        "",
        "## 2. Design Assumptions",
    ]
    first_result = next(iter(design_results.values()))
    lines.extend(f"- {item}" for item in first_result.assumptions)
    lines.extend(
        [
            "",
            "## 3. Material Properties",
            f"- Concrete f'c = {concrete.fc_ksc:.0f} ksc = {concrete.fc_prime:.2f} MPa.",
            f"- Longitudinal steel fy = {steel.fy_ksc:.0f} ksc = {steel.fy:.2f} MPa.",
            f"- Stirrup steel fyt = {steel.fyt_ksc:.0f} ksc = {steel.fyt:.2f} MPa.",
            f"- Es = {steel.Es_mpa:.0f} MPa.",
            f"- beta1 = {concrete.beta1:.3f}.",
            "",
            "## 4. Design Loads",
        ]
    )
    for sec_key, result in design_results.items():
        lines.append(
            f"- {SECTIONS[sec_key]}: Mu = {result.Mu_tfm:.2f} tonf-m, Vu = {result.Vu_tf:.2f} tonf, L = {span_lengths[sec_key]:.0f} mm."
        )

    lines.extend(["", "## 5. Flexural Design"])
    for sec_key, result in design_results.items():
        lines.append(
            f"- {SECTIONS[sec_key]}: As_required = {result.required_As:.2f} mm2, "
            f"As_provided = {result.provided_As:.2f} mm2, phiMn = {result.phi_Mn_tfm:.2f} tonf-m, "
            f"U_flex = {result.flexural_utilization:.3f}."
        )

    lines.extend(["", "## 6. Shear Design"])
    for sec_key, result in design_results.items():
        summary = rebar_summaries[sec_key]
        lines.append(
            f"- {SECTIONS[sec_key]}: stirrups = 2 legs, dia {summary['StirrupDia']:.0f} @ "
            f"{summary['StirrupSpacing']:.0f} mm, phiVn = {result.phi_Vn_tf:.2f} tonf, "
            f"U_shear = {result.shear_utilization:.3f}."
        )

    lines.extend(["", "## 7. Detailed Calculations"])
    for sec_key, result in design_results.items():
        lines.append(f"### {SECTIONS[sec_key]}")
        for step in result.calculation_steps:
            lines.extend(
                [
                    f"- {step.variable_name} ({step.symbol})",
                    f"  - Formula: {step.formula}",
                    f"  - Substitution: {step.substitution}",
                    f"  - Result: {step.result} {step.unit}",
                    f"  - Reference: {step.reference}",
                    f"  - Explanation: {step.explanation}",
                ]
            )

    lines.extend(["", "## 8. Formula References"])
    for step in _unique_steps(design_results):
        lines.append(f"- {step.symbol}: {step.formula}; reference: {step.reference}.")

    lines.extend(["", "## 9. Code References"])
    for sec_key, result in design_results.items():
        for check in result.code_checks:
            lines.append(f"- {SECTIONS[sec_key]} - {check.name}: {check.reference}; {check.status}; {check.criterion}.")

    lines.extend(["", "## 10. Notation Table"])
    for row in _notation_library():
        lines.append(f"- {row['Symbol']}: {row['Description']} [{row['Unit']}].")

    lines.extend(["", "## 11. Beam Detailing Drawing"])
    for sec_key, summary in rebar_summaries.items():
        lines.append(
            f"- {SECTIONS[sec_key]}: top bars {summary['Top']}; bottom bars {summary['Bottom']}; "
            f"stirrups dia {summary['StirrupDia']:.0f} @ {summary['StirrupSpacing']:.0f} mm."
        )

    lines.extend(["", "## Overall Status"])
    for sec_key, result in design_results.items():
        lines.append(f"- {SECTIONS[sec_key]}: {result.status}, governing U = {result.utilization:.3f}.")
    return "\n".join(lines)
