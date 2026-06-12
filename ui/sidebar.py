"""
RC Section Visualizer — Sidebar UI Component
"""
import streamlit as st
from constants import STEEL_GRADES, STEEL_LABELS, CONCRETE_GRADES, KSC_TO_MPA
from models.section import SectionGeometry
from models.materials import ConcreteProps, SteelProps

# Common beam presets (b × h)
BEAM_PRESETS = {
    "200×400": (200, 400),
    "250×500": (250, 500),
    "300×600": (300, 600),
    "400×700": (400, 700),
    "400×800": (400, 800),
    "500×900": (500, 900),
}

def render_sidebar() -> tuple[SectionGeometry, ConcreteProps, SteelProps, dict]:
    """
    Render sidebar controls and inputs.
    Returns (SectionGeometry, ConcreteProps, SteelProps, display_options).
    """
    with st.sidebar:
        # ── Section Geometry ──────────────────────────────────────────────
        st.markdown(
            '<div class="sidebar-section-title"><span class="icon">📐</span> Section Geometry</div>',
            unsafe_allow_html=True
        )
        section_type = "Rectangular"
        D = b_f = t_f = b_w = 0.0
        st.markdown('<div class="info-box"><b>Rectangular beam only</b></div>', unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:0.68rem;color:#5a6a8a;margin-bottom:4px;font-weight:600;letter-spacing:0.5px">QUICK PRESETS</div>',
            unsafe_allow_html=True
        )
        preset_cols = st.columns(3)
        preset_keys = list(BEAM_PRESETS.keys())
        for i, col in enumerate(preset_cols):
            for j in range(2):
                idx = i + j * 3
                if idx < len(preset_keys):
                    key = preset_keys[idx]
                    if col.button(key, key=f"preset_{key}", use_container_width=True):
                        st.session_state["_preset_b"], st.session_state["_preset_h"] = BEAM_PRESETS[key]
                        st.rerun()

        default_b = st.session_state.pop("_preset_b", 400)
        default_h = st.session_state.pop("_preset_h", 600)

        _c1, _c2 = st.columns(2)
        b = _c1.number_input("B (mm)", 100, 2000, default_b, step=50)
        h = _c2.number_input("H (mm)", 100, 4000, default_h, step=50)

        st.divider()

        # ── Cover & Stirrup ───────────────────────────────────────────────
        st.markdown(
            '<div class="sidebar-section-title"><span class="icon">🛡️</span> Cover & Stirrup</div>',
            unsafe_allow_html=True
        )

        _c1, _c2 = st.columns(2)
        cover = _c1.number_input("Cover (mm)", 10, 100, 40, step=5)
        stirrup_dia = _c2.number_input("Stirrup Ø (mm)", 6, 20, 10, step=2)

        # Stirrup yield strength (fyt)
        _st1, _st2 = st.columns([3, 2])
        grade_stirrup = _st1.selectbox(
            "Stirrup Grade", list(STEEL_GRADES.keys()),
            index=0, key="grade_stirrup",
            label_visibility="collapsed"
        )
        if grade_stirrup == "Custom":
            fyt_ksc = st.number_input("fyt (ksc)", 1500, 8000, 2400, step=100)
        else:
            fyt_ksc = STEEL_GRADES[grade_stirrup]
            _fyt_mpa = fyt_ksc * KSC_TO_MPA
            _st2.markdown(
                f"<div style='margin-top:24px'>"
                f"<span class='unit-pill ksc'>{fyt_ksc} ksc</span>"
                f"<span class='unit-pill mpa'>{_fyt_mpa:.0f} MPa</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.markdown(
            f"<div style='font-size:0.66rem;color:#4a5580;margin-top:-4px;font-style:italic'>"
            f"{STEEL_LABELS.get(grade_stirrup, 'fyt — stirrup yield strength')}</div>",
            unsafe_allow_html=True
        )

        st.divider()

        # ── Materials ─────────────────────────────────────────────────────
        st.markdown(
            '<div class="sidebar-section-title"><span class="icon">🧱</span> Materials</div>',
            unsafe_allow_html=True
        )

        # Concrete grade
        st.markdown(
            '<div style="font-size:0.65rem;color:#5a6a8a;font-weight:600;letter-spacing:0.5px;margin-bottom:2px">CONCRETE f\'c</div>',
            unsafe_allow_html=True
        )
        _cg1, _cg2 = st.columns([3, 2])
        grade_fc = _cg1.selectbox(
            "Concrete Grade", list(CONCRETE_GRADES.keys()),
            index=3, key="grade_fc",
            label_visibility="collapsed"
        )
        if grade_fc == "Custom":
            fc_ksc = st.number_input("f'c (ksc)", 100, 700, 280, step=5)
        else:
            fc_ksc = CONCRETE_GRADES[grade_fc]
            _fc_mpa = fc_ksc * KSC_TO_MPA
            _cg2.markdown(
                f"<div style='margin-top:24px'>"
                f"<span class='unit-pill ksc'>{fc_ksc} ksc</span>"
                f"<span class='unit-pill mpa'>{_fc_mpa:.1f} MPa</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        # Main Steel grade
        st.markdown(
            '<div style="font-size:0.65rem;color:#5a6a8a;font-weight:600;letter-spacing:0.5px;margin:8px 0 2px">MAIN STEEL fy</div>',
            unsafe_allow_html=True
        )
        _sg1, _sg2 = st.columns([3, 2])
        grade_fy = _sg1.selectbox(
            "Main Steel Grade", list(STEEL_GRADES.keys()),
            index=2, key="grade_fy",
            label_visibility="collapsed"
        )
        if grade_fy == "Custom":
            fy_ksc = st.number_input("fy (ksc)", 1500, 8000, 4000, step=100)
        else:
            fy_ksc = STEEL_GRADES[grade_fy]
            _fy_mpa = fy_ksc * KSC_TO_MPA
            _sg2.markdown(
                f"<div style='margin-top:24px'>"
                f"<span class='unit-pill ksc'>{fy_ksc} ksc</span>"
                f"<span class='unit-pill mpa'>{_fy_mpa:.0f} MPa</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.markdown(
            f"<div style='font-size:0.66rem;color:#4a5580;margin-top:-4px;font-style:italic'>"
            f"{STEEL_LABELS.get(grade_fy, 'fy — longitudinal bar yield strength')}</div>",
            unsafe_allow_html=True
        )

        st.divider()

        # ── Display Options ───────────────────────────────────────────────
        st.markdown(
            '<div class="sidebar-section-title"><span class="icon">🎨</span> Display Options</div>',
            unsafe_allow_html=True
        )
        _d1, _d2 = st.columns(2)
        show_dims      = _d1.checkbox("Dim Lines",    True)
        show_centroid  = _d2.checkbox("Centroid",     True)
        show_na        = _d1.checkbox("Neutral Axis", False)
        show_cover_box = _d2.checkbox("Cover Box",    True)
        dark_mode      = st.checkbox("Light Background", False)

    # Instantiate Models
    geom = SectionGeometry(
        section_type=section_type,
        b=b,
        h=h,
        cover=cover,
        stirrup_dia=stirrup_dia,
        D=D,
        b_f=b_f,
        t_f=t_f,
        b_w=b_w
    )
    concrete = ConcreteProps(fc_ksc=fc_ksc)
    steel = SteelProps(fy_ksc=fy_ksc, fyt_ksc=fyt_ksc)
    
    display_opts = {
        "show_dims": show_dims,
        "show_centroid": show_centroid,
        "show_na": show_na,
        "show_cover_box": show_cover_box,
        "dark_mode": dark_mode
    }
    
    return geom, concrete, steel, display_opts
