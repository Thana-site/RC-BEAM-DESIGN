"""
RC Section Visualizer — Tab 1 Section UI Component
"""
import streamlit as st
import pandas as pd
import numpy as np
from constants import SECTIONS, STANDARD_BARS
from models.section import SectionGeometry
from models.materials import ConcreteProps, SteelProps
from models.rebar import rebar_df_to_records, RebarRecord
from utils.math_helpers import bar_area
from template_io.templates import save_template, load_template, delete_template
from plotting.section_plot import create_section_plot
from analysis.properties import calculate_cracked_inertia
from analysis.validation import check_bars_outside_bounds

def render_section_tab(sec_key: str, geom: SectionGeometry, concrete: ConcreteProps, steel: SteelProps, display_opts: dict):
    """
    Render full section UI (left: input, right: plot + properties) for one section.
    """
    left_col, right_col = st.columns([1.05, 1], gap="large")
    
    with left_col:
        st.markdown(f'<div class="section-tag">Rebar Input — {SECTIONS[sec_key]}</div>', unsafe_allow_html=True)
        
        edited_df = _render_rebar_editors(sec_key, geom)
        records = rebar_df_to_records(edited_df)
        
        _render_row_generator_expander(sec_key, geom)
        _render_templates_expander(sec_key)
        _render_validation_warnings(geom, records)
        
        st.markdown('<div class="info-box"><b>Origin</b> at centroid · X→ · Y↑ · <b>Count</b> = bars at same position</div>', unsafe_allow_html=True)

    with right_col:
        st.markdown(f'<div class="section-tag">Cross-Section — {SECTIONS[sec_key]}</div>', unsafe_allow_html=True)
        
        fig = create_section_plot(
            geom, records,
            show_dims=display_opts["show_dims"],
            show_centroid=display_opts["show_centroid"],
            show_na=display_opts["show_na"],
            show_cover_box=display_opts["show_cover_box"],
            dark_mode=display_opts["dark_mode"],
            concrete=concrete,
            fy=steel.fy
        )
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{sec_key}")

    # Properties & Summary Table (Spans full width at the bottom of the section tab)
    st.markdown('<div class="section-tag">Section Properties</div>', unsafe_allow_html=True)
    _render_section_properties(geom, records, concrete, steel, sec_key)
    _render_rebar_summary(geom, records)

