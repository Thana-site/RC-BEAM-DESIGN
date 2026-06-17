"""
RC Section Visualizer — Notation UI Component
"""
import streamlit as st
import pandas as pd
import numpy as np
from constants import SECTIONS, STANDARD_BARS
from config import NOTATION_STYLE, VARIABLE_REF_STYLE
from models.section import SectionGeometry
from models.materials import ConcreteProps, SteelProps
from models.rebar import rebar_df_to_records
from utils.math_helpers import bar_area
from analysis.properties import get_steel_area

def render_notation_tab(geom: SectionGeometry, concrete: ConcreteProps, steel: SteelProps):
    """
    Render notations, parameter summary table, and variable reference table.
    """
    show_mpa = st.session_state.get("show_mpa", False)
    nt1, nt2, nt3 = st.tabs(["📖  Notation & Symbols", "📋  Parameter Summary", "💻  Variable Reference"])

    # ── Tab 1: Notation & Symbols ─────────────────────────────────────────────
    with nt1:
        st.markdown(NOTATION_STYLE, unsafe_allow_html=True)
        st.markdown('<div class="section-tag">Notation &amp; Symbols</div>', unsafe_allow_html=True)
        st.markdown("""
<div class="nt">
  <div class="nt-head">Section Geometry</div>
  <div class="nt-sym">b, B</div><div class="nt-def">Width of rectangular section or flange width of T-beam (mm)</div>
  <div class="nt-sym">h, H</div><div class="nt-def">Overall depth of section (mm)</div>
  <div class="nt-sym">b<sub>w</sub></div><div class="nt-def">Web width of T-beam (mm)</div>
  <div class="nt-sym">b<sub>f</sub></div><div class="nt-def">Flange width of T-beam (mm)</div>
  <div class="nt-sym">t<sub>f</sub></div><div class="nt-def">Flange thickness of T-beam (mm)</div>
  <div class="nt-sym">D</div><div class="nt-def">Diameter of circular section (mm)</div>
  <div class="nt-sym">d</div><div class="nt-def">Effective depth to tension steel centroid (mm)</div>
  <div class="nt-sym">cover</div><div class="nt-def">Clear concrete cover to stirrup face (mm)</div>

  <div class="nt-head">Materials &amp; Properties</div>
  <div class="nt-sym">f'c</div><div class="nt-def">Specified compressive strength of concrete (ksc)</div>
  <div class="nt-sym">fy</div><div class="nt-def">Specified yield strength of reinforcement (ksc) — SD30=3000 · SD40=4000 · SD50=5000</div>
  <div class="nt-sym">Ec</div><div class="nt-def">Modulus of elasticity of concrete = 4700√f'c (MPa) per ACI 318 (displayed in ksc)</div>
  <div class="nt-sym">Es</div><div class="nt-def">Modulus of elasticity of steel = 200 000 MPa (constant)</div>
  <div class="nt-sym">n</div><div class="nt-def">Modular ratio = Es / Ec (dimensionless)</div>

  <div class="nt-head">Reinforcement</div>
  <div class="nt-sym">Ø</div><div class="nt-def">Nominal bar diameter (mm)</div>
  <div class="nt-sym">As</div><div class="nt-def">Total steel area (mm²)</div>
  <div class="nt-sym">A<sub>s,bot</sub></div><div class="nt-def">Area of bottom (tension) reinforcement (mm²)</div>
  <div class="nt-sym">A<sub>s,top</sub></div><div class="nt-def">Area of top (compression) reinforcement (mm²)</div>
  <div class="nt-sym">ρ</div><div class="nt-def">Steel ratio = As / Ag × 100 (%)</div>

  <div class="nt-head">Section Properties</div>
  <div class="nt-sym">Ag</div><div class="nt-def">Gross cross-sectional area of concrete (cm²)</div>
  <div class="nt-sym">Ig</div><div class="nt-def">Gross moment of inertia about centroidal axis (mm⁴) — rectangular: bh³/12</div>
  <div class="nt-sym">Icr</div><div class="nt-def">Cracked transformed moment of inertia — simplified ACI rectangular method (mm⁴)</div>
  <div class="nt-sym">kd</div><div class="nt-def">Depth to neutral axis under service loads (cracked elastic, mm)</div>
  <div class="nt-sym">a</div><div class="nt-def">Depth of equivalent rectangular stress block = As·fy / (0.85·f'c·b) (mm)</div>
  <div class="nt-sym">β₁</div><div class="nt-def">Stress-block factor = 0.85 for f'c ≤ 28 MPa; reduced 0.05 per 7 MPa above (ACI 318 §22.2.2.4)</div>
  <div class="nt-sym">c</div><div class="nt-def">Neutral axis depth = a / β₁ (mm)</div>

  <div class="nt-head">Unit System — MKS</div>
  <div class="nt-sym">kgf</div><div class="nt-def">Kilogram-force — unit of force</div>
  <div class="nt-sym">ksc</div><div class="nt-def">kgf/cm² — unit of stress &nbsp;(1 ksc = 0.098 067 MPa)</div>
  <div class="nt-sym">mm</div><div class="nt-def">Millimetre — unit of length for dimensions and bar diameters</div>
  <div class="nt-sym">cm²</div><div class="nt-def">Square centimetre — used for gross area display</div>
  <div class="nt-sym">mm²</div><div class="nt-def">Square millimetre — used for steel area</div>
  <div class="nt-sym">mm⁴</div><div class="nt-def">Fourth power of millimetre — used for moment of inertia</div>

  <div class="nt-head">Section Positions</div>
  <div class="nt-sym">Int.</div><div class="nt-def">Interior section — at interior support; governs negative moment (top steel)</div>
  <div class="nt-sym">Mid.</div><div class="nt-def">Mid-span section — at midspan; governs positive moment (bottom steel)</div>
  <div class="nt-sym">Ext.</div><div class="nt-def">Exterior section — at exterior support; negative moment, usually less than interior</div>
</div>
        """, unsafe_allow_html=True)

    # ── Tab 2: Parameter Summary ──────────────────────────────────────────────
    with nt2:
        st.markdown('<div class="section-tag">Parameter Summary</div>', unsafe_allow_html=True)

        rows = []
        
        # Geometry description
        if geom.section_type == "Rectangular":
            sec_desc = "Rectangular"
        elif geom.section_type == "Circular":
            sec_desc = "Circular"
        else:
            sec_desc = "T-Beam"

        rows.append(("Section Type", "Input", sec_desc, "—"))
        rows.append(("b", "Input", f"{geom.b:.0f}", "mm"))
        rows.append(("h", "Input", f"{geom.h:.0f}", "mm"))
        if geom.section_type == "Circular":
            rows.append(("D", "Input", f"{geom.D:.0f}", "mm"))
        if geom.section_type == "T-Beam":
            rows.append(("b_f", "Input", f"{geom.b_f:.0f}", "mm"))
            rows.append(("t_f", "Input", f"{geom.t_f:.0f}", "mm"))
            rows.append(("b_w", "Input", f"{geom.b_w:.0f}", "mm"))
            
        rows.append(("Cover", "Input", f"{geom.cover:.0f}", "mm"))
        rows.append(("Stirrup dia.", "Input", f"{geom.stirrup_dia:.0f}", "mm"))

        # Materials
        rows.append(("f'c", "Input", f"{concrete.fc_ksc:.0f}", "ksc"))
        if show_mpa:
            rows.append(("f'c", "Derived", f"{concrete.fc_prime:.2f}", "MPa"))
        rows.append(("fy  (main steel)", "Input", f"{steel.fy_ksc:.0f}", "ksc"))
        if show_mpa:
            rows.append(("fy  (main steel)", "Derived", f"{steel.fy:.2f}", "MPa"))
        rows.append(("fyt (stirrup)", "Input", f"{steel.fyt_ksc:.0f}", "ksc"))
        if show_mpa:
            rows.append(("fyt (stirrup)", "Derived", f"{steel.fyt:.2f}", "MPa"))
        rows.append(("Es", "Constant", f"{steel.Es_ksc:.0f}", "ksc"))
        if show_mpa:
            rows.append(("Es", "Constant", f"{steel.Es_mpa:.0f}", "MPa"))
            rows.append(("Ec", "Derived", f"{concrete.Ec_mpa:.0f}", "MPa"))
        rows.append(("Ec", "Derived", f"{concrete.Ec_ksc:.0f}", "ksc"))
        rows.append(("n = Es/Ec", "Derived", f"{(steel.Es_mpa/concrete.Ec_mpa):.2f}", "—"))
        rows.append(("β₁", "Derived", f"{concrete.beta1:.3f}", "—"))

        # Gross section
        rows.append(("Ag", "Computed", f"{(geom.Ag/1e4):.2f}", "cm²"))
        rows.append(("Ig", "Computed", f"{(geom.Ig/1e8):.4f}", "×10⁸ mm⁴"))

        # Per-section rebar
        for sec_key, sec_label in SECTIONS.items():
            df_b = st.session_state[f"rebar_bot_{sec_key}"]
            df_t = st.session_state[f"rebar_top_{sec_key}"]
            df_all = pd.concat([df_b, df_t], ignore_index=True)
            records = rebar_df_to_records(df_all)
            
            bot = get_steel_area(records, "Bottom")
            top = get_steel_area(records, "Top")
            sid = get_steel_area(records, "Side")
            tot = bot + top + sid
            rho = tot / geom.Ag * 100.0 if geom.Ag > 0 else 0.0

            rows.append((f"As,bot  [{sec_label}]", "Section", f"{bot:.1f}", "mm²"))
            rows.append((f"As,top  [{sec_label}]", "Section", f"{top:.1f}", "mm²"))
            rows.append((f"As,side [{sec_label}]", "Section", f"{sid:.1f}", "mm²"))
            rows.append((f"As,total [{sec_label}]", "Section", f"{tot:.1f}", "mm²"))
            rows.append((f"ρ        [{sec_label}]", "Section", f"{rho:.3f}", "%"))

        # Build DataFrame
        param_df = pd.DataFrame(rows, columns=["Parameter", "Type", "Value", "Unit"])

        def _row_color(row):
            c = {
                "Input":    "background-color:#1a2a1a; color:#4ade80",
                "Derived":  "background-color:#1a1d2e; color:#60a5fa",
                "Constant": "background-color:#1e1a10; color:#f59e0b",
                "Computed": "background-color:#1e1d2e; color:#a78bfa",
                "Section":  "background-color:#1a1a2e; color:#f472b6",
            }.get(row["Type"], "")
            return [c] * len(row)

        styled = (param_df.style
                  .apply(_row_color, axis=1)
                  .set_properties(**{"font-size": "0.82rem", "font-family": "JetBrains Mono, monospace"})
                  .set_table_styles([
                      {"selector": "thead th",
                       "props": "background:#1a1d2e; color:#7c8db5; font-size:0.72rem; "
                                "text-transform:uppercase; letter-spacing:0.8px;"},
                  ]))

        st.dataframe(styled, use_container_width=True, height=680)

        # Legend
        st.markdown("""
<div style="display:flex;gap:14px;margin-top:6px;flex-wrap:wrap;font-size:0.75rem">
  <span style="color:#4ade80">■ Input</span>&nbsp;— sidebar value entered by user&emsp;
  <span style="color:#60a5fa">■ Derived</span>&nbsp;— converted / calculated from input&emsp;
  <span style="color:#f59e0b">■ Constant</span>&nbsp;— fixed engineering constant&emsp;
  <span style="color:#a78bfa">■ Computed</span>&nbsp;— gross section geometry&emsp;
  <span style="color:#f472b6">■ Section</span>&nbsp;— per-section rebar result
</div>""", unsafe_allow_html=True)

    # ── Tab 3: Variable Reference ─────────────────────────────────────────────
    with nt3:
        st.markdown(VARIABLE_REF_STYLE, unsafe_allow_html=True)
        st.markdown('<div class="section-tag">Variable Reference — how to call any parameter in Tab 2 / Tab 3</div>', unsafe_allow_html=True)

        _live_D = geom.D if geom.section_type == "Circular" else "—"
        _live_bf = geom.b_f if geom.section_type == "T-Beam" else "—"
        _live_tf = geom.t_f if geom.section_type == "T-Beam" else "—"
        _live_bw = geom.b_w if geom.section_type == "T-Beam" else "—"

        def _vrow(name, current, desc, unit, color="#60a5fa"):
            return (f"<tr><td class='vname' style='color:{color}'>{name}</td>"
                    f"<td class='vval'>{current}</td>"
                    f"<td class='vdesc'>{desc}</td>"
                    f"<td class='vunit'>{unit}</td></tr>")

        def _vsec(label):
            return f"<tr><td colspan='4' class='vr-head'>{label}</td></tr>"

        rows_html = (
            "<table class='vr'>"
            "<thead><tr><th>Variable name</th><th>Current value</th>"
            "<th>Description</th><th>Unit</th></tr></thead><tbody>"
            + _vsec("Section Geometry — global scalars")
            + _vrow("b", f"{geom.b:.0f}", "Width of section (or flange width for T-Beam)", "mm")
            + _vrow("h", f"{geom.h:.0f}", "Overall depth of section", "mm")
            + _vrow("D", f"{_live_D}", "Diameter — Circular section only", "mm")
            + _vrow("b_f", f"{_live_bf}", "Flange width — T-Beam only", "mm")
            + _vrow("t_f", f"{_live_tf}", "Flange thickness — T-Beam only", "mm")
            + _vrow("b_w", f"{_live_bw}", "Web width — T-Beam only", "mm")
            + _vrow("cover", f"{geom.cover:.0f}", "Clear cover to stirrup face", "mm")
            + _vrow("stirrup_dia", f"{geom.stirrup_dia:.0f}", "Stirrup bar diameter", "mm")
            + _vrow("section_type", f"'{geom.section_type}'", "'Rectangular' / 'Circular' / 'T-Beam'", "str")

            + _vsec("Material Strengths — global scalars")
            + _vrow("fc_ksc", f"{concrete.fc_ksc:.0f}", "Concrete f'c input", "ksc", "#4ade80")
            + (_vrow("fc_prime", f"{concrete.fc_prime:.2f}", "Concrete f'c converted", "MPa", "#4ade80") if show_mpa else "")
            + _vrow("fy_ksc", f"{steel.fy_ksc:.0f}", "Main steel fy input", "ksc", "#f87171")
            + (_vrow("fy", f"{steel.fy:.2f}", "Main steel fy converted", "MPa", "#f87171") if show_mpa else "")
            + _vrow("fyt_ksc", f"{steel.fyt_ksc:.0f}", "Stirrup fyt input", "ksc", "#fb923c")
            + (_vrow("fyt", f"{steel.fyt:.2f}", "Stirrup fyt converted", "MPa", "#fb923c") if show_mpa else "")

            + _vsec("Per-Section Steel Areas — pre-computed, ready to use")
            + _vrow("st.session_state['d_bot_Int']",
                    f"{st.session_state['d_bot_Int']:.1f}" if st.session_state['d_bot_Int'] else "—",
                    "Effective depth to bottom steel centroid — Interior  (from top)", "mm", "#fbbf24")
            + _vrow("st.session_state['d_top_Int']",
                    f"{st.session_state['d_top_Int']:.1f}" if st.session_state['d_top_Int'] else "—",
                    "Depth to top steel centroid — Interior  (from top)", "mm", "#fbbf24")
            + _vrow("st.session_state['d_bot_Mid']",
                    f"{st.session_state['d_bot_Mid']:.1f}" if st.session_state['d_bot_Mid'] else "—",
                    "Effective depth to bottom steel centroid — Mid-Span  (from top)", "mm", "#fbbf24")
            + _vrow("st.session_state['d_top_Mid']",
                    f"{st.session_state['d_top_Mid']:.1f}" if st.session_state['d_top_Mid'] else "—",
                    "Depth to top steel centroid — Mid-Span  (from top)", "mm", "#fbbf24")
            + _vrow("st.session_state['d_bot_Ext']",
                    f"{st.session_state['d_bot_Ext']:.1f}" if st.session_state['d_bot_Ext'] else "—",
                    "Effective depth to bottom steel centroid — Exterior  (from top)", "mm", "#fbbf24")
            + _vrow("st.session_state['d_top_Ext']",
                    f"{st.session_state['d_top_Ext']:.1f}" if st.session_state['d_top_Ext'] else "—",
                    "Depth to top steel centroid — Exterior  (from top)", "mm", "#fbbf24")
            + _vrow("st.session_state['As_bot_Int']", f"{st.session_state['As_bot_Int']:.1f}", "As bottom — Interior section", "mm²", "#f87171")
            + _vrow("st.session_state['As_top_Int']", f"{st.session_state['As_top_Int']:.1f}", "As top    — Interior section", "mm²", "#34d399")
            + _vrow("st.session_state['As_side_Int']", f"{st.session_state['As_side_Int']:.1f}", "As side   — Interior section", "mm²", "#60a5fa")
            + _vrow("st.session_state['As_total_Int']", f"{st.session_state['As_total_Int']:.1f}", "As total  — Interior section", "mm²", "#e8eaf0")
            + _vrow("st.session_state['rho_Int']", f"{st.session_state['rho_Int']:.3f}", "ρ (%)     — Interior section", "%", "#e8eaf0")
            + _vrow("st.session_state['As_bot_Mid']", f"{st.session_state['As_bot_Mid']:.1f}", "As bottom — Mid-Span section", "mm²", "#f87171")
            + _vrow("st.session_state['As_top_Mid']", f"{st.session_state['As_top_Mid']:.1f}", "As top    — Mid-Span section", "mm²", "#34d399")
            + _vrow("st.session_state['As_side_Mid']", f"{st.session_state['As_side_Mid']:.1f}", "As side   — Mid-Span section", "mm²", "#60a5fa")
            + _vrow("st.session_state['As_total_Mid']", f"{st.session_state['As_total_Mid']:.1f}", "As total  — Mid-Span section", "mm²", "#e8eaf0")
            + _vrow("st.session_state['rho_Mid']", f"{st.session_state['rho_Mid']:.3f}", "ρ (%)     — Mid-Span section", "%", "#e8eaf0")
            + _vrow("st.session_state['As_bot_Ext']", f"{st.session_state['As_bot_Ext']:.1f}", "As bottom — Exterior section", "mm²", "#f87171")
            + _vrow("st.session_state['As_top_Ext']", f"{st.session_state['As_top_Ext']:.1f}", "As top    — Exterior section", "mm²", "#34d399")
            + _vrow("st.session_state['As_side_Ext']", f"{st.session_state['As_side_Ext']:.1f}", "As side   — Exterior section", "mm²", "#60a5fa")
            + _vrow("st.session_state['As_total_Ext']", f"{st.session_state['As_total_Ext']:.1f}", "As total  — Exterior section", "mm²", "#e8eaf0")
            + _vrow("st.session_state['rho_Ext']", f"{st.session_state['rho_Ext']:.3f}", "ρ (%)     — Exterior section", "%", "#e8eaf0")

            + _vsec("Rebar DataFrames — raw tables (columns: Layer, X, Y, Dia, Count, Bar Size)")
            + _vrow("st.session_state['rebar_bot_Int']", "DataFrame", "Bottom/Side rows for Interior section", "pd.DataFrame")
            + _vrow("st.session_state['rebar_top_Int']", "DataFrame", "Top rows for Interior section", "pd.DataFrame")
            + _vrow("st.session_state['rebar_bot_Mid']", "DataFrame", "Bottom/Side rows for Mid-Span section", "pd.DataFrame")
            + _vrow("st.session_state['rebar_top_Mid']", "DataFrame", "Top rows for Mid-Span section", "pd.DataFrame")
            + _vrow("st.session_state['rebar_bot_Ext']", "DataFrame", "Bottom/Side rows for Exterior section", "pd.DataFrame")
            + _vrow("st.session_state['rebar_top_Ext']", "DataFrame", "Top rows for Exterior section", "pd.DataFrame")

            + _vsec("Helper Function")
            + _vrow("bar_area(dia)", "π·dia²/4", "Returns cross-section area of one bar in mm²", "mm²", "#a78bfa")

            + _vsec("Derived Constants — recompute in Tab 2/3 as needed")
            + _vrow("Ec_ksc", f"{concrete.Ec_ksc:.0f}", "Modulus of elasticity of concrete", "ksc")
            + (_vrow("Ec = 4700*np.sqrt(fc_prime)", f"{concrete.Ec_mpa:.0f}", "Modulus of elasticity of concrete (ACI 318)", "MPa") if show_mpa else "")
            + _vrow("n  = Es/Ec", f"{(steel.Es_mpa/concrete.Ec_mpa):.2f}", "Modular ratio Es/Ec", "—")
            + _vrow("beta1", f"{concrete.beta1:.3f}", "ACI 318 stress-block factor β₁", "—")
            + "</tbody></table>"
        )
        st.markdown(rows_html, unsafe_allow_html=True)

        st.markdown("""
<div class='info-box' style='margin-top:4px'>
<b>Pattern to get As for any section:</b><br>
<code style='color:#a78bfa;font-size:0.82rem'>
df = pd.concat([st.session_state["rebar_bot_Int"], st.session_state["rebar_top_Int"]], ignore_index=True)<br>
As_bot = sum(bar_area(r["Dia (mm)"])*r["Count"] for _,r in df.iterrows() if r.get("Layer","")=="Bottom")<br>
As_top = sum(bar_area(r["Dia (mm)"])*r["Count"] for _,r in df.iterrows() if r.get("Layer","")=="Top")
</code>
</div>""", unsafe_allow_html=True)
