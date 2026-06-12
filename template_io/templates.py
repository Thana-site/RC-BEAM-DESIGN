"""
RC Section Visualizer — Template Operations (IO)
"""
import streamlit as st
import pandas as pd

def save_template(name: str, bot_df: pd.DataFrame, top_df: pd.DataFrame, origin: str) -> bool:
    """
    Save the current rebar configuration as a template.
    Returns True if successfully saved, False otherwise.
    """
    name_stripped = name.strip()
    if not name_stripped:
        return False
        
    st.session_state.templates[name_stripped] = {
        "records_bot": bot_df.to_dict("records"),
        "records_top": top_df.to_dict("records"),
        "origin": origin,
    }
    return True

def load_template(name: str) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Load a rebar template by name.
    Returns (bot_df, top_df, origin).
    """
    EMPTY_COLS = ["Layer", "X (mm)", "Y (mm)", "Dia (mm)", "Count", "Bar Size"]
    EMPTY_DF = pd.DataFrame(columns=EMPTY_COLS)
    
    if name not in st.session_state.templates:
        return EMPTY_DF.copy(), EMPTY_DF.copy(), ""
        
    t = st.session_state.templates[name]
    origin = t.get("origin", "")
    
    if "records_bot" in t:
        bot_df = pd.DataFrame(t["records_bot"])
        top_df = pd.DataFrame(t["records_top"])
    else:  # Legacy single-table format support
        all_df = pd.DataFrame(t.get("records", []))
        if len(all_df) and "Layer" in all_df.columns:
            bot_df = all_df[all_df["Layer"] != "Top"].reset_index(drop=True)
            top_df = all_df[all_df["Layer"] == "Top"].reset_index(drop=True)
        else:
            bot_df = EMPTY_DF.copy()
            top_df = EMPTY_DF.copy()
            
    return bot_df, top_df, origin

def delete_template(name: str) -> bool:
    """Delete a template by name."""
    if name in st.session_state.templates:
        del st.session_state.templates[name]
        return True
    return False
