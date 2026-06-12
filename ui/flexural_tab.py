"""
RC Section Visualizer — Tab 2 Flexural Analysis UI Component
"""
import streamlit as st
import pandas as pd
from constants import SECTIONS, STANDARD_BARS, MPA_TO_KSC
from config import ANALYSIS_METHOD_STYLE
from models.section import SectionGeometry
from models.materials import ConcreteProps, SteelProps
from models.rebar import rebar_df_to_records
from utils.math_helpers import bar_area
from template_io.templates import save_template, load_template, delete_template
from analysis.capacity import calculate_flexural_capacity, CapacityResult
from plotting.flexural_plot import create_flexural_plot, build_layer_results_table

def render_flexural_tab(sec_key: str, pos_moment: bool, geom: SectionGeometry, concrete: ConcreteProps, steel: SteelProps):
    """
    Render flexural capacity analysis (diagrams, editor, capacity stats) for one section.
    """
    # 1. Resolve steel areas & effective depths based on moment sign
    As, Asp, d, dp, comp_lbl, tens_lbl, m_tag = _get_flexural_inputs(sec_key, pos_moment, geom)
    
    # 2. Run flexural capacity calculations
    capacity = calculate_flexural_capacity(geom, As, Asp, d, dp, concrete, steel)
    
    # 3. Capacity status badge
    _render_capacity_status(capacity, m_tag, SECTIONS[sec_key])
    
    # 4. Render the 3-panel subplot diagram
    df_bot = st.session_state[f"rebar_bot_{sec_key}"]
    df_top = st.session_state[f"rebar_top_{sec_key}"]
    df_all = pd.concat([df_bot, df_top], ignore_index=True)
    records = rebar_df_to_records(df_all)
    
    fig = create_flexural_plot(geom, records, capacity, pos_moment, concrete, d, dp, comp_lbl, tens_lbl, steel)
    st.plotly_chart(fig, use_container_width=True, key=f"flex_{sec_key}")

    layer_df = build_layer_results_table(geom, records, capacity, pos_moment, concrete, steel)
    if not layer_df.empty:
        st.markdown(
            '<div class="section-tag" style="margin-top:8px">Layer Results</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(layer_df, use_container_width=True, hide_index=True)

    # 5. Render inline editor & templates side-by-side
    st.divider()
    st.markdown(f'<div class="section-tag" style="margin-top:4px">Rebar Editor — {SECTIONS[sec_key]}</div>', unsafe_allow_html=True)
    
    ed_col, tmpl_col = st.columns([3, 1])
    with ed_col:
        _render_inline_editors(sec_key, geom)
    with tmpl_col:
        _render_inline_templates(sec_key)
        
    # 6. Render calculations explanation expander
    _render_analysis_method_expander(capacity, concrete, steel)
    
    # 7. Render capacity stats grids
    st.divider()
    st.markdown(f'<div class="section-tag">{m_tag} — {SECTIONS[sec_key]}</div>', unsafe_allow_html=True)
    _render_capacity_data_tables(geom, concrete, steel, As, Asp, d, dp, capacity)

def _render_capacity_status(capacity: CapacityResult, m_tag: str, sec_label: str):
    """Render the capacity status badge and φ factor indicator."""
    N_TO_TONF = 1.0 / 9806.65
    NMM_TO_TONFM = 1.0 / 9806650.0
    phiMn_tfm = capacity.phi_Mn * NMM_TO_TONFM
    Mn_tfm = capacity.Mn * NMM_TO_TONFM
    
    # Determine ductility status
    if capacity.eps_s >= 0.005:
        status_class = "tension-controlled"
        status_label = "Tension-Controlled"
        status_icon = "✅"
    elif capacity.eps_s <= 0.002:
        status_class = "compression-controlled"
        status_label = "Compression-Controlled"
        status_icon = "⚠️"
    else:
        status_class = "transition"
        status_label = "Transition Zone"
        status_icon = "🔶"
    
    # Badge + phi bar in two columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if capacity.phi_Mn > 0:
            st.markdown(f"""
            <div class="capacity-badge {status_class}">
                <span style="font-size:1.1rem">{status_icon}</span>
                <div>
                    <div style="font-size:0.62rem;opacity:0.7;letter-spacing:1px;text-transform:uppercase">{m_tag} · {sec_label}</div>
                    <div style="font-size:1.15rem;font-weight:800">φMn = {phiMn_tfm:.2f} <span style="font-size:0.72rem;opacity:0.7">tonf·m</span></div>
                    <div style="font-size:0.68rem;opacity:0.8">{status_label} · φ = {capacity.phi:.3f} · εt = {capacity.eps_s:.4f}</div>
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="capacity-badge compression-controlled">
                <span style="font-size:1.1rem">⚡</span>
                <div>
                    <div style="font-size:0.72rem">No tension steel — add reinforcement to calculate capacity</div>
                </div>
            </div>""", unsafe_allow_html=True)
    
    with col2:
        if capacity.phi > 0:
            # φ factor visual bar
            phi_pct = max(0, min(100, (capacity.phi - 0.65) / (0.90 - 0.65) * 100))
            st.markdown(f"""
            <div class="phi-bar-container">
                <div style="font-size:0.65rem;color:#5a6a8a;font-weight:600;letter-spacing:0.5px;text-transform:uppercase">
                    Strength Reduction Factor φ
                </div>
                <div class="phi-bar-track">
                    <div class="phi-bar-marker" style="left:{phi_pct}%"></div>
                </div>
                <div class="phi-bar-labels">
                    <span>0.65</span>
                    <span style="color:#fbbf24">φ = {capacity.phi:.3f}</span>
                    <span>0.90</span>
                </div>
            </div>""", unsafe_allow_html=True)


def _get_flexural_inputs(sec_key: str, pos_moment: bool, geom: SectionGeometry) -> tuple[float, float, float, float, str, str, str]:
    """Calculate effective steel areas and depths based on the moment sign (+M or -M)."""
    h = geom.h
    cover = geom.cover
    stirrup_dia = geom.stirrup_dia
    
    if pos_moment:
        # Positive Moment: Tension at Bottom, Compression at Top
        As = st.session_state[f"As_bot_{sec_key}"]
        Asp = st.session_state[f"As_top_{sec_key}"]
        d_val = st.session_state.get(f"d_bot_{sec_key}")
        dp_val = st.session_state.get(f"d_top_{sec_key}")
        
        d = d_val if d_val else h - cover - stirrup_dia - 25.0
        dp = dp_val if dp_val else cover + stirrup_dia + 25.0
        comp_lbl = "Top  (Compression)"
        tens_lbl = "Bottom  (Tension)"
        m_tag = "+M  Positive Moment"
    else:
        # Negative Moment: Tension at Top, Compression at Bottom
        As = st.session_state[f"As_top_{sec_key}"]
        Asp = st.session_state[f"As_bot_{sec_key}"]
        d_val = st.session_state.get(f"d_top_{sec_key}")
        dp_val = st.session_state.get(f"d_bot_{sec_key}")
        
        # depths from bottom compression face
        d = h - (d_val if d_val else cover + stirrup_dia + 25.0)
        dp = h - (dp_val if dp_val else h - cover - stirrup_dia - 25.0)
        comp_lbl = "Bottom  (Compression)"
        tens_lbl = "Top  (Tension)"
        m_tag = "−M  Negative Moment"
        
    return As, Asp, d, dp, comp_lbl, tens_lbl, m_tag

def _render_inline_editors(sec_key: str, geom: SectionGeometry):
    """Render compact rebar data editors for Bottom/Side and Top rebars."""
    df_bot_key = f"rebar_bot_{sec_key}"
    df_top_key = f"rebar_top_{sec_key}"
    EMPTY_DF = pd.DataFrame(columns=["Layer", "X (mm)", "Y (mm)", "Dia (mm)", "Count", "Bar Size"])
    
    _xy_cfg2 = {
        "X (mm)": st.column_config.NumberColumn("X (mm)", format="%.1f", step=10.0),
        "Y (mm)": st.column_config.NumberColumn("Y (mm)", format="%.1f", step=10.0),
        "Dia (mm)": st.column_config.NumberColumn("Dia (mm)", format="%d", step=2),
        "Count": st.column_config.NumberColumn("Count", format="%d", step=1, min_value=1),
        "Bar Size": st.column_config.SelectboxColumn("Bar Size", options=list(STANDARD_BARS.keys()) + ["Custom"], width="small"),
    }
    
    ed_bt2, ed_tp2 = st.tabs(["⬇  Bottom / Side", "⬆  Top"])
    with ed_bt2:
        fl_bot = st.data_editor(
            st.session_state[df_bot_key],
            num_rows="dynamic", use_container_width=True,
            column_config={
                "Layer": st.column_config.SelectboxColumn("Layer", options=["Bottom", "Side", "Custom"], width="small"),
                **_xy_cfg2,
            },
            key=f"flex_editor_bot_{sec_key}",
            height=200,
        )
        st.session_state[df_bot_key] = fl_bot
        
        fq1, fq2, fq3 = st.columns(3)
        if fq1.button("＋ Bottom", key=f"flex_qa_bot_{sec_key}", use_container_width=True):
            yB2 = -geom.h/2 + geom.cover + 20.0
            new_row = pd.DataFrame([{"Layer": "Bottom", "X (mm)": 0.0, "Y (mm)": yB2, "Dia (mm)": 20, "Count": 1, "Bar Size": "DB20"}])
            st.session_state[df_bot_key] = pd.concat([st.session_state[df_bot_key], new_row], ignore_index=True)
            st.rerun()
        if fq2.button("＋ Side", key=f"flex_qa_side_{sec_key}", use_container_width=True):
            new_row = pd.DataFrame([{"Layer": "Side", "X (mm)": -geom.b/2+geom.cover+20.0, "Y (mm)": 0.0, "Dia (mm)": 12, "Count": 1, "Bar Size": "DB12"}])
            st.session_state[df_bot_key] = pd.concat([st.session_state[df_bot_key], new_row], ignore_index=True)
            st.rerun()
        if fq3.button("🗑 Clear", key=f"flex_clrbot_{sec_key}", use_container_width=True):
            st.session_state[df_bot_key] = EMPTY_DF.copy()
            st.rerun()
            
    with ed_tp2:
        fl_top = st.data_editor(
            st.session_state[df_top_key],
            num_rows="dynamic", use_container_width=True,
            column_config={
                "Layer": st.column_config.SelectboxColumn("Layer", options=["Top", "Custom"], width="small"),
                **_xy_cfg2,
            },
            key=f"flex_editor_top_{sec_key}",
            height=200,
        )
        st.session_state[df_top_key] = fl_top
        
        ft1, ft2 = st.columns(2)
        if ft1.button("＋ Top", key=f"flex_qa_top_{sec_key}", use_container_width=True):
            yT2 = geom.h/2 - geom.cover - 20.0
            new_row = pd.DataFrame([{"Layer": "Top", "X (mm)": 0.0, "Y (mm)": yT2, "Dia (mm)": 16, "Count": 1, "Bar Size": "DB16"}])
            st.session_state[df_top_key] = pd.concat([st.session_state[df_top_key], new_row], ignore_index=True)
            st.rerun()
        if ft2.button("🗑 Clear", key=f"flex_clrtop_{sec_key}", use_container_width=True):
            st.session_state[df_top_key] = EMPTY_DF.copy()
            st.rerun()

def _render_inline_templates(sec_key: str):
    """Render template save/load UI panel inside flexural analysis view."""
    df_bot_key = f"rebar_bot_{sec_key}"
    df_top_key = f"rebar_top_{sec_key}"
    EMPTY_DF = pd.DataFrame(columns=["Layer", "X (mm)", "Y (mm)", "Dia (mm)", "Count", "Bar Size"])
    
    st.markdown('<div class="section-tag">Template</div>', unsafe_allow_html=True)
    ft_name = st.text_input("Name", key=f"flex_tmpl_name_{sec_key}", placeholder="e.g. B400H600-3DB25")
    if st.button("💾 Save", key=f"flex_tmpl_save_{sec_key}", use_container_width=True):
        if ft_name.strip():
            save_template(ft_name, st.session_state[df_bot_key], st.session_state[df_top_key], sec_key)
            st.success(f'Saved "{ft_name.strip()}"', icon="✅")
        else:
            st.warning("Enter a name first.")
            
    if st.session_state.templates:
        st.divider()
        tmpl_keys2 = list(st.session_state.templates.keys())
        sel2 = st.selectbox("Load template", tmpl_keys2, key=f"flex_tmpl_sel_{sec_key}")
        lc1, lc2 = st.columns(2)
        if lc1.button("📥 Load", key=f"flex_tmpl_load_{sec_key}", use_container_width=True):
            bot_df, top_df, _ = load_template(sel2)
            st.session_state[df_bot_key] = bot_df
            st.session_state[df_top_key] = top_df
            st.rerun()
        if lc2.button("🗑 Del", key=f"flex_tmpl_del_{sec_key}", use_container_width=True):
            delete_template(sel2)
            st.rerun()
            
        t2_info = st.session_state.templates[sel2]
        n2_rec = len(t2_info.get("records_bot", [])) + len(t2_info.get("records_top", []))
        st.markdown(f'<div class="tmpl-box"><b>{sel2}</b><br>{n2_rec} bars (from {SECTIONS.get(t2_info.get("origin",""), "?")})</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="tmpl-box">No templates yet.</div>', unsafe_allow_html=True)

def _render_analysis_method_expander(capacity: CapacityResult, concrete: ConcreteProps, steel: SteelProps):
    """Render the Whitney stress-block calculation steps."""
    st.markdown(ANALYSIS_METHOD_STYLE, unsafe_allow_html=True)
    
    # Values
    N_TO_TONF = 1.0 / 9806.65
    NMM_TO_TONFM = 1.0 / 9806650.0
    
    T_tf = capacity.T * N_TO_TONF
    Cc_tf = capacity.Cc * N_TO_TONF
    Cs_tf = capacity.Cs * N_TO_TONF
    Mn_tfm = capacity.Mn * NMM_TO_TONFM
    phiMn_tfm = capacity.phi_Mn * NMM_TO_TONFM
    
    with st.expander("📐  Analysis Method — ACI 318 Rectangular Stress Block", expanded=False):
        st.markdown(f"""
<div class="am">
<h4>Assumptions</h4>
<ul>
  <li>Plane sections remain plane (Bernoulli / Navier hypothesis)</li>
  <li>Maximum concrete compressive strain <b>εcu = 0.003</b></li>
  <li>Tensile strength of concrete is neglected</li>
  <li>Steel is elastic-perfectly plastic — yield plateau at <b>fy</b>,  Es = 200 000 MPa</li>
  <li>Whitney rectangular stress block: intensity <b>0.85 f'c</b>, depth <b>a = β₁·c</b></li>
  <li>Doubly-reinforced: compression steel displacement correction applied when <b>a &gt; d'</b></li>
</ul>
<h4>Step-by-Step Procedure  (Doubly-Reinforced, Newton-Raphson)</h4>
<b>1. Stress-block factor β₁</b> (ACI 318-19 §22.2.2.4, thresholds in ksc)<br>
&nbsp;&nbsp;f'c ≤ 280 ksc → <code>β₁ = 0.85</code> &nbsp;|&nbsp; 280–550 ksc → <code>β₁ = 0.85 − 0.05·(f'c−280)/70</code> &nbsp;|&nbsp; &gt; 550 ksc → <code>β₁ = 0.65</code>
<br><br>
<b>2. Force equilibrium  — iterate c  (Newton-Raphson)</b><br>
&nbsp;&nbsp;<code>Cc = 0.85·f'c·b·(β₁·c)</code> &nbsp; [concrete stress block]<br>
&nbsp;&nbsp;<code>εt  = εcu·(d − c)/c</code> &nbsp;→&nbsp; <code>fst = min(Es·εt, fy)</code> &nbsp; [tension steel]<br>
&nbsp;&nbsp;<code>εc' = εcu·(c − d')/c</code> &nbsp;→&nbsp; <code>fsc = clamp(Es·εc', −fy, fy)</code><br>
&nbsp;&nbsp;<code>Cs  = As'·(fsc − 0.85·f'c)</code> if a &gt; d', else <code>As'·fsc</code> &nbsp; [net comp. steel]<br>
&nbsp;&nbsp;Solve: <code>T − (Cc + Cs) = 0</code> &nbsp;where <code>T = As·fst</code>
<br><br>
<b>3. Strength reduction factor φ  (ACI 318-19 §21.2.2)</b><br>
&nbsp;&nbsp;εt ≥ 0.005 → <code>φ = 0.90</code> (tension-controlled)<br>
&nbsp;&nbsp;εt ≤ 0.002 → <code>φ = 0.65</code> (compression-controlled)<br>
&nbsp;&nbsp;0.002 &lt; εt &lt; 0.005 → <code>φ = 0.65 + (εt − 0.002) × 250/3</code> (transition)
<br><br>
<b>4. Nominal moment capacity</b>  (moments about tension steel centroid)<br>
&nbsp;&nbsp;<code>Mn = Cc·(d − a/2) + Cs·(d − d')</code> &nbsp;[N·mm] ÷ 9 806 650 → tonf·m
<br><br>
<b>5. Design moment capacity</b><br>
&nbsp;&nbsp;<code>φMn = φ × Mn</code>
<br><br>
<b>Current values: </b>
Model calculations:
a = {capacity.a:.1f} mm &nbsp;|&nbsp; c = {capacity.c_na:.1f} mm &nbsp;|&nbsp; β₁ = {concrete.beta1:.3f} &nbsp;|&nbsp;
εt = {capacity.eps_s:.4f} &nbsp;|&nbsp; εc' = {capacity.eps_cp:.4f} &nbsp;|&nbsp; φ = {capacity.phi:.3f}<br>
Cc = {Cc_tf:.2f} tonf &nbsp;|&nbsp; Cs = {Cs_tf:.2f} tonf &nbsp;|&nbsp; T = {T_tf:.2f} tonf<br>
Mn = {Mn_tfm:.2f} tonf·m &nbsp;|&nbsp; φMn = {phiMn_tfm:.2f} tonf·m
</div>""", unsafe_allow_html=True)

def _render_capacity_data_tables(geom: SectionGeometry, concrete: ConcreteProps, steel: SteelProps, As: float, Asp: float, d: float, dp: float, capacity: CapacityResult):
    """Render the details table containing Steel Areas, Depths, and capacity metrics."""
    # Derived values
    b = geom.b
    h = geom.h
    A_eff = b * d if d > 0.0 else 1.0
    rho = As / A_eff
    rho_b = (0.85 * concrete.beta1 * concrete.fc_prime / steel.fy) * (600.0 / (600.0 + steel.fy))
    
    # Forces conversion
    N_TO_TONF = 1.0 / 9806.65
    NMM_TO_TONFM = 1.0 / 9806650.0
    T_tf = capacity.T * N_TO_TONF
    Cc_tf = capacity.Cc * N_TO_TONF
    Cs_tf = capacity.Cs * N_TO_TONF
    Mn_tfm = capacity.Mn * NMM_TO_TONFM
    phiMn_tfm = capacity.phi_Mn * NMM_TO_TONFM

    g1, g2, g3 = st.columns(3)
    
    with g1:
        st.markdown("""<div class="glass-card">
            <div class="glass-card-title">🔩 Steel Areas</div>""", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame({
            "Parameter": ["As  (tension)", "As' (compression)", "A = b × d", "ρ = As/A", "ρ_bal"],
            "Value":     [f"{As/100:.2f}", f"{Asp/100:.2f}", f"{A_eff/100:.1f}", f"{rho*100:.3f}", f"{rho_b*100:.3f}"],
            "Unit":      ["cm²", "cm²", "cm²", "%", "%"],
        }), use_container_width=True, hide_index=True, height=212)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with g2:
        st.markdown("""<div class="glass-card">
            <div class="glass-card-title">📏 Depths</div>""", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame({
            "Parameter": ["h", "d  (tension centroid)", "d' (comp. centroid)", "a  (stress block)", "c  (neutral axis)"],
            "Value":     [f"{h:.0f}", f"{d:.1f}", f"{dp:.1f}", f"{capacity.a:.1f}" if capacity.a is not None else "—", f"{capacity.c_na:.1f}" if capacity.c_na is not None else "—"],
            "Unit":      ["mm", "mm", "mm", "mm", "mm"],
        }), use_container_width=True, hide_index=True, height=212)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with g3:
        st.markdown("""<div class="glass-card">
            <div class="glass-card-title">⚡ Capacity (MKS)</div>""", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame({
            "Parameter": ["εt  (tension)", "εc' (comp. steel)", "φ  (ACI 318)", "Cc (conc. block)", "Cs (comp. steel)", "T  (tension)", "Mn", "φMn"],
            "Value":     [
                f"{capacity.eps_s:.4f}" if capacity.eps_s is not None else "—",
                f"{capacity.eps_cp:.4f}" if capacity.eps_cp is not None else "—",
                f"{capacity.phi:.3f}" if capacity.phi is not None else "—",
                f"{Cc_tf:.2f}" if Cc_tf is not None else "—",
                f"{Cs_tf:.2f}" if capacity.a is not None else "—",
                f"{T_tf:.2f}" if T_tf is not None else "—",
                f"{Mn_tfm:.2f}" if Mn_tfm is not None else "—",
                f"{phiMn_tfm:.2f}" if phiMn_tfm is not None else "—"
            ],
            "Unit":      ["—", "—", "—", "tonf", "tonf", "tonf", "tonf·m", "tonf·m"],
        }), use_container_width=True, hide_index=True, height=310)
        st.markdown("</div>", unsafe_allow_html=True)