def _render_rebar_editors(sec_key: str, geom: SectionGeometry) -> pd.DataFrame:
    """Render Bottom/Side and Top rebar table editors."""
    df_bot_key = f"rebar_bot_{sec_key}"
    df_top_key = f"rebar_top_{sec_key}"
    EMPTY_DF = pd.DataFrame(columns=["Layer", "X (mm)", "Y (mm)", "Dia (mm)", "Count", "Bar Size"])
    
    _xy_cfg = {
        "X (mm)": st.column_config.NumberColumn("X (mm)", format="%.1f", step=10.0),
        "Y (mm)": st.column_config.NumberColumn("Y (mm)", format="%.1f", step=10.0),
        "Dia (mm)": st.column_config.NumberColumn("Dia (mm)", format="%d", step=2),
        "Count": st.column_config.NumberColumn("Count", format="%d", step=1, min_value=1),
        "Bar Size": st.column_config.SelectboxColumn("Bar Size", options=list(STANDARD_BARS.keys()) + ["Custom"], width="small"),
    }
    
    rebar_bt, rebar_tp = st.tabs(["⬇  Bottom / Side", "⬆  Top"])
    
    with rebar_bt:
        edited_bot = st.data_editor(
            st.session_state[df_bot_key],
            num_rows="dynamic", use_container_width=True,
            column_config={
                "Layer": st.column_config.SelectboxColumn("Layer", options=["Bottom", "Side", "Custom"], width="small"),
                **_xy_cfg,
            },
            key=f"editor_bot_{sec_key}",
            height=220,
        )
        st.session_state[df_bot_key] = edited_bot
        
        qa_c1, qa_c2, qa_c3 = st.columns(3)
        if qa_c1.button("＋ Bottom", key=f"qa_bot_{sec_key}", use_container_width=True):
            y_b = -geom.h/2 + geom.cover + 20.0
            new_row = pd.DataFrame([{"Layer": "Bottom", "X (mm)": 0.0, "Y (mm)": y_b, "Dia (mm)": 20, "Count": 1, "Bar Size": "DB20"}])
            st.session_state[df_bot_key] = pd.concat([st.session_state[df_bot_key], new_row], ignore_index=True)
            st.rerun()
        if qa_c2.button("＋ Side", key=f"qa_side_{sec_key}", use_container_width=True):
            new_row = pd.DataFrame([{"Layer": "Side", "X (mm)": -geom.b/2+geom.cover+20.0, "Y (mm)": 0.0, "Dia (mm)": 12, "Count": 1, "Bar Size": "DB12"}])
            st.session_state[df_bot_key] = pd.concat([st.session_state[df_bot_key], new_row], ignore_index=True)
            st.rerun()
        if qa_c3.button("🗑 Clear", key=f"qa_clrbot_{sec_key}", use_container_width=True):
            st.session_state[df_bot_key] = EMPTY_DF.copy()
            st.rerun()
            
    with rebar_tp:
        edited_top = st.data_editor(
            st.session_state[df_top_key],
            num_rows="dynamic", use_container_width=True,
            column_config={
                "Layer": st.column_config.SelectboxColumn("Layer", options=["Top", "Custom"], width="small"),
                **_xy_cfg,
            },
            key=f"editor_top_{sec_key}",
            height=220,
        )
        st.session_state[df_top_key] = edited_top
        
        q_top, q_clr = st.columns(2)
        if q_top.button("＋ Top", key=f"qa_top_{sec_key}", use_container_width=True):
            y_t = geom.h/2 - geom.cover - 20.0
            new_row = pd.DataFrame([{"Layer": "Top", "X (mm)": 0.0, "Y (mm)": y_t, "Dia (mm)": 16, "Count": 1, "Bar Size": "DB16"}])
            st.session_state[df_top_key] = pd.concat([st.session_state[df_top_key], new_row], ignore_index=True)
            st.rerun()
        if q_clr.button("🗑 Clear", key=f"qa_clrtop_{sec_key}", use_container_width=True):
            st.session_state[df_top_key] = EMPTY_DF.copy()
            st.rerun()
            
    return pd.concat([edited_bot, edited_top], ignore_index=True)

def _render_row_generator_expander(sec_key: str, geom: SectionGeometry):
    """Render expander form for auto-generating rows of rebar."""
    from analysis.rebar_generator import generate_rebar_coordinates, get_row_preview_y
    df_bot_key = f"rebar_bot_{sec_key}"
    df_top_key = f"rebar_top_{sec_key}"
    
    st.markdown('<div class="section-tag" style="margin-top:8px">Add Rebar by Row</div>', unsafe_allow_html=True)
    with st.expander("Layer · Bar · Spacing → auto-generate positions", expanded=False):
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        rl_layer = c1.selectbox("Layer", ["Bottom", "Top", "Side"], key=f"rl_layer_{sec_key}")
        rl_bar = c2.selectbox("Bar", list(STANDARD_BARS.keys()), index=list(STANDARD_BARS.keys()).index("DB25"), key=f"rl_bar_{sec_key}")
        
        n_lbl = "N bars" + ("/side" if rl_layer == "Side" else "")
        rl_n = c3.number_input(n_lbl, 1, 30, 3, step=1, key=f"rl_n_{sec_key}")
        
        if rl_layer in ("Bottom", "Top"):
            rl_rownum = c4.number_input("Row #", 1, 6, 1, step=1, key=f"rl_rownum_{sec_key}", help="1=nearest face; +1 shifts inward")
        else:
            rl_rownum = 1
            c4.caption("Both faces")
            
        sc1, sc2 = st.columns([1, 1])
        rl_smode = sc1.radio("Spacing", ["Auto", "Fixed"], key=f"rl_smode_{sec_key}", horizontal=True)
        rl_fixed_s = 100.0
        if rl_smode == "Fixed":
            rl_fixed_s = float(sc2.number_input("c/c (mm)", 10, 2000, 100, step=5, key=f"rl_fixeds_{sec_key}"))
            
        if st.button("Add Row to Table", key=f"rl_add_{sec_key}", use_container_width=True):
            dia = float(STANDARD_BARS[rl_bar])
            new_coords = generate_rebar_coordinates(geom, rl_layer, rl_bar, dia, rl_n, rl_rownum, rl_smode, rl_fixed_s)
            new_df = pd.DataFrame([r.to_dict() for r in new_coords])
            
            target_key = df_top_key if rl_layer == "Top" else df_bot_key
            st.session_state[target_key] = pd.concat([st.session_state[target_key], new_df], ignore_index=True)
            st.rerun()
            
        # Preview Text
        dia = float(STANDARD_BARS[rl_bar])
        if rl_layer in ("Bottom", "Top"):
            y_prev = get_row_preview_y(geom, rl_layer, dia, rl_rownum)
            st.markdown(f'<div class="info-box"><b>Preview:</b> {rl_n}×Ø{int(dia)} mm at Y={y_prev} mm (Row {rl_rownum} {rl_layer})</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="info-box"><b>Preview:</b> {rl_n}×Ø{int(dia)} mm/side — {rl_n*2} bars total</div>', unsafe_allow_html=True)

