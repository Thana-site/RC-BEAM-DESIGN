"""
RC Section Visualizer — Streamlit Session State Helpers
"""
import streamlit as st
import pandas as pd
from constants import SECTIONS
from models.section import SectionGeometry
from models.rebar import rebar_df_to_records
from utils.math_helpers import bar_area

def default_rebar_bot(b_val: float, h_val: float, cov: float) -> pd.DataFrame:
    """Generate default bottom/side reinforcement DataFrame."""
    xL = -b_val / 2.0 + cov + 20.0
    xR =  b_val / 2.0 - cov - 20.0
    yB = -h_val / 2.0 + cov + 20.0
    return pd.DataFrame([
        {"Layer": "Bottom", "X (mm)": xL, "Y (mm)": yB, "Dia (mm)": 25, "Count": 1, "Bar Size": "DB25"},
        {"Layer": "Bottom", "X (mm)": 0.0, "Y (mm)": yB, "Dia (mm)": 25, "Count": 1, "Bar Size": "DB25"},
        {"Layer": "Bottom", "X (mm)": xR, "Y (mm)": yB, "Dia (mm)": 25, "Count": 1, "Bar Size": "DB25"},
        {"Layer": "Side",   "X (mm)": xL, "Y (mm)": 0.0, "Dia (mm)": 12, "Count": 1, "Bar Size": "DB12"},
        {"Layer": "Side",   "X (mm)": xR, "Y (mm)": 0.0, "Dia (mm)": 12, "Count": 1, "Bar Size": "DB12"},
    ])

def default_rebar_top(b_val: float, h_val: float, cov: float) -> pd.DataFrame:
    """Generate default top reinforcement DataFrame."""
    xL = -b_val / 2.0 + cov + 20.0
    xR =  b_val / 2.0 - cov - 20.0
    yT =  h_val / 2.0 - cov - 20.0
    return pd.DataFrame([
        {"Layer": "Top", "X (mm)": xL, "Y (mm)": yT, "Dia (mm)": 16, "Count": 1, "Bar Size": "DB16"},
        {"Layer": "Top", "X (mm)": xR, "Y (mm)": yT, "Dia (mm)": 16, "Count": 1, "Bar Size": "DB16"},
    ])

def init_session_state(b: float, h: float, cover: float):
    """Initialize default rebars and templates in session state if not already initialized."""
    for sec in SECTIONS:
        if f"rebar_bot_{sec}" not in st.session_state:
            st.session_state[f"rebar_bot_{sec}"] = default_rebar_bot(b, h, cover)
        if f"rebar_top_{sec}" not in st.session_state:
            st.session_state[f"rebar_top_{sec}"] = default_rebar_top(b, h, cover)

    if "templates" not in st.session_state:
        st.session_state.templates = {}

def update_session_state_properties(geom: SectionGeometry):
    """
    Precompute steel areas, ratios, and effective depths for all sections.
    Updates the results in st.session_state.
    """
    from analysis.properties import get_steel_area, calculate_effective_depth

    for sec in SECTIONS:
        # Load tables and merge
        df_bot = st.session_state[f"rebar_bot_{sec}"]
        df_top = st.session_state[f"rebar_top_{sec}"]
        df_all = pd.concat([df_bot, df_top], ignore_index=True)
        
        # Convert to records
        records = rebar_df_to_records(df_all)
        
        # Compute steel areas
        bot_area = get_steel_area(records, "Bottom")
        top_area = get_steel_area(records, "Top")
        side_area = get_steel_area(records, "Side")
        total_area = bot_area + top_area + side_area
        
        # Save areas in state
        st.session_state[f"As_bot_{sec}"] = bot_area
        st.session_state[f"As_top_{sec}"] = top_area
        st.session_state[f"As_side_{sec}"] = side_area
        st.session_state[f"As_total_{sec}"] = total_area
        
        # Steel ratio
        ag = geom.Ag
        st.session_state[f"rho_{sec}"] = (total_area / ag * 100.0) if ag else 0.0
        
        # Effective depths (measured from top compression face in MKS coords)
        st.session_state[f"d_bot_{sec}"] = calculate_effective_depth(records, "Bottom", geom.h)
        st.session_state[f"d_top_{sec}"] = calculate_effective_depth(records, "Top", geom.h)
