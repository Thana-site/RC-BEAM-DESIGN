"""Single-page rectangular reinforced concrete beam design app."""

import streamlit as st

from config import CUSTOM_CSS
from ui import render_beam_design_workflow, render_calculation_details, render_notation_tab, render_sidebar, render_traceability_center
from utils import init_session_state, update_session_state_properties


st.set_page_config(
    page_title="RC Rectangular Beam Design",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown(
    """
    <div class="app-header">
      <span style="font-size:1.7rem">RC</span>
      <div>
        <h1>RC Beam Design Platform</h1>
        <p><span class="status-dot"></span>Traceable exterior, mid, and interior span design - MKS (kgf, ksc, mm)</p>
      </div>
      <span class="version-tag">ACI 318-19 / TIS</span>
    </div>
    """,
    unsafe_allow_html=True,
)

geom, concrete, steel, display_opts = render_sidebar()

init_session_state(geom.b, geom.h, geom.cover)
update_session_state_properties(geom)

design_tab, details_tab, trace_tab, notation_tab = st.tabs(["Beam Design", "Calculation Details", "Traceability", "Notation"])

with design_tab:
    design_results, rebar_summaries, span_lengths = render_beam_design_workflow(geom, concrete, steel, display_opts)

with details_tab:
    render_calculation_details(geom, concrete, steel, design_results)

with trace_tab:
    render_traceability_center(geom, concrete, steel, design_results, rebar_summaries, span_lengths)

with notation_tab:
    render_notation_tab(geom, concrete, steel)

st.markdown(
    """
    <div style="text-align:center;margin-top:20px;padding:14px 0 10px;
      border-top:1px solid rgba(42,48,80,0.3);
      background: linear-gradient(180deg, transparent, rgba(13,15,24,0.5));">
      <span style="font-size:0.72rem;color:#3a4060;letter-spacing:0.5px;">
        RC Rectangular Beam Design - ACI 318-19 / TIS 1008
        &nbsp;|&nbsp;
        <span style="color:#4a5580">MKS: kgf, ksc, mm</span>
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)