def _render_templates_expander(sec_key: str):
    """Render template save/load UI."""
    df_bot_key = f"rebar_bot_{sec_key}"
    df_top_key = f"rebar_top_{sec_key}"
    
    st.markdown('<div class="section-tag" style="margin-top:8px">Templates</div>', unsafe_allow_html=True)
    with st.expander("Save · Load · Copy between sections", expanded=False):
        c1, c2 = st.columns([2, 1])
        tmpl_name = c1.text_input("Template name", key=f"tmpl_name_{sec_key}", placeholder="e.g. B400H600-3DB25")
        c2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        
        if c2.button("💾 Save", key=f"tmpl_save_{sec_key}", use_container_width=True):
            if tmpl_name.strip():
                save_template(tmpl_name, st.session_state[df_bot_key], st.session_state[df_top_key], sec_key)
                st.success(f'Saved "{tmpl_name.strip()}"', icon="✅")
            else:
                st.warning("Enter a template name first.")
                
        if st.session_state.templates:
            st.divider()
            tmpl_keys = list(st.session_state.templates.keys())
            sel = st.selectbox("Load template", tmpl_keys, key=f"tmpl_sel_{sec_key}")
            lc1, lc2 = st.columns(2)
            
            if lc1.button("📥 Load here", key=f"tmpl_load_{sec_key}", use_container_width=True):
                bot_df, top_df, _ = load_template(sel)
                st.session_state[df_bot_key] = bot_df
                st.session_state[df_top_key] = top_df
                st.rerun()
            if lc2.button("🗑 Delete tmpl", key=f"tmpl_del_{sec_key}", use_container_width=True):
                delete_template(sel)
                st.rerun()
                
            t_info = st.session_state.templates[sel]
            orig = SECTIONS.get(t_info.get("origin", ""), "?")
            n_rec = len(t_info.get("records_bot", [])) + len(t_info.get("records_top", []))
            st.markdown(f'<div class="tmpl-box"><b>{sel}</b> — {n_rec} entries (from {orig})</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="tmpl-box">No templates saved yet.</div>', unsafe_allow_html=True)
            
        # Copy from other sections
        st.divider()
        st.markdown("<small style='color:#5a6a8a'>Copy rebar from another section:</small>", unsafe_allow_html=True)
        other_secs = [s for s in SECTIONS if s != sec_key]
        copy_cols = st.columns(len(other_secs))
        for col, src in zip(copy_cols, other_secs):
            if col.button(f"← {src}", key=f"copy_{src}_{sec_key}", use_container_width=True):
                st.session_state[df_bot_key] = st.session_state[f"rebar_bot_{src}"].copy()
                st.session_state[df_top_key] = st.session_state[f"rebar_top_{src}"].copy()
                st.rerun()

def _render_validation_warnings(geom: SectionGeometry, records: list[RebarRecord]):
    """Display warning box if rebars are positioned outside the cross-section boundary."""
    out_count = check_bars_outside_bounds(geom, records)
    if out_count > 0:
        st.markdown(f'<div class="warn-box">⚠️ <b>{out_count} bar(s)</b> outside boundary.</div>', unsafe_allow_html=True)

def _render_section_properties(geom: SectionGeometry, records: list[RebarRecord], concrete: ConcreteProps, steel: SteelProps, sec_key: str):
    """Render section properties metrics grid — 4 columns × 2 rows for readability."""
    As_bot = st.session_state[f"As_bot_{sec_key}"]
    As_top = st.session_state[f"As_top_{sec_key}"]
    As_total = st.session_state[f"As_total_{sec_key}"]
    rho = st.session_state[f"rho_{sec_key}"]
    d_bot = st.session_state[f"d_bot_{sec_key}"]
    d_top = st.session_state[f"d_top_{sec_key}"]
    
    n = steel.Es_mpa / concrete.Ec_mpa
    Ec_ksc = concrete.Ec_ksc
    
    Icr = calculate_cracked_inertia(geom, As_bot, As_top, d_bot, d_top, n)
    
    # Color for steel ratio
    if rho < 2.0:
        rho_color = "#4ade80"
    elif rho < 4.0:
        rho_color = "#fbbf24"
    else:
        rho_color = "#f87171"
    
    # Row 1: 4 columns
    m1, m2, m3, m4 = st.columns(4)
    row1_metrics = [
        ("Gross Area Ag", f"{geom.Ag/1e4:.2f}", "cm²", "#e8eaf0"),
        ("As,bot ⬇", f"{As_bot:.0f}", "mm²", "#f87171"),
        ("As,top ⬆", f"{As_top:.0f}", "mm²", "#34d399"),
        ("As total", f"{As_total:.0f}", "mm²", "#e8eaf0"),
    ]
    for col, (lbl, val, unit, color) in zip([m1, m2, m3, m4], row1_metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">{lbl}</div>
              <div class="metric-value" style="color:{color}">{val}<span class="metric-unit">{unit}</span></div>
            </div>""", unsafe_allow_html=True)
    
    # Row 2: 4 columns
    m5, m6, m7, m8 = st.columns(4)
    row2_metrics = [
        ("Steel Ratio ρ", f"{rho:.2f}", "%", rho_color),
        ("Gross Ig", f"{geom.Ig/1e8:.2f}", "×10⁸ mm⁴", "#e8eaf0"),
        ("Cracked Icr", f"{Icr/1e8:.2f}", "×10⁸ mm⁴", "#a78bfa"),
        ("Ec  (n)", f"{Ec_ksc/1e3:.0f}", f"×10³ ksc  (n={n:.1f})", "#e8eaf0"),
    ]
    for col, (lbl, val, unit, color) in zip([m5, m6, m7, m8], row2_metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">{lbl}</div>
              <div class="metric-value" style="color:{color}">{val}<span class="metric-unit">{unit}</span></div>
            </div>""", unsafe_allow_html=True)

def _render_rebar_summary(geom: SectionGeometry, records: list[RebarRecord]):
    """Render rebar summary table."""
    if records:
        st.markdown('<div class="section-tag" style="margin-top:10px">Rebar Summary</div>', unsafe_allow_html=True)
        summary = pd.DataFrame([r.to_dict() for r in records])
        summary["A/bar (mm²)"] = summary["Dia (mm)"].apply(bar_area).round(1)
        summary["As (mm²)"] = (summary["A/bar (mm²)"] * summary["Count"]).round(1)
        summary["ρ (%)"] = (summary["As (mm²)"] / geom.Ag * 100.0).round(4) if geom.Ag > 0 else 0.0
        
        disp_cols = ["Layer", "Bar Size", "Dia (mm)", "X (mm)", "Y (mm)", "Count", "A/bar (mm²)", "As (mm²)", "ρ (%)"]
        st.dataframe(summary[disp_cols].reset_index(drop=True), use_container_width=True, height=180)
        
        # Pull values from state to be consistent
        # Find layer sum
        bot_sum = sum(r.count * bar_area(r.dia) for r in records if r.layer == "Bottom")
        top_sum = sum(r.count * bar_area(r.dia) for r in records if r.layer == "Top")
        total_sum = sum(r.count * bar_area(r.dia) for r in records)
        rho_sum = total_sum / geom.Ag * 100.0 if geom.Ag > 0 else 0.0
        
        st.markdown(
            f'<div class="info-box" style="margin-top:4px">'
            f'<b>As,bot</b> = <span style="color:#f87171">{bot_sum:.1f}</span> mm²  ·  '
            f'<b>As,top</b> = <span style="color:#34d399">{top_sum:.1f}</span> mm²  ·  '
            f'<b>Total</b> = {total_sum:.1f} mm²  ·  '
            f'<b>ρ</b> = {rho_sum:.3f} %</div>',
            unsafe_allow_html=True
        )
